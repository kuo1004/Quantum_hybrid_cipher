import os
import sys
import time
from PIL import Image
import numpy as np
import base64
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

# === AES-GCM 加/解密 with timing ===
def aes_gcm_encrypt(data: bytes, key: bytes):
    iv = os.urandom(12)
    encryptor = Cipher(
        algorithms.AES(key), 
        modes.GCM(iv), 
        backend=default_backend()
    ).encryptor()
    start_time = time.perf_counter()
    ct = encryptor.update(data) + encryptor.finalize()
    enc_time = time.perf_counter() - start_time
    return iv, encryptor.tag, ct, enc_time

def aes_gcm_decrypt(iv: bytes, tag: bytes, ct: bytes, key: bytes):
    decryptor = Cipher(
        algorithms.AES(key), 
        modes.GCM(iv, tag), 
        backend=default_backend()
    ).decryptor()
    start_time = time.perf_counter()
    data = decryptor.update(ct) + decryptor.finalize()
    dec_time = time.perf_counter() - start_time
    return data, dec_time

# === 在 α 通道做 LSB embed / extract ===
def lsb_embed_alpha(image_path, secret: bytes, output_path):
    img = Image.open(image_path).convert("RGBA")
    arr = np.array(img)
    h, w, _ = arr.shape

    bits = ''.join(format(b, '08b') for b in secret)
    if len(bits) > h * w:
        raise ValueError("影像太小，放不下 secret")

    alpha = arr[..., 3].flatten()
    for i, bit in enumerate(bits):
        alpha[i] = (alpha[i] & 0xFE) | int(bit)
    arr[..., 3] = alpha.reshape((h, w))

    Image.fromarray(arr, 'RGBA').save(output_path)
    print(f"✅ 已於 α 通道 LSB 藏入 secret → {output_path}")

def lsb_extract_alpha(stego_path, secret_len):
    img = Image.open(stego_path).convert("RGBA")
    arr = np.array(img)
    alpha = arr[..., 3].flatten()
    n = secret_len * 8
    bits = [str(alpha[i] & 1) for i in range(n)]
    data = bytes(int(''.join(bits[i:i+8]), 2) for i in range(0, n, 8))
    return data

# === 主流程 ===
if __name__ == "__main__":
    # 檔名設定
    src           = "input.png"       # 原圖
    tmp_cipher    = "cipher.png"      # 暫存：ciphertext 放 RGBA
    stego         = "stego.png"       # 最終：藏完 α channel 的 stego
    recovered_png = "decrypted.png"   # 解密後

    # 1) 讀原圖 RGB → flatten → AES-GCM 加密
    img = Image.open(src).convert("RGB")
    arr = np.array(img)
    h, w, c = arr.shape
    plain = arr.tobytes()

    key = os.urandom(32)
    iv, tag, ct, enc_time = aes_gcm_encrypt(plain, key)
    print(f"⏱️ AES-GCM 加密時間: {enc_time:.4f} 秒")

    # 2) 用 ciphertext bytes 重建一張 RGBA（α 全 255）
    ct_arr = np.frombuffer(ct, dtype=np.uint8).reshape((h, w, c))
    alpha = np.full((h, w, 1), 255, dtype=np.uint8)
    rgba = np.concatenate([ct_arr, alpha], axis=2)  # shape (h,w,4)
    Image.fromarray(rgba, 'RGBA').save(tmp_cipher)

    # 3) 把 key‖iv‖tag 藏入 tmp_cipher 的 α LSB → stego.png
    secret = key + iv + tag   # 32 + 12 + 16 = 60 bytes
    lsb_embed_alpha(tmp_cipher, secret, stego)

    # —— 此後只要 stego.png 就能「先還原密鑰」+「解密」——

    # 4) extract secret
    rec = lsb_extract_alpha(stego, len(secret))
    key2, iv2, tag2 = rec[:32], rec[32:44], rec[44:]
    print("🔑 已從 stego.png 提取金鑰參數")

    # 5) 讀回 stego.png 的 RGB 當 ciphertext → AES-GCM 解密
    img2 = Image.open(stego).convert("RGBA")
    arr2 = np.array(img2)[..., :3]
    ct2 = arr2.tobytes()
    plain2, dec_time = aes_gcm_decrypt(iv2, tag2, ct2, key2)
    print(f"⏱️ AES-GCM 解密時間: {dec_time:.4f} 秒")

    # 6) 重建原圖
    dec_arr = np.frombuffer(plain2, dtype=np.uint8).reshape((h, w, c))
    Image.fromarray(dec_arr, 'RGB').save(recovered_png)
    print(f"✅ 已還原並解密成 {recovered_png}")
