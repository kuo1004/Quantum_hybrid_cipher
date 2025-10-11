import os
import time
import sys
import pickle
import oqs

from PIL import Image
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

# === AES-GCM 加解密 ===
def aes_gcm_encrypt(data: bytes, key: bytes):
    iv = os.urandom(12)
    encryptor = Cipher(algorithms.AES(key), modes.GCM(iv), backend=default_backend()).encryptor()
    ct = encryptor.update(data) + encryptor.finalize()
    return iv, encryptor.tag, ct

def aes_gcm_decrypt(iv: bytes, tag: bytes, ct: bytes, key: bytes):
    decryptor = Cipher(algorithms.AES(key), modes.GCM(iv, tag), backend=default_backend()).decryptor()
    data = decryptor.update(ct) + decryptor.finalize()
    return data

# === 混合加密：加密端 ===
def hybrid_encrypt(input_image_path, encrypted_image_path, encrypted_key_path, kem_alg="ML-KEM-1024"):
    """
    混合加密流程：
    1. 讀取影像
    2. 生成隨機AES密鑰
    3. 用AES加密影像
    4. 用ML-KEM封裝AES密鑰
    5. 儲存加密影像和封裝的密鑰
    """

    
    # 1. 讀取影像 (不計時)
    img = Image.open(input_image_path)
    mode, size = img.mode, img.size
    raw_data = img.tobytes()
    print(f"📷 圖像模式={mode}, 尺寸={size}, 數據量={len(raw_data)} bytes")
    
    # === 混合加密總計時開始 ===
    total_start = time.perf_counter()
    
    # 2. 生成隨機AES密鑰
    aes_key = os.urandom(32)  # AES-256密鑰
    
    # 3. 用AES加密影像
    iv, tag, ciphertext = aes_gcm_encrypt(raw_data, aes_key)
    
    # 4. 用ML-KEM封裝AES密鑰
    # 生成KEM密鑰對
    kem = oqs.KeyEncapsulation(kem_alg)
    public_key = kem.generate_keypair()
    
    # 封裝AES密鑰
    with oqs.KeyEncapsulation(kem_alg) as encapsulator:
        encapsulated_key, shared_secret = encapsulator.encap_secret(public_key)
    
    # 用shared_secret加密AES密鑰 (額外保護)
    aes_key_encrypted = bytes(a ^ b for a, b in zip(aes_key, shared_secret[:32]))
    
    # === 混合加密總計時結束 ===
    total_duration = time.perf_counter() - total_start
    
    # 5. 儲存加密影像 (不計時)
    encrypted_img = Image.frombytes(mode, size, ciphertext)
    encrypted_img.save(encrypted_image_path)
    
    # 6. 儲存封裝的密鑰資訊 (不計時)
    key_package = {
        'encapsulated_key': encapsulated_key,
        'aes_key_encrypted': aes_key_encrypted,
        'iv': iv,
        'tag': tag,
        'mode': mode,
        'size': size,
        'kem_alg': kem_alg
    }
    
    with open(encrypted_key_path, 'wb') as f:
        pickle.dump(key_package, f)
    
   
    print(f"📁 加密影像儲存: {encrypted_image_path}")
    print(f"🔐 密鑰封裝儲存: {encrypted_key_path}")
   # print(f"🕐 混合加密總時間: {total_duration:.4f} 秒")
    
    return kem, total_duration

# === 混合解密：解密端 ===
def hybrid_decrypt(encrypted_image_path, encrypted_key_path, output_image_path, kem_private_key):
    """
    混合解密流程：
    1. 讀取加密影像和封裝的密鑰
    2. 用ML-KEM私鑰解封裝，還原AES密鑰
    3. 用AES密鑰解密影像
    4. 還原原始影像
    """

    
    # 1. 讀取封裝的密鑰資訊 (不計時)
    with open(encrypted_key_path, 'rb') as f:
        key_package = pickle.load(f)
    
    encapsulated_key = key_package['encapsulated_key']
    aes_key_encrypted = key_package['aes_key_encrypted']
    iv = key_package['iv']
    tag = key_package['tag']
    mode = key_package['mode']
    size = key_package['size']
    
    # 2. 讀取加密影像 (不計時)
    encrypted_img = Image.open(encrypted_image_path)
    ciphertext = encrypted_img.tobytes()
    
    # === 混合解密總計時開始 ===
    total_start = time.perf_counter()
    
    # 3. 用ML-KEM私鑰解封裝，還原AES密鑰
    shared_secret = kem_private_key.decap_secret(encapsulated_key)
    aes_key = bytes(a ^ b for a, b in zip(aes_key_encrypted, shared_secret[:32]))
    
    # 4. 用AES密鑰解密影像
    decrypted_data = aes_gcm_decrypt(iv, tag, ciphertext, aes_key)
    
    # === 混合解密總計時結束 ===
    total_duration = time.perf_counter() - total_start
    
    # 5. 還原原始影像 (不計時)
    decrypted_img = Image.frombytes(mode, size, decrypted_data)
    decrypted_img.save(output_image_path)
    
   
    print(f"📁 解密影像儲存: {output_image_path}")
  # print(f"🕐 混合解密總時間: {total_duration:.4f} 秒")
    
    return total_duration

if __name__ == "__main__":
    # 檔案路徑
    original_image = "input.png"
    hybrid_encrypted_image = "hybrid_encrypted.png"
    hybrid_key_package = "hybrid_key.pkl"
    hybrid_decrypted_image = "hybrid_decrypted.png"
    

    
    # === 混合加密測試 ===
    print("\n【混合加密測試】")
    kem_obj, enc_time = hybrid_encrypt(
        original_image, hybrid_encrypted_image, hybrid_key_package
    )
    
    print("\n【混合解密測試】")
    dec_time = hybrid_decrypt(
        hybrid_encrypted_image, hybrid_key_package, hybrid_decrypted_image, kem_obj
    )
    
    # === 驗證結果 ===
    print("\n" + "=" * 50)
    print("🔍 驗證結果")
    
    orig = Image.open(original_image)
    hybrid_dec = Image.open(hybrid_decrypted_image)
    hybrid_correct = (orig.mode == hybrid_dec.mode and 
                     orig.size == hybrid_dec.size and 
                     orig.tobytes() == hybrid_dec.tobytes())
    
    print(f"混合加密解密: {'✅ 正確' if hybrid_correct else '❌ 失敗'}")
    
