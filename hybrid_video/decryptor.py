# decryptor.py
# 解密方程式 - 使用第三方私鑰進行混合解密
# 使用方式: python decryptor.py --input video.mp4.hyb --priv private.key

import os, time, json, pickle, struct, hashlib, argparse
import oqs
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend


MAGIC = b"VX1GCM"
TAG_LEN = 16


def _gcm_decrypt_chunk(key: bytes, iv: bytes, ciphertext: bytes, tag: bytes, aad: bytes | None):
    dec = Cipher(algorithms.AES(key), modes.GCM(iv, tag), backend=default_backend()).decryptor()
    if aad:
        dec.authenticate_additional_data(aad)
    return dec.update(ciphertext) + dec.finalize()


def _aad_for_chunk(header_json_bytes: bytes, idx: int) -> bytes:
    h = hashlib.sha256(header_json_bytes).digest()
    return h + struct.pack(">I", idx)


def load_private_key(private_key_path: str, kem_alg: str):
    """載入第三方私鑰並重建KEM物件"""
    if not os.path.exists(private_key_path):
        raise FileNotFoundError(f"私鑰檔案不存在: {private_key_path}")
    
    with open(private_key_path, "rb") as f:
        data = pickle.load(f)
    
    # 重建KEM物件
    kem = oqs.KeyEncapsulation(kem_alg)
    kem.import_secret_key(data['private_key'])
    
    print(f"📥 載入私鑰: {data['metadata']['key_id']} ({data['metadata']['algorithm']})")
    return kem, data['metadata']


def analyze_encrypted_file(encrypted_path: str):
    """分析加密檔案的標頭資訊"""
    print(f"🔍 分析加密檔案: {encrypted_path}")
    
    with open(encrypted_path, "rb") as fin:
        # 檢查 MAGIC
        magic = fin.read(len(MAGIC))
        if magic != MAGIC:
            raise ValueError("檔頭 magic 不符，非本工具產物或檔案損毀")

        # 讀取標頭
        hdr_len = struct.unpack(">I", fin.read(4))[0]
        hdr_json = fin.read(hdr_len)
        meta = json.loads(hdr_json.decode())
        
        # 顯示檔案資訊
        print(f"📋 檔案資訊:")
        print(f"  原始檔名: {meta['filename']}")
        print(f"  原始大小: {meta['orig_size']:,} bytes")
        print(f"  分塊大小: {meta['chunk_size']:,} bytes ({meta['chunk_size']//1024//1024} MB)")
        print(f"  總分塊數: {(meta['orig_size'] + meta['chunk_size'] - 1) // meta['chunk_size']}")
        print(f"  加密演算法: {meta.get('aead', 'AES-GCM')}")
        print(f"  KEM演算法: {meta.get('kem_algorithm', 'ML-KEM-1024')}")
        print(f"  金鑰ID: {meta.get('key_id', 'unknown')}")
        print(f"  加密方: {meta.get('encryptor_id', 'unknown')}")
        
        if 'encrypted_at' in meta:
            encrypt_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(meta['encrypted_at']))
            print(f"  加密時間: {encrypt_time}")
        
        return meta


def hybrid_decrypt_with_private_key(encrypted_path: str,
                                   encrypted_key_path: str,
                                   output_path: str,
                                   private_key_path: str):
    """使用第三方私鑰進行混合解密"""
    
    print(f"🔓 [解密方] 開始解密: {os.path.basename(encrypted_path)}")
    
    # 1) 分析加密檔案
    meta = analyze_encrypted_file(encrypted_path)
    
    orig_size = int(meta["orig_size"])
    chunk_size = int(meta["chunk_size"])
    nonce_prefix = bytes.fromhex(meta["nonce_prefix"])
    total_chunks = (orig_size + chunk_size - 1) // chunk_size
    key_id = meta.get("key_id", "unknown")
    kem_alg = meta.get("kem_algorithm", "ML-KEM-1024")
    encryptor_id = meta.get("encryptor_id", "unknown")

    # 2) 載入第三方私鑰
    print(f"\n🔐 載入私鑰檔案...")
    kem_priv, key_metadata = load_private_key(private_key_path, kem_alg)
    
    # 驗證金鑰匹配
    if key_metadata['key_id'] != key_id:
        print(f"⚠️ 警告: 金鑰ID不匹配")
        print(f"   檔案需要: {key_id}")
        print(f"   私鑰提供: {key_metadata['key_id']}")
        response = input("   是否繼續解密? (y/N): ")
        if response.lower() != 'y':
            print("❌ 解密取消")
            kem_priv.free()
            return

    # 3) 載入金鑰封裝資料
    print(f"🗝️ 載入金鑰封裝檔案...")
    if not os.path.exists(encrypted_key_path):
        raise FileNotFoundError(f"金鑰封裝檔案不存在: {encrypted_key_path}")
    
    with open(encrypted_key_path, "rb") as f:
        key_package = pickle.load(f)
    
    encapsulated_key = key_package["encapsulated_key"]
    aes_key_encrypted = key_package["aes_key_encrypted"]
    
    print(f"📊 封裝金鑰: {len(encapsulated_key)} bytes")

    # 4) ML-KEM 解封裝
    print(f"🔓 執行ML-KEM解封裝...")
    t0 = time.perf_counter()
    
    shared = kem_priv.decap_secret(encapsulated_key)
    aes_key = bytes(a ^ b for a, b in zip(aes_key_encrypted, shared[:32]))
    
    print(f"🔐 AES密鑰復原完成: {len(aes_key)} bytes")

    # 5) 串流解密
    print(f"📦 開始分塊解密: {total_chunks} 塊")
    
    with open(encrypted_path, "rb") as fin:
        # 跳過標頭
        fin.read(len(MAGIC))
        hdr_len = struct.unpack(">I", fin.read(4))[0]
        hdr_json = fin.read(hdr_len)
        
        # 解密分塊
        with open(output_path, "wb") as fout:
            remaining = orig_size
            
            for idx in range(total_chunks):
                plen = min(chunk_size, remaining)
                ct = fin.read(plen)
                tag = fin.read(TAG_LEN)
                
                if len(ct) != plen or len(tag) != TAG_LEN:
                    raise IOError(f"密文長度異常: 分塊 {idx}")
                    
                iv = nonce_prefix + struct.pack(">I", idx)
                aad = _aad_for_chunk(hdr_json, idx)
                
                try:
                    pt = _gcm_decrypt_chunk(aes_key, iv, ct, tag, aad)
                except Exception as e:
                    raise ValueError(f"分塊 {idx} 解密或驗證失敗: {e}")
                    
                fout.write(pt)
                remaining -= len(pt)
                
                # 進度顯示
                if total_chunks > 10 and (idx + 1) % max(1, total_chunks // 10) == 0:
                    progress = (idx + 1) * 100 // total_chunks
                    print(f"  📈 進度: {progress}% ({idx + 1}/{total_chunks})")

    t1 = time.perf_counter()
    kem_priv.free()
    
    # 驗證解密結果
    decrypted_size = os.path.getsize(output_path)
    
    print(f"\n✅ 解密完成!")
    print(f"📁 原始大小: {orig_size:,} bytes")
    print(f"📁 解密大小: {decrypted_size:,} bytes")
    print(f"🔍 大小驗證: {'✅ 通過' if orig_size == decrypted_size else '❌ 失敗'}")
    print(f"⏱️ 解密耗時: {t1-t0:.3f} 秒")
    print(f"🚀 處理速度: {orig_size/(t1-t0)/1024/1024:.1f} MB/s")
    print(f"📂 解密檔案: {output_path}")


def derive_output_path(encrypted_path: str, custom_output: str = None):
    """推導解密輸出檔案路徑"""
    if custom_output:
        return custom_output
    
    if encrypted_path.endswith('.hyb'):
        base = encrypted_path[:-4]  # 移除 .hyb
        
        # 嘗試從標頭讀取原始檔名
        try:
            with open(encrypted_path, "rb") as f:
                f.read(len(MAGIC))
                hdr_len = struct.unpack(">I", f.read(4))[0]
                hdr_json = f.read(hdr_len)
                meta = json.loads(hdr_json.decode())
                original_name = meta.get('filename', '')
                
                if original_name:
                    dir_path = os.path.dirname(encrypted_path)
                    stem, ext = os.path.splitext(original_name)
                    return os.path.join(dir_path, f"{stem}.decrypted{ext}")
        except:
            pass
    
    # 回退方案
    return encrypted_path + '.decrypted'


def main():
    parser = argparse.ArgumentParser(description="混合加密系統 - 解密方")
    parser.add_argument("--input", required=True, help="加密檔案(.hyb)路徑")
    parser.add_argument("--key", help="金鑰封裝檔案(.pkl)路徑 (自動推斷)")
    parser.add_argument("--priv", required=True, help="私鑰檔案路徑")
    parser.add_argument("--output", help="解密輸出路徑 (自動推斷)")
    parser.add_argument("--info-only", action="store_true", help="僅顯示檔案資訊，不解密")
    
    args = parser.parse_args()

    # 檢查加密檔案
    if not os.path.isfile(args.input):
        print(f"❌ 找不到加密檔案: {args.input}")
        exit(1)
    
    if not args.input.endswith('.hyb'):
        print(f"❌ 輸入檔案必須是 .hyb 格式")
        exit(1)

    try:
        # 僅顯示資訊模式
        if args.info_only:
            analyze_encrypted_file(args.input)
            return

        # 推導金鑰檔案路徑
        key_path = args.key or args.input[:-4] + '.pkl'
        if not os.path.isfile(key_path):
            print(f"❌ 找不到金鑰封裝檔案: {key_path}")
            print(f"   請使用 --key 指定正確路徑")
            exit(1)

        # 檢查私鑰檔案
        if not os.path.isfile(args.priv):
            print(f"❌ 找不到私鑰檔案: {args.priv}")
            exit(1)

        # 推導輸出路徑
        output_path = derive_output_path(args.input, args.output)
        
        # 檢查輸出檔案是否已存在
        if os.path.exists(output_path):
            response = input(f"⚠️ 檔案 {output_path} 已存在，是否覆蓋? (y/N): ")
            if response.lower() != 'y':
                print("❌ 取消解密操作")
                exit(1)

        # 執行解密
        hybrid_decrypt_with_private_key(
            encrypted_path=args.input,
            encrypted_key_path=key_path,
            output_path=output_path,
            private_key_path=args.priv
        )

    except KeyboardInterrupt:
        print("\n⚠️ 解密被使用者中斷")
    except Exception as e:
        print(f"❌ 解密失敗: {e}")
        exit(1)


if __name__ == "__main__":
    main()
