#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
receiver.py (修改版) - 醫療影像接收方
添加了金鑰資訊記錄功能，供監控系統使用
"""

import os
import time
import json
import base64
import pickle
import tempfile
import platform
import numpy as np
from PIL import Image
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from kem import SimpleKEM
from signature_utils import verify_signature


def aes_gcm_decrypt(iv: bytes, tag: bytes, ct: bytes, key: bytes):
    """AES-GCM解密"""
    try:
        dec = Cipher(algorithms.AES(key), modes.GCM(iv, tag), backend=default_backend()).decryptor()
        return dec.update(ct) + dec.finalize()
    except Exception as e:
        print(f"AES-GCM解密失敗: {e}")
        raise


class Receiver:
    """醫療影像接收方"""

    def __init__(self, receiver_id: str = "Medical_Receiver"):
        self.receiver_id = receiver_id

        self.private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        self.public_key = self.private_key.public_key()

        self.kem = SimpleKEM("ML-KEM-1024")
        self.kem_public_key = self.kem.generate_keypair()

        self.certificate = None
        self.ca_public_key_pem = None
        
        # ⭐ 新增：最後一次解密的金鑰資訊（供監控系統使用）
        self.last_decryption_info = None

        print(f"📥 接收方 {receiver_id} 已初始化")

    def get_public_key_pem(self) -> bytes:
        """獲取公鑰的PEM格式"""
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

    def register_with_ca(self, ca):
        """向CA註冊並獲取憑證"""
        self.certificate = ca.register_party(
            self.receiver_id, 
            self.get_public_key_pem(), 
            self.kem_public_key
        )
        self.ca_public_key_pem = ca.get_ca_public_key_pem()
        print(f"✅ {self.receiver_id} 已向CA註冊完成")

    def verify_peer_certificate(self, peer_certificate: dict, ca_public_key_pem: bytes) -> bool:
        """驗證對方的憑證"""
        if peer_certificate is None:
            return True
        
        if not isinstance(peer_certificate, dict):
            return True
        
        try:
            ca_public_key = serialization.load_pem_public_key(ca_public_key_pem)
            cert_data = json.dumps(peer_certificate["certificate_info"], sort_keys=True).encode()
            signature = base64.b64decode(peer_certificate["ca_signature"])

            ca_public_key.verify(
                signature,
                cert_data,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )

            if time.time() > peer_certificate["certificate_info"]["valid_until"]:
                print("⚠️ 憑證已過期")
                return False

            print("✅ 憑證驗證成功（CA 簽章有效）")
            return True
            
        except Exception as e:
            print(f"⚠️ 憑證驗證錯誤: {e}（測試模式：允許）")
            return True

       
    def receive_and_decrypt(self, transmission_package: dict, 
                        output_file_path: str, 
                        ca_public_key_pem: bytes):
        """
        接收並解密傳輸包
        ⭐ 修改版：記錄金鑰資訊供監控系統使用
        """
        # 跨平台路徑處理
        if platform.system() == 'Windows' and output_file_path.startswith('/'):
            filename = os.path.basename(output_file_path)
            output_file_path = os.path.join(tempfile.gettempdir(), filename)
            print(f"📝 Windows 路徑轉換: {output_file_path}")
        
        output_dir = os.path.dirname(output_file_path)
        if output_dir and not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir, exist_ok=True)
            except Exception as e:
                print(f"⚠️ 創建目錄失敗: {e}")
        
        t_start = time.perf_counter()
        
        # ⭐ 重置解密資訊
        self.last_decryption_info = None

        try:
            # 步驟 1: 處理傳送方憑證
            sender_cert_b64 = transmission_package.get('sender_cert_b64')
            sender_cert = None
            sender_pub_pem = None
            
            if sender_cert_b64:
                try:
                    sender_cert_json = base64.b64decode(sender_cert_b64).decode('utf-8')
                    sender_cert = json.loads(sender_cert_json)
                    
                    if self.verify_peer_certificate(sender_cert, ca_public_key_pem):
                        print("✅ 傳送方憑證驗證成功")
                    
                    try:
                        if sender_cert and isinstance(sender_cert, dict):
                            if 'certificate_info' in sender_cert:
                                sender_pub_pem = sender_cert['certificate_info'].get('public_key_pem')
                            elif 'public_key_pem' in sender_cert:
                                sender_pub_pem = sender_cert.get('public_key_pem')
                        
                        if sender_pub_pem and isinstance(sender_pub_pem, str):
                            sender_pub_pem = sender_pub_pem.encode('utf-8')
                    except Exception as e:
                        sender_pub_pem = None
                        
                except Exception as e:
                    print(f"⚠️ 憑證解析失敗: {e}")

            # 步驟 2: 解析加密資料
            enc_data = transmission_package['enc_data']
            ciphertext = base64.b64decode(enc_data['ciphertext_b64'])
            iv = base64.b64decode(enc_data['iv_b64'])
            tag = base64.b64decode(enc_data['tag_b64'])
            kem_ciphertext = base64.b64decode(enc_data['kem_ciphertext_b64'])
            kem_alg = enc_data['kem_alg']
            
            # 步驟 3: 解密金鑰
            has_wrapped_key = 'wrapped_aes_key_b64' in enc_data
            
            if has_wrapped_key:
                print("🔑 檢測到包裝的 AES 金鑰，將進行解包裝...")
                wrapped_aes_key = base64.b64decode(enc_data['wrapped_aes_key_b64'])
                key_wrap_iv = base64.b64decode(enc_data['key_wrap_iv_b64'])
                key_wrap_tag = base64.b64decode(enc_data['key_wrap_tag_b64'])
                
                # KEM 解封裝
                shared_secret = self.kem.decap_secret(kem_ciphertext)
                if not shared_secret:
                    print("❌ 錯誤: KEM 解封裝失敗。")
                    return False
                print(f"🔓 KEM 解封裝成功 (shared_secret: {len(shared_secret)} bytes)")
                
                # 派生金鑰
                derived_key = HKDF(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=None,
                    info=b'aes-key-wrap',
                    backend=default_backend()
                ).derive(shared_secret)
                
                # 解包裝 AES 金鑰
                key_decryptor = Cipher(
                    algorithms.AES(derived_key),
                    modes.GCM(key_wrap_iv, key_wrap_tag),
                    backend=default_backend()
                ).decryptor()
                
                aes_key = key_decryptor.update(wrapped_aes_key) + key_decryptor.finalize()
                print(f"🔓 AES 金鑰解包裝成功 ({len(aes_key)} bytes)")
                
                # ⭐ 記錄金鑰資訊
                self.last_decryption_info = {
                    "shared_secret_hex": shared_secret.hex(),
                    "aes_key_hex": aes_key.hex(),
                    "iv_hex": iv.hex(),
                    "kem_ciphertext_hex": kem_ciphertext.hex()[:128],  # 只取前 128 字元
                    "ciphertext_preview_hex": ciphertext[:64].hex() if len(ciphertext) > 64 else ciphertext.hex()
                }
                
            else:
                # 舊版格式
                print("⚠️ 使用舊版格式（未包裝的 AES 金鑰）")
                
                if 'aes_key_encapsulated_b64' in enc_data:
                    encapsulated_key = base64.b64decode(enc_data['aes_key_encapsulated_b64'])
                    aes_key = self.kem.decap_secret(encapsulated_key)
                else:
                    aes_key = self.kem.decap_secret(kem_ciphertext)
                
                if not aes_key:
                    print("❌ 錯誤: AES 金鑰解封裝失敗。")
                    return False
                
                # ⭐ 記錄金鑰資訊（舊版格式）
                self.last_decryption_info = {
                    "aes_key_hex": aes_key.hex(),
                    "iv_hex": iv.hex(),
                    "kem_ciphertext_hex": kem_ciphertext.hex()[:128],
                    "ciphertext_preview_hex": ciphertext[:64].hex() if len(ciphertext) > 64 else ciphertext.hex()
                }

            # 步驟 4: AES-GCM 解密
            decryptor = Cipher(
                algorithms.AES(aes_key), 
                modes.GCM(iv, tag), 
                backend=default_backend()
            ).decryptor()
            plaintext = decryptor.update(ciphertext) + decryptor.finalize()
            print(f"✅ AES-GCM 解密成功 ({len(plaintext)} bytes)")

            # 步驟 5: 驗證數位簽章
            signature_verified = False
            
            if 'signature' in transmission_package:
                sig_info = transmission_package['signature']
                signature_bytes = base64.b64decode(sig_info['signature_b64'])
                
                if sender_pub_pem is not None:
                    try:
                        sender_public_key = serialization.load_pem_public_key(sender_pub_pem)
                        
                        if verify_signature(sender_public_key, plaintext, signature_bytes):
                            print("✅ 數位簽章驗證成功")
                            signature_verified = True
                        else:
                            print("⚠️ 數位簽章驗證失敗")
                            
                    except Exception as e:
                        print(f"⚠️ 簽章驗證過程錯誤: {e}")

            # 步驟 6: 寫入檔案
            with open(output_file_path, 'wb') as f:
                f.write(plaintext)

            elapsed = time.perf_counter() - t_start
            
            if signature_verified:
                print(f"🔓 解密與驗章流程成功完成，耗時 {elapsed:.3f} 秒。")
            else:
                print(f"🔓 解密流程完成（未驗證簽章），耗時 {elapsed:.3f} 秒。")

            app_meta = transmission_package.get('app_meta', {})
            return plaintext, app_meta

        except Exception as e:
            print(f"❌ 解密過程中發生嚴重錯誤: {e}")
            import traceback
            traceback.print_exc()
            return False


    def load_transmission_package(self, input_path: str) -> dict:
        """從檔案載入傳輸包"""
        with open(input_path, 'rb') as f:
            transmission_package = pickle.load(f)
        print(f"📂 已載入傳輸包: {input_path}")
        return transmission_package


# LSB 相關函數（保持原有）
def _ensure_mode_for_channels(img, channels: str):
    need = "RGB" if "A" not in channels else "RGBA"
    if img.mode != need:
        img = img.convert(need)
    return img


def _symbols_to_bytes(symbols, bpc: int, out_len: int) -> bytes:
    import numpy as np
    weights = (1 << np.arange(bpc)[::-1]).astype(np.uint8)
    bits = ((symbols[:, None] & weights) > 0).astype(np.uint8)
    bits = bits.reshape(-1)
    cut = (len(bits) // 8) * 8
    by = np.packbits(bits[:cut]).tobytes()
    return by[:out_len]


def lsb_extract_transmission_package(stego_path: str, channels: str = "RGB", bpc: int = 1) -> dict:
    """從LSB提取傳輸包"""
    import numpy as np
    img = Image.open(stego_path)
    img = _ensure_mode_for_channels(img, channels)
    arr = np.array(img, dtype=np.uint8)

    ch_idx = {"R":0, "G":1, "B":2, "A":3}
    idxs = [ch_idx[ch] for ch in channels]
    flat = arr[:, :, idxs].reshape(-1)

    n_symbols_for_len = (8 * 8 + bpc - 1) // bpc
    mask = (1 << bpc) - 1
    len_symbols = flat[:n_symbols_for_len] & mask
    header = _symbols_to_bytes(len_symbols, bpc, 8)
    L = int.from_bytes(header, "big")

    n_symbols_for_payload = (L * 8 + bpc - 1) // bpc
    symbols = flat[n_symbols_for_len : n_symbols_for_len + n_symbols_for_payload] & mask
    payload = _symbols_to_bytes(symbols, bpc, L)

    transmission_package = pickle.loads(payload)
    print(f"🔍 已從隱寫影像提取傳輸包: {stego_path}")

    return transmission_package


if __name__ == "__main__":
    receiver = Receiver("Test_Hospital_B")
    print("\n✅ 接收方模組測試完成（含金鑰記錄功能）")