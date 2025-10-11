from PIL import Image
import numpy as np
import os
import time
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

# AES-GCM 加密
def aes_gcm_encrypt(data: bytes, key: bytes):
    iv = os.urandom(12)
    encryptor = Cipher(
        algorithms.AES(key),
        modes.GCM(iv),
        backend=default_backend()
    ).encryptor()
    ciphertext = encryptor.update(data) + encryptor.finalize()
    return iv, encryptor.tag, ciphertext

# AES-GCM 解密
def aes_gcm_decrypt(iv: bytes, tag: bytes, ciphertext: bytes, key: bytes):
    decryptor = Cipher(
        algorithms.AES(key),
        modes.GCM(iv, tag),
        backend=default_backend()
    ).decryptor()
    return decryptor.update(ciphertext) + decryptor.finalize()

# bytes → bits
def bytes_to_bits(data: bytes):
    return ''.join(format(b, '08b') for b in data)

# bits → bytes
def bits_to_bytes(bits: str):
    return bytes(int(bits[i:i+8], 2) for i in range(0, len(bits), 8))
'''
# 將 data 藏入 image 的 LSB
def lsb_embed_to_image(image_path, data: bytes, output_path):
    img = Image.open(image_path).convert("RGB")
    pixels = np.array(img)
    flat_pixels = pixels.flatten()

    bitstring = bytes_to_bits(data)
    if len(bitstring) > len(flat_pixels):
        raise ValueError("❌ 資料太大無法藏入這張圖片")

    for i in range(len(bitstring)):
        flat_pixels[i] = (flat_pixels[i] & 0xFE) | int(bitstring[i])

    new_pixels = flat_pixels.reshape(pixels.shape)
    stego_img = Image.fromarray(new_pixels)
    stego_img.save(output_path)
    print(f"✅ 已將金鑰資訊藏入 {output_path}")

# 從圖片提取 LSB 資料
def lsb_extract_from_image(image_path, num_bytes: int):
    img = Image.open(image_path).convert("RGB")
    pixels = np.array(img).flatten()

    bits = [str(pixels[i] & 1) for i in range(num_bytes * 8)]
    return bits_to_bytes(''.join(bits))
'''
# 加密圖片像素
def encrypt_image_pixels(input_path, output_path, key):
    img = Image.open(input_path).convert("RGB")
    data = np.array(img)
    h, w, c = data.shape
    flat_data = data.tobytes()

    start_time = time.time()  # 開始計時
    iv, tag, ciphertext = aes_gcm_encrypt(flat_data, key)
    end_time = time.time()  # 結束計時

    encrypted_array = np.frombuffer(ciphertext[:h * w * c], dtype=np.uint8).reshape((h, w, c))
    encrypted_img = Image.fromarray(encrypted_array)
    encrypted_img.save(output_path)

    print(f"✅ 圖片像素加密完成，花費時間: {end_time - start_time:.6f} 秒")

    return iv, tag, data.shape

# 解密圖片像素
def decrypt_image_pixels(image_path, output_path, key, iv, tag, shape):
    img = Image.open(image_path).convert("RGB")
    data = np.array(img).tobytes()

    decrypted = aes_gcm_decrypt(iv, tag, data, key)
    decrypted_array = np.frombuffer(decrypted, dtype=np.uint8).reshape(shape)
    Image.fromarray(decrypted_array).save(output_path)
    print(f"✅ 已解密還原圖片為 {output_path}")

# 主流程
if __name__ == "__main__":
    input_image = "input.png"         # 原圖
    encrypted_image = "AES_encrypted.png" # 亂碼圖
    stego_image = "stego.png"         # 藏入資訊的亂碼圖
    decrypted_image = "decrypted.png" # 還原圖

    key = os.urandom(32)  # AES-256 金鑰

    # 加密圖片
    iv, tag, shape = encrypt_image_pixels(input_image, encrypted_image, key)

    # 合併 key + iv + tag 並藏入 encrypted.png → stego.png
    secret = key + iv + tag  # 32 + 12 + 16 = 60 bytes

    start_embed_time = time.time()
    #lsb_embed_to_image(encrypted_image, secret, stego_image)
    #end_embed_time = time.time()
    #rint(f"✅ LSB 藏入資訊完成，花費時間: {end_embed_time - start_embed_time:.6f} 秒")

    # 從 stego.png 提取 key、iv、tag
    #recovered = lsb_extract_from_image(stego_image, 60)
    #key2, iv2, tag2 = recovered[:32], recovered[32:44], recovered[44:]

    # 解密 stego.png 成原圖
    #decrypt_image_pixels(encrypted_image, decrypted_image, key2, iv2, tag2, shape)
