# hybrid_video_one_shot.py
# 使用方式：python hybrid_video_one_shot.py input.mp4
import os, time, json, pickle, struct, hashlib, argparse
import oqs
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

MAGIC = b"VX1GCM"
TAG_LEN = 16  # AES-GCM tag 長度

def _gcm_encrypt_chunk(key: bytes, iv: bytes, plaintext: bytes, aad: bytes | None):
    enc = Cipher(algorithms.AES(key), modes.GCM(iv), backend=default_backend()).encryptor()
    if aad:
        enc.authenticate_additional_data(aad)
    ct = enc.update(plaintext) + enc.finalize()
    return ct, enc.tag

def _gcm_decrypt_chunk(key: bytes, iv: bytes, ciphertext: bytes, tag: bytes, aad: bytes | None):
    dec = Cipher(algorithms.AES(key), modes.GCM(iv, tag), backend=default_backend()).decryptor()
    if aad:
        dec.authenticate_additional_data(aad)
    return dec.update(ciphertext) + dec.finalize()

def _aad_for_chunk(header_json_bytes: bytes, idx: int) -> bytes:
    # AAD 綁定檔頭與區塊序，使竄改/洗牌能被偵測
    h = hashlib.sha256(header_json_bytes).digest()
    return h + struct.pack(">I", idx)

def hybrid_encrypt_file_stream(input_path: str,
                               encrypted_path: str,
                               encrypted_key_path: str,
                               kem_alg: str = "ML-KEM-1024",
                               chunk_size: int = 4 * 1024 * 1024):
    """將任意檔案（包含影片）分塊做 AES-GCM；KEM 封裝金鑰寫 sidecar。"""
    fsize = os.path.getsize(input_path)
    nonce_prefix = os.urandom(8)  # 8B 前綴 + 4B 計數器 = 12B GCM nonce
    meta = {
        "v": 1,
        "orig_size": fsize,
        "chunk_size": chunk_size,
        "nonce_prefix": nonce_prefix.hex(),
        "filename": os.path.basename(input_path),
        "aead": "AES-GCM",
    }
    hdr_json = json.dumps(meta).encode()
    header = MAGIC + struct.pack(">I", len(hdr_json)) + hdr_json

    # 1) 產生會話 AES-256 key
    t0 = time.perf_counter()
    aes_key = os.urandom(32)

    # 2) ML-KEM 封裝
    kem = oqs.KeyEncapsulation(kem_alg)
    pk = kem.generate_keypair()
    with oqs.KeyEncapsulation(kem_alg) as encap:
        encapsulated_key, shared = encap.encap_secret(pk)
    # 與你現有專案一致：使用 XOR 包裹 CEK（亦可改 HKDF 版本）
    aes_key_encrypted = bytes(a ^ b for a, b in zip(aes_key, shared[:32]))

    # 3) 串流分塊加密
    total_chunks = (fsize + chunk_size - 1) // chunk_size
    with open(input_path, "rb") as fin, open(encrypted_path, "wb") as fout:
        fout.write(header)  # 寫檔頭（含自我描述 JSON）
        for idx in range(total_chunks):
            plain = fin.read(chunk_size)
            iv = nonce_prefix + struct.pack(">I", idx)
            aad = _aad_for_chunk(hdr_json, idx)
            ct, tag = _gcm_encrypt_chunk(aes_key, iv, plain, aad)
            fout.write(ct)
            fout.write(tag)

    # 4) sidecar 寫入 KEM 封裝資料
    with open(encrypted_key_path, "wb") as f:
        pickle.dump({
            "kem_alg": kem_alg,
            "encapsulated_key": encapsulated_key,
            "aes_key_encrypted": aes_key_encrypted,
        }, f, protocol=pickle.HIGHEST_PROTOCOL)

    t1 = time.perf_counter()
    print(f"🎞️ 加密完成 -> {encrypted_path}  （{fsize} bytes, {total_chunks} 塊）")
    print(f"🔐 金鑰封裝 -> {encrypted_key_path}")
    print(f"🕐 耗時：{t1 - t0:.3f}s")
    return kem  # 含私鑰的物件（當輪可用來解密）

def hybrid_decrypt_file_stream(encrypted_path: str,
                               encrypted_key_path: str,
                               output_path: str,
                               kem_priv):
    """解密上一函式產出的密文；需要同一次執行中的 kem_priv（含私鑰）。"""
    with open(encrypted_path, "rb") as fin:
        magic = fin.read(len(MAGIC))
        if magic != MAGIC:
            raise ValueError("檔頭 magic 不符，非本工具產物或檔案損毀")

        hdr_len = struct.unpack(">I", fin.read(4))[0]
        hdr_json = fin.read(hdr_len)
        meta = json.loads(hdr_json.decode())
        orig_size = int(meta["orig_size"])
        chunk_size = int(meta["chunk_size"])
        nonce_prefix = bytes.fromhex(meta["nonce_prefix"])
        total_chunks = (orig_size + chunk_size - 1) // chunk_size

        # 還原 AES key
        with open(encrypted_key_path, "rb") as f:
            kp = pickle.load(f)
        enc_kem = kp["encapsulated_key"]
        aes_key_enc = kp["aes_key_encrypted"]
        shared = kem_priv.decap_secret(enc_kem)
        aes_key = bytes(a ^ b for a, b in zip(aes_key_enc, shared[:32]))

        # 串流解密
        with open(output_path, "wb") as fout:
            remaining = orig_size
            for idx in range(total_chunks):
                plen = min(chunk_size, remaining)
                ct = fin.read(plen)
                tag = fin.read(TAG_LEN)
                if len(ct) != plen or len(tag) != TAG_LEN:
                    raise IOError("密文長度異常或檔案受損")
                iv = nonce_prefix + struct.pack(">I", idx)
                aad = _aad_for_chunk(hdr_json, idx)
                pt = _gcm_decrypt_chunk(aes_key, iv, ct, tag, aad)
                fout.write(pt)
                remaining -= plen

    print(f"✅ 解密完成 -> {output_path}")

def derive_output_names(input_path: str):
    d, fname = os.path.split(input_path)
    stem, ext = os.path.splitext(fname)
    enc_path = os.path.join(d, f"{fname}.hyb")
    key_path = os.path.join(d, f"{fname}.key.pkl")
    dec_path = os.path.join(d, f"{stem}.decrypted{ext or ''}")
    return enc_path, key_path, dec_path

def main():
    ap = argparse.ArgumentParser(description="Hybrid AES-GCM + ML-KEM：一次性加密並立即解密驗證")
    ap.add_argument("input", help="輸入影片或任意檔案路徑，例如 input.mp4")
    ap.add_argument("--kem", default="ML-KEM-1024", help="KEM 演算法（預設 ML-KEM-1024）")
    ap.add_argument("--chunk-mib", type=int, default=4, help="每塊大小（MiB，預設 4）")
    args = ap.parse_args()

    inp = args.input
    if not os.path.isfile(inp):
        raise SystemExit(f"找不到檔案：{inp}")

    enc_path, key_path, dec_path = derive_output_names(inp)

    print(f"來源：{inp}")
    print(f"將輸出：\n  密文  -> {enc_path}\n  key   -> {key_path}\n  明文  -> {dec_path}")
    kem_obj = hybrid_encrypt_file_stream(
        input_path=inp,
        encrypted_path=enc_path,
        encrypted_key_path=key_path,
        kem_alg=args.kem,
        chunk_size=args.chunk_mib * 1024 * 1024
    )
    # 立即解密驗證
    hybrid_decrypt_file_stream(enc_path, key_path, dec_path, kem_obj)

    # 驗證一致性（可選）
    ok = (os.path.getsize(inp) == os.path.getsize(dec_path))
    print("🔍 大小比對：", "OK" if ok else "⚠️ 不一致（請進一步做位元逐一比對）")

if __name__ == "__main__":
    main()
