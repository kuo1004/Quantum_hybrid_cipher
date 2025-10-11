# -*- coding: utf-8 -*-
"""
pqenc.py — 後量子混合式檔案加密傳輸（不做隱寫）
- KEM: ML-KEM (OQS) 用接收端公鑰封裝，接收端私鑰解封裝
- 對稱: AES-GCM (分段加密)
- 金鑰導出: HKDF(SHA-256) 從 KEM shared secret 導出 32 bytes AES key
- 容器: [MAGIC][header_len][header_json][chunks...]
  * AAD = MAGIC || header_json || seqno    （每段都會驗證）
  * chunk record = [seqno(4)][pt_len(4)][iv(12)][ct_len(4)][ct...]
"""

import os, sys, time, json, base64, struct, argparse, hashlib, math
from datetime import datetime

#sys.path.append("D:/graduation_project/liboqs-python")
try:
    import oqs
    import oqs.oqs as oqs_mod
except Exception as e:
    print("❌ 無法載入 liboqs-python：", e)
    if len(sys.argv) > 1 and sys.argv[1] == "diagnose":
        sys.exit(1)
    else:
        raise

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

MAGIC = b"PQENCv1\x00"  # 8 bytes
DEFAULT_ALG = "ML-KEM-1024"
DEFAULT_CHUNK = 4 * 1024 * 1024  # 4 MiB
def diagnose_liboqs():
    """列印 liboqs-python 與 C 函式庫版本資訊，及 DLL 來源路徑"""
    print("🔍 liboqs-python 版本 :", oqs_mod.oqs_python_version())
    print("🔍 liboqs C 函式庫版本:", oqs_mod.liboqs_versionstr())
    try:
        dll_path = oqs_mod.native()._name  # Windows DLL 路徑
    except AttributeError:
        dll_path = "(未知)"
    print("📂 DLL 路徑:", dll_path)
    print("💡 如果版本不一致，請確認 DLL 與 Python 套件版本對齊，並檢查 PATH。")
# ------------------------- 小工具 -------------------------
def b64e(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")

def b64d(s: str) -> bytes:
    return base64.b64decode(s.encode("ascii"))

def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for ch in iter(lambda: f.read(1024*1024), b""):
            h.update(ch)
    return h.hexdigest()

def parse_size(s: str) -> int:
    """接受 4096 / 4MiB / 8MB 等寫法（MB 視為 10^6，MiB 視為 2^20）。"""
    s = s.strip().lower()
    if s.endswith("kib"):
        return int(float(s[:-3]) * 1024)
    if s.endswith("mib"):
        return int(float(s[:-3]) * 1024**2)
    if s.endswith("gib"):
        return int(float(s[:-3]) * 1024**3)
    if s.endswith("kb"):
        return int(float(s[:-2]) * 1000)
    if s.endswith("mb"):
        return int(float(s[:-2]) * 1000**2)
    if s.endswith("gb"):
        return int(float(s[:-2]) * 1000**3)
    return int(s)

# ---------------------- KEM 金鑰管理 ----------------------
def kem_generate_keypair(kem_alg: str, pub_path: str, priv_path: str):
    print(f"🔑 生成 KEM 金鑰對（{kem_alg}）...")
    kem = oqs.KeyEncapsulation(kem_alg)
    public_key = kem.generate_keypair()             # bytes
    try:
        secret_key = kem.export_secret_key()        # bytes
    except AttributeError:
        raise RuntimeError("你的 liboqs-python 版本不支援 export_secret_key()，請更新。")

    with open(pub_path, "wb") as f:
        f.write(public_key)
    with open(priv_path, "wb") as f:
        f.write(secret_key)
    print(f"📤 公鑰：{pub_path}  ({len(public_key)} bytes)")
    print(f"📥 私鑰：{priv_path}  ({len(secret_key)} bytes)")
    kem.free()

def kem_load_pub(pub_path: str) -> bytes:
    with open(pub_path, "rb") as f:
        pk = f.read()
    return pk

def kem_load_priv(kem_alg: str, priv_path: str) -> oqs.KeyEncapsulation:
    kem = oqs.KeyEncapsulation(kem_alg)
    try:
        with open(priv_path, "rb") as f:
            sk = f.read()
        kem.import_secret_key(sk)
    except AttributeError:
        kem.free()
        raise RuntimeError("你的 liboqs-python 版本不支援 import_secret_key()，請更新。")
    return kem

# ---------------------- 金鑰導出（HKDF） ----------------------
def derive_aes_key(shared_secret: bytes, salt: bytes, length: int = 32) -> bytes:
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=length,
        salt=salt,
        info=b"PQENC-AESGCM-v1",
    )
    return hkdf.derive(shared_secret)

# ---------------------- Header 打包/解析 ----------------------
def build_header_json(**kwargs) -> bytes:
    # 將 header 編碼為 UTF-8 JSON，供所有 chunk 作 AAD 綁定
    return json.dumps(kwargs, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

def read_exact(f, n: int) -> bytes:
    b = f.read(n)
    if len(b) != n:
        raise EOFError("檔案結構不完整或已損壞（讀取長度不足）")
    return b

# ---------------------- 加密主流程 ----------------------
def encrypt_file(input_path: str, out_path: str, recipient_pub_path: str,
                 kem_alg: str = DEFAULT_ALG, chunk_size: int = DEFAULT_CHUNK):
    file_size = os.path.getsize(input_path)
    file_name = os.path.basename(input_path)
    print(f"📦 準備加密：{input_path}  ({file_size} bytes)")
    print(f"    SHA-256: {sha256_file(input_path)}")

    # 1) KEM：用接收端公鑰封裝 → shared secret
    pk = kem_load_pub(recipient_pub_path)
    with oqs.KeyEncapsulation(kem_alg) as encap:
        encapsulated_key, shared = encap.encap_secret(pk)

    # 2) 從 shared 導出 AES 會話金鑰
    hkdf_salt = os.urandom(16)
    aes_key = derive_aes_key(shared, hkdf_salt, 32)
    aesgcm = AESGCM(aes_key)

    # 3) 分段參數 & Header
    total_chunks = math.ceil(file_size / chunk_size) if file_size > 0 else 1
    iv_salt = os.urandom(8)  # 8 bytes，IV = iv_salt || counter(4)
    header_obj = {
        "v": 1,
        "kem_alg": kem_alg,
        "encapsulated_key": b64e(encapsulated_key),
        "hkdf_salt": b64e(hkdf_salt),
        "iv_salt": b64e(iv_salt),
        "chunk_size": chunk_size,
        "file_size": file_size,
        "total_chunks": total_chunks,
        "file_name": file_name,
        "created_at": int(time.time()),
    }
    header_bytes = build_header_json(**header_obj)
    aad_prefix = MAGIC + header_bytes

    t0 = time.perf_counter()
    with open(input_path, "rb") as fin, open(out_path, "wb") as fout:
        # 寫 MAGIC + header_len + header_bytes
        fout.write(MAGIC)
        fout.write(struct.pack(">I", len(header_bytes)))
        fout.write(header_bytes)

        # 4) 逐段加密
        seqno = 0
        while True:
            pt = fin.read(chunk_size)
            if not pt and seqno >= total_chunks:
                break
            if not pt:
                pt = b""

            # IV = 8 bytes salt + 4 bytes counter (big-endian)
            iv = iv_salt + struct.pack(">I", seqno)
            aad = aad_prefix + struct.pack(">Q", seqno)  # 綁定序號

            ct = aesgcm.encrypt(iv, pt, aad)  # 回傳 = ciphertext||tag（末尾 16 bytes 是 tag）
            # 寫入 chunk record
            fout.write(struct.pack(">I", seqno))
            fout.write(struct.pack(">I", len(pt)))
            fout.write(iv)                       # 12 bytes
            fout.write(struct.pack(">I", len(ct)))
            fout.write(ct)

            seqno += 1
            if total_chunks >= 10 and seqno % max(1, total_chunks // 10) == 0:
                print(f"  · 進度 {seqno}/{total_chunks} 段")

    t1 = time.perf_counter()
    print(f"✅ 加密完成 → {out_path}")
    print(f"🕐 總耗時：{t1 - t0:.3f}s；段數：{total_chunks}；分段大小：{chunk_size} bytes")
    return out_path

# ---------------------- 解密主流程 ----------------------
def decrypt_file(in_path: str, out_path: str, recipient_priv_path: str):
    print(f"🔓 準備解密：{in_path}")
    t0 = time.perf_counter()

    with open(in_path, "rb") as fin:
        magic = read_exact(fin, len(MAGIC))
        if magic != MAGIC:
            raise ValueError("檔案格式錯誤（MAGIC 不符）")

        header_len = struct.unpack(">I", read_exact(fin, 4))[0]
        header_bytes = read_exact(fin, header_len)
        header = json.loads(header_bytes.decode("utf-8"))

        # 解析 header
        kem_alg = header["kem_alg"]
        encapsulated_key = b64d(header["encapsulated_key"])
        hkdf_salt = b64d(header["hkdf_salt"])
        iv_salt = b64d(header["iv_salt"])
        chunk_size = int(header["chunk_size"])
        file_size = int(header["file_size"])
        total_chunks = int(header["total_chunks"])
        file_name = header.get("file_name", "recovered.bin")

        # KEM decap → shared → 導出 AES key
        kem = kem_load_priv(kem_alg, recipient_priv_path)
        shared = kem.decap_secret(encapsulated_key)
        kem.free()
        aes_key = derive_aes_key(shared, hkdf_salt, 32)
        aesgcm = AESGCM(aes_key)
        aad_prefix = MAGIC + header_bytes

        # 逐段解密
        written = 0
        seq_expect = 0
        with open(out_path or file_name, "wb") as fout:
            while True:
                hdr = fin.read(4)
                if not hdr:
                    break  # EOF
                if len(hdr) < 4:
                    raise EOFError("chunk 標頭不完整")
                seqno = struct.unpack(">I", hdr)[0]
                pt_len = struct.unpack(">I", read_exact(fin, 4))[0]
                iv = read_exact(fin, 12)
                ct_len = struct.unpack(">I", read_exact(fin, 4))[0]
                ct = read_exact(fin, ct_len)

                if seqno != seq_expect:
                    raise ValueError(f"chunk 序號不連續：期望 {seq_expect}，實得 {seqno}")
                aad = aad_prefix + struct.pack(">Q", seqno)
                pt = aesgcm.decrypt(iv, ct, aad)

                if len(pt) != pt_len:
                    raise ValueError("解密後長度與記錄不符（可能資料遭竄改）")

                fout.write(pt)
                written += len(pt)
                seq_expect += 1

        if written != file_size:
            raise ValueError(f"解密後大小不符：宣告 {file_size}，實際 {written}")

    t1 = time.perf_counter()
    print(f"✅ 解密完成 → {out_path or file_name}  （{written} bytes）")
    print(f"🕐 總耗時：{t1 - t0:.3f}s；段數：{seq_expect}")

# ---------------------- CLI ----------------------
def main():
    ap = argparse.ArgumentParser(description="後量子混合式檔案加密傳輸（不做隱寫）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("genkey", help="產生 KEM 金鑰對")
    p1.add_argument("--alg", default=DEFAULT_ALG)
    p1.add_argument("--pub", required=True, help="輸出公鑰檔")
    p1.add_argument("--priv", required=True, help="輸出私鑰檔")

    p2 = sub.add_parser("encrypt", help="加密檔案 → .pqenc")
    p2.add_argument("--in", dest="inp", required=True)
    p2.add_argument("--out", required=True)
    p2.add_argument("--pub", required=True, help="接收端公鑰檔")
    p2.add_argument("--alg", default=DEFAULT_ALG)
    p2.add_argument("--chunk", default=str(DEFAULT_CHUNK),
                    help="分段大小（ex: 4MiB, 8MiB, 1048576）")

    p3 = sub.add_parser("decrypt", help="解密 .pqenc → 原檔")
    p3.add_argument("--in", dest="inp", required=True)
    p3.add_argument("--out", default="", help="輸出檔名（預設用原始 file_name）")
    p3.add_argument("--priv", required=True, help="接收端私鑰檔（與公鑰配對生成）")

    args = ap.parse_args()

    if args.cmd == "genkey":
        kem_generate_keypair(args.alg, args.pub, args.priv)

    elif args.cmd == "encrypt":
        chunk = parse_size(args.chunk)
        if chunk < 64 * 1024:
            print("⚠️ 分段太小，可能造成大量開銷；建議 ≥ 1MiB")
        out = args.out
        if not out.lower().endswith(".pqenc"):
            out += ".pqenc"
        encrypt_file(args.inp, out, args.pub, kem_alg=args.alg, chunk_size=chunk)

    elif args.cmd == "decrypt":
        decrypt_file(args.inp, args.out, args.priv)

if __name__ == "__main__":
    main()
