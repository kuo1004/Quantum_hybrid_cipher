# encryptor.py
# 加密方程式 - 使用第三方公鑰進行混合加密
# 使用方式: python encryptor.py --input video.mp4 --pub public.key

import os, time, json, pickle, struct, hashlib, argparse
import oqs
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend


MAGIC = b"VX1GCM"
TAG_LEN = 16


def _gcm_encrypt_chunk(key: bytes, iv: bytes, plaintext: bytes, aad: bytes | None):
    enc = Cipher(algorithms.AES(key), modes.GCM(iv), backend=default_backend()).encryptor()
    if aad:
        enc.authenticate_additional_data(aad)
    ct = enc.update(plaintext) + enc.finalize()
    return ct, enc.tag


def _aad_for_chunk(header_json_bytes: bytes, idx: int) -> bytes:
    h = hashlib.sha256(header_json_bytes).digest()
    return h + struct.pack(">I", idx)


def load_public_key(public_key_path: str):
    """載入第三方公鑰"""
    if not os.path.exists(public_key_path):
        raise FileNotFoundError(f"公鑰檔案不存在: {public_key_path}")
    
    with open(public_key_path, "rb") as f:
        data = pickle.load(f)
    
    print(f"📤 載入公鑰: {data['metadata']['key_id']} ({data['metadata']['algorithm']})")
    return data['public_key'], data['metadata']


def hybrid_encrypt_with_public_key(input_path: str,
                                   encrypted_path: str,
                                   encrypted_key_path: str,
                                   public_key_path: str,
                                   chunk_size: int = 4 * 1024 * 1024,
                                   encryptor_id: str = "anonymous"):
    """使用第三方公鑰進行混合加密"""
    
    # 載入第三方公鑰
    public_key, key_metadata = load_public_key(public_key_path)
    kem_alg = key_metadata['algorithm']
    key_id = key_metadata['key_id']
    
    fsize = os.path.getsize(input_path)
    nonce_prefix = os.urandom(8)
    
    # 擴展的元數據
    meta = {
        "v": 1,
        "orig_size": fsize,
        "chunk_size": chunk_size,
        "nonce_prefix": nonce_prefix.hex(),
        "filename": os.path.basename(input_path),
        "aead": "AES-GCM",
        "key_id": key_id,
        "encryptor_id": encryptor_id,
        "encrypted_at": int(time.time()),
        "kem_algorithm": kem_alg
    }
    hdr_json = json.dumps(meta, separators=(',', ':')).encode()
    header = MAGIC + struct.pack(">I", len(hdr_json)) + hdr_json

    print(f"🎞️ [加密方] 開始加密: {input_path}")
    print(f"📋 使用金鑰: {key_id} ({kem_alg})")
    print(f"👤 加密方ID: {encryptor_id}")
    print(f"📊 檔案大小: {fsize:,} bytes")

    t0 = time.perf_counter()
    
    # 1) 產生會話 AES-256 key
    aes_key = os.urandom(32)
    print(f"🔐 生成AES會話密鑰: {len(aes_key)} bytes")

    # 2) 使用第三方公鑰進行 ML-KEM 封裝
    with oqs.KeyEncapsulation(kem_alg) as encap:
        encapsulated_key, shared = encap.encap_secret(public_key)
    
    print(f"🔒 ML-KEM封裝完成: {len(encapsulated_key)} bytes")
    
    # XOR 包裹 AES 密鑰
    aes_key_encrypted = bytes(a ^ b for a, b in zip(aes_key, shared[:32]))

    # 3) 串流分塊加密
    total_chunks = (fsize + chunk_size - 1) // chunk_size
    print(f"📦 開始分塊加密: {total_chunks} 塊 x {chunk_size//1024//1024}MB")
    
    with open(input_path, "rb") as fin, open(encrypted_path, "wb") as fout:
        fout.write(header)
        
        for idx in range(total_chunks):
            plain = fin.read(chunk_size)
            iv = nonce_prefix + struct.pack(">I", idx)
            aad = _aad_for_chunk(hdr_json, idx)
            ct, tag = _gcm_encrypt_chunk(aes_key, iv, plain, aad)
            fout.write(ct)
            fout.write(tag)
            
            # 進度顯示
            if total_chunks > 10 and (idx + 1) % max(1, total_chunks // 10) == 0:
                progress = (idx + 1) * 100 // total_chunks
                print(f"  📈 進度: {progress}% ({idx + 1}/{total_chunks})")

    # 4) 儲存金鑰封裝資料
    key_package = {
        "encapsulated_key": encapsulated_key,
        "aes_key_encrypted": aes_key_encrypted,
        "key_id": key_id,
        "encryptor_id": encryptor_id,
        "timestamp": int(time.time()),
        "kem_algorithm": kem_alg
    }
    
    with open(encrypted_key_path, "wb") as f:
        pickle.dump(key_package, f, protocol=pickle.HIGHEST_PROTOCOL)

    t1 = time.perf_counter()
    
    # 輸出統計
    encrypted_size = os.path.getsize(encrypted_path)
    key_size = os.path.getsize(encrypted_key_path)
    overhead = encrypted_size - fsize
    
    print(f"\n✅ 加密完成!")
    print(f"📁 原始檔案: {fsize:,} bytes")
    print(f"📁 密文檔案: {encrypted_size:,} bytes")
    print(f"📁 金鑰檔案: {key_size:,} bytes")
    print(f"📈 空間開銷: {overhead:,} bytes ({overhead/fsize*100:.2f}%)")
    print(f"⏱️ 加密耗時: {t1-t0:.3f} 秒")
    print(f"🚀 處理速度: {fsize/(t1-t0)/1024/1024:.1f} MB/s")
    
    print(f"\n📋 輸出檔案:")
    print(f"  密文: {encrypted_path}")
    print(f"  金鑰: {encrypted_key_path}")


def derive_output_names(input_path: str, custom_prefix: str = None):
    d, fname = os.path.split(input_path)
    stem, ext = os.path.splitext(fname)
    
    if custom_prefix:
        enc_path = os.path.join(d, f"{custom_prefix}.hyb")
        key_path = os.path.join(d, f"{custom_prefix}.pkl")
    else:
        enc_path = os.path.join(d, f"{fname}.hyb")
        key_path = os.path.join(d, f"{fname}.pkl")
    
    return enc_path, key_path


def main():
    parser = argparse.ArgumentParser(description="混合加密系統 - 加密方")
    parser.add_argument("--input", required=True, help="輸入檔案路徑")
    parser.add_argument("--pub", required=True, help="公鑰檔案路徑")
    parser.add_argument("--output", help="輸出檔名前綴 (預設使用輸入檔名)")
    parser.add_argument("--chunk-mib", type=int, default=4, 
                        choices=[1, 2, 4, 8, 16, 32],
                        help="分塊大小(MiB)")
    parser.add_argument("--encryptor-id", default="anonymous", help="加密方識別碼")
    
    args = parser.parse_args()

    # 檢查輸入檔案
    if not os.path.isfile(args.input):
        print(f"❌ 找不到輸入檔案: {args.input}")
        exit(1)
    
    # 檢查公鑰檔案
    if not os.path.isfile(args.pub):
        print(f"❌ 找不到公鑰檔案: {args.pub}")
        exit(1)

    try:
        # 生成輸出檔名
        enc_path, key_path = derive_output_names(args.input, args.output)
        
        # 檢查輸出檔案是否已存在
        for path in [enc_path, key_path]:
            if os.path.exists(path):
                response = input(f"⚠️ 檔案 {path} 已存在，是否覆蓋? (y/N): ")
                if response.lower() != 'y':
                    print("❌ 取消加密操作")
                    exit(1)

        # 執行加密
        hybrid_encrypt_with_public_key(
            input_path=args.input,
            encrypted_path=enc_path,
            encrypted_key_path=key_path,
            public_key_path=args.pub,
            chunk_size=args.chunk_mib * 1024 * 1024,
            encryptor_id=args.encryptor_id
        )
        
        print(f"\n📮 請將以下檔案傳送給解密方:")
        print(f"  🔒 {enc_path}")
        print(f"  🗝️ {key_path}")

    except KeyboardInterrupt:
        print("\n⚠️ 加密被使用者中斷")
    except Exception as e:
        print(f"❌ 加密失敗: {e}")
        exit(1)


if __name__ == "__main__":
    main()
