import os, sys
sys.path.append("D:/graduation_project/liboqs-python")
import oqs

from PIL import Image
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

# ===== 通用：AES-GCM 加解密 =====
def aes_gcm_encrypt(data: bytes, key: bytes):
    iv = os.urandom(12)
    encryptor = Cipher(algorithms.AES(key), modes.GCM(iv), backend=default_backend()).encryptor()
    ct = encryptor.update(data) + encryptor.finalize()
    return iv, encryptor.tag, ct

def aes_gcm_decrypt(iv: bytes, tag: bytes, ct: bytes, key: bytes):
    decryptor = Cipher(algorithms.AES(key), modes.GCM(iv, tag), backend=default_backend()).decryptor()
    return decryptor.update(ct) + decryptor.finalize()

# ===== 加密：輸出噪聲圖 + 參數檔 =====
def encrypt_image(input_image_path, encrypted_image_path):
    # 1. 讀圖、取原始像素
    img = Image.open(input_image_path)
    mode, size = img.mode, img.size
    raw = img.tobytes()
    print(f"📥 原圖：{input_image_path} → 模式={mode}、尺寸={size}、bytes={len(raw)}")

    # 2. KEM 交換
    alice = oqs.KeyEncapsulation("ML-KEM-1024")
    pub = alice.generate_keypair()
    with oqs.KeyEncapsulation("ML-KEM-1024") as bob:
        kem_ct, shared_bob = bob.encap_secret(pub)
    shared_alice = alice.decap_secret(kem_ct)
    aes_key = shared_alice[:32]

    # 3. AES-GCM 加密 raw pixel
    iv, tag, ct = aes_gcm_encrypt(raw, aes_key)

    # 4. 存噪聲圖
    enc_img = Image.frombytes(mode, size, ct)
    enc_img.save(encrypted_image_path)
    print(f"🖼️ 加密圖檔：{encrypted_image_path}")

    # 5. 把參數寫成二進位檔，方便傳輸
    open("kem_ct.bin", "wb").write(kem_ct)
    open("iv.bin", "wb").write(iv)
    open("tag.bin", "wb").write(tag)
    print("參數檔：kem_ct.bin, iv.bin, tag.bin")

    return mode, size, alice  # alice 含私鑰

# ===== 解密：從噪聲圖 + 參數檔 還原原圖 =====
def decrypt_image(encrypted_image_path, output_image_path, mode, size, alice):
    # 1. 讀噪聲圖當成 ciphertext
    enc_img = Image.open(encrypted_image_path)
    ct = enc_img.tobytes()
    print(f"📥 讀密文圖：{encrypted_image_path} → bytes={len(ct)}")

    # 2. 讀參數檔
    kem_ct = open("kem_ct.bin", "rb").read()
    iv     = open("iv.bin",     "rb").read()
    tag    = open("tag.bin",    "rb").read()

    # 3. KEM 解封裝
    shared = alice.decap_secret(kem_ct)
    aes_key = shared[:32]

    # 4. AES-GCM 解密
    raw = aes_gcm_decrypt(iv, tag, ct, aes_key)

    # 5. 重建並存檔
    dec_img = Image.frombytes(mode, size, raw)
    dec_img.save(output_image_path)
    print(f"✅ 成功還原：{output_image_path}")

if __name__ == "__main__":
    # 加密階段
    mode, size, alice = encrypt_image("input.png", "MAencrypted.png")
    # (你把 MAencrypted.png + kem_ct.bin + iv.bin + tag.bin 傳給對方)
    # 解密階段
    decrypt_image("MAencrypted.png", "MAdecrypted.png", mode, size, alice)
