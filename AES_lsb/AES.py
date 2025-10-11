from PIL import Image
import os
import time
import pickle
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

# === AES-GCM 加解密 ===
def aes_gcm_encrypt(data: bytes, key: bytes):
    iv = os.urandom(12)
    encryptor = Cipher(
        algorithms.AES(key),
        modes.GCM(iv),
        backend=default_backend()
    ).encryptor()
    ciphertext = encryptor.update(data) + encryptor.finalize()
    return iv, encryptor.tag, ciphertext

def aes_gcm_decrypt(iv: bytes, tag: bytes, ciphertext: bytes, key: bytes):
    decryptor = Cipher(
        algorithms.AES(key),
        modes.GCM(iv, tag),
        backend=default_backend()
    ).decryptor()
    data = decryptor.update(ciphertext) + decryptor.finalize()
    return data

# === 純AES加密：加密端 ===
def aes_encrypt(input_image_path, encrypted_image_path, key_path):
    """
    純AES加密流程：
    1. 讀取影像
    2. 生成隨機AES密鑰
    3. 用AES加密影像
    4. 儲存加密影像和密鑰
    """

    
    # 1. 讀取影像 (不計時)
    img = Image.open(input_image_path)
    mode, size = img.mode, img.size
    raw_data = img.tobytes()
    print(f"📷 圖像模式={mode}, 尺寸={size}, 數據量={len(raw_data)} bytes")
    
    # === 純AES加密總計時開始 ===
    total_start = time.perf_counter()
    
    # 2. 生成隨機AES密鑰
    key = os.urandom(32)  # AES-256密鑰
    
    # 3. 用AES加密影像
    iv, tag, ciphertext = aes_gcm_encrypt(raw_data, key)
    
    # === 純AES加密總計時結束 ===
    total_duration = time.perf_counter() - total_start
    
    # 4. 儲存加密影像 (不計時)
    encrypted_img = Image.frombytes(mode, size, ciphertext)
    encrypted_img.save(encrypted_image_path)
    
    # 5. 儲存密鑰資訊 (不計時)
    key_info = {
        'key': key,
        'iv': iv,
        'tag': tag,
        'mode': mode,
        'size': size
    }
    
    with open(key_path, 'wb') as f:
        pickle.dump(key_info, f)
    
    print(f"📁 加密影像儲存: {encrypted_image_path}")
    print(f"🔐 密鑰資訊儲存: {key_path}")
   # print(f"🕐 純AES加密總時間: {total_duration:.4f} 秒")
    
    return key_info, total_duration

# === 純AES解密：解密端 ===
def aes_decrypt(encrypted_image_path, key_path, output_image_path):
    """
    純AES解密流程：
    1. 讀取加密影像和密鑰
    2. 用AES密鑰解密影像
    3. 還原原始影像
    """

    # 1. 讀取密鑰資訊 (不計時)
    with open(key_path, 'rb') as f:
        key_info = pickle.load(f)
    
    key = key_info['key']
    iv = key_info['iv']
    tag = key_info['tag']
    mode = key_info['mode']
    size = key_info['size']
    
    # 2. 讀取加密影像 (不計時)
    encrypted_img = Image.open(encrypted_image_path)
    ciphertext = encrypted_img.tobytes()
    
    # === 純AES解密總計時開始 ===
    total_start = time.perf_counter()
    
    # 3. 用AES密鑰解密影像
    decrypted_data = aes_gcm_decrypt(iv, tag, ciphertext, key)
    
    # === 純AES解密總計時結束 ===
    total_duration = time.perf_counter() - total_start
    
    # 4. 還原原始影像 (不計時)
    decrypted_img = Image.frombytes(mode, size, decrypted_data)
    decrypted_img.save(output_image_path)
    

    print(f"📁 解密影像儲存: {output_image_path}")
    #print(f"🕐 純AES解密總時間: {total_duration:.4f} 秒")
    
    return total_duration

if __name__ == "__main__":
    # 檔案路徑
    original_image = "input.png"
    aes_encrypted_image = "aes_encrypted.png"
    aes_key_file = "aes_key.pkl"
    aes_decrypted_image = "aes_decrypted.png"
    

    # === 純AES加密測試 ===
    print("\n【純AES加密測試】")
    key_info, enc_time = aes_encrypt(
        original_image, aes_encrypted_image, aes_key_file
    )
    
    print("\n【純AES解密測試】")
    dec_time = aes_decrypt(
        aes_encrypted_image, aes_key_file, aes_decrypted_image
    )
    
    # === 驗證結果 ===
    print("\n" + "=" * 50)
    print("🔍 驗證結果")
    
    orig = Image.open(original_image)
    aes_dec = Image.open(aes_decrypted_image)
    aes_correct = (orig.mode == aes_dec.mode and 
                   orig.size == aes_dec.size and 
                   orig.tobytes() == aes_dec.tobytes())
    
    print(f"純AES加密解密: {'✅ 正確' if aes_correct else '❌ 失敗'}")
    
    # === 性能總結 ===
    print("\n" + "=" * 50)
    print("📊 純AES加密性能")
    print(f"🔐 純AES加密時間: {enc_time:.4f} 秒")
    print(f"🔓 純AES解密時間: {dec_time:.4f} 秒")
    print(f"🔄 總處理時間: {enc_time + dec_time:.4f} 秒")