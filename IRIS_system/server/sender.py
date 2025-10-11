# sender.py (增加傳輸速度計算版)
# 醫療影像傳輸方 - 負責加密和傳送醫療影像

import os, time, json, base64, pickle, math
import numpy as np
from PIL import Image, ImageFilter
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from .simple_kem import SimpleKEM
from .signature_utils import sign_bytes

# AES-GCM加密函數（保持原有加密流程）
def aes_gcm_encrypt(data: bytes, key: bytes):
    """AES-GCM加密"""
    iv = os.urandom(12)
    enc = Cipher(algorithms.AES(key), modes.GCM(iv), backend=default_backend()).encryptor()
    ct = enc.update(data) + enc.finalize()
    return iv, enc.tag, ct

def format_speed(bytes_per_second):
    """格式化傳輸速度"""
    if bytes_per_second >= 1024**3:
        return f"{bytes_per_second / (1024**3):.2f} GB/s"
    elif bytes_per_second >= 1024**2:
        return f"{bytes_per_second / (1024**2):.2f} MB/s"
    elif bytes_per_second >= 1024:
        return f"{bytes_per_second / 1024:.2f} KB/s"
    else:
        return f"{bytes_per_second:.2f} B/s"

def format_size(bytes_size):
    """格式化檔案大小"""
    if bytes_size >= 1024**3:
        return f"{bytes_size / (1024**3):.2f} GB"
    elif bytes_size >= 1024**2:
        return f"{bytes_size / (1024**2):.2f} MB"
    elif bytes_size >= 1024:
        return f"{bytes_size / 1024:.2f} KB"
    else:
        return f"{bytes_size} bytes"

class Sender:
    """醫療影像傳輸方"""

    def __init__(self, sender_id: str = "Medical_Sender"):
        self.sender_id = sender_id

        # 生成RSA金鑰對（用於身份驗證）
        self.private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        self.public_key = self.private_key.public_key()

        # 生成量子安全的KEM金鑰對
        self.kem = SimpleKEM("ML-KEM-1024")
        self.kem_public_key = self.kem.generate_keypair()

        self.certificate = None
        self.ca_public_key = None

        print(f"📤 傳輸方 {sender_id} 已初始化")

    def get_public_key_pem(self) -> bytes:
        """獲取公鑰的PEM格式"""
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

    def register_with_ca(self, ca):
        """向CA註冊並獲取憑證"""
        self.certificate = ca.register_party(
            self.sender_id, 
            self.get_public_key_pem(), 
            self.kem_public_key
        )
        self.ca_public_key = ca.get_ca_public_key_pem()
        print(f"✅ {self.sender_id} 已向CA註冊完成")

    def verify_peer_certificate(self, peer_certificate: dict, ca_public_key_pem: bytes) -> bool:
        """驗證對方的憑證"""
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
                return False

            return True
        except:
            return False

    def encrypt_and_prepare_transmission(self, plaintext_bytes: bytes, 
                                   receiver_certificate: dict, 
                                   signature: bytes, 
                                   app_meta: dict, 
                                   kem_alg: str = "ML-KEM-1024") -> dict:
        """
        使用 plaintext_bytes 加密並打包，加入簽章與應用層元資料。
        """
        # 步驟 1: 驗證接收方憑證的有效性
        if not self.verify_peer_certificate(receiver_certificate, self.ca_public_key_pem):
            raise ValueError("❌ 接收方憑證驗證失敗")
        print("✅ 接收方憑證驗證成功")

        original_size = len(plaintext_bytes)
        print(f"📷 原始資料大小: {original_size} bytes")

        encryption_start = time.perf_counter()

        # 步驟 2: 使用 AES-GCM 加密原始資料
        aes_key = os.urandom(32)  # 每次都生成新的對稱金鑰
        iv = os.urandom(12)      # GCM 建議的 IV 長度
        encryptor = Cipher(algorithms.AES(aes_key), modes.GCM(iv), backend=default_backend()).encryptor()
        ciphertext = encryptor.update(plaintext_bytes) + encryptor.finalize()
        tag = encryptor.tag  # GCM 的認證標籤

        # 步驟 3: 使用 ML-KEM 封裝 AES 金鑰
        # 從接收方憑證中取得其 KEM 公鑰
        receiver_kem_pk_b64 = receiver_certificate['kem_public_key']
        receiver_kem_pk = base64.b64decode(receiver_kem_pk_b64)
        
        kem = SimpleKEM(kem_alg)
        encapsulated_key, _ = kem.encapsecret(receiver_kem_pk)

        # 步驟 4: 構建標準化的傳輸封包
        transmission_package = {
            "enc_data": {
                "ciphertext_b64": base64.b64encode(ciphertext).decode('utf-8'),
                "iv_b64": base64.b64encode(iv).decode('utf-8'),
                "tag_b64": base64.b64encode(tag).decode('utf-8'),
                "kem_alg": kem_alg,
                "aes_key_encapsulated_b64": base64.b64encode(encapsulated_key).decode('utf-8'),
            },
            "signature": {
                "alg": "RSA-PSS-SHA256",
                "signature_b64": base64.b64encode(signature).decode('utf-8'),
            },
            "app_meta": app_meta, # 包含 patient_id, uploader_id 等
            "sender_cert_b64": base64.b64encode(json.dumps(self.certificate).encode('utf-8')).decode('utf-8')
        }
        
        encryption_end = time.perf_counter()
        print(f"🔐 加密與打包耗時: {encryption_end - encryption_start:.4f} 秒")

        return transmission_package
    def save_transmission_package(self, transmission_package: dict, output_path: str):
        """儲存傳輸包到檔案"""
        with open(output_path, 'wb') as f:
            pickle.dump(transmission_package, f, protocol=pickle.HIGHEST_PROTOCOL)
        print(f"💾 傳輸包已儲存: {output_path}")

# LSB隱寫術相關函數（保持原有LSB流程）
def _ensure_mode_for_channels(img, channels: str):
    need = "RGB" if "A" not in channels else "RGBA"
    if img.mode != need:
        img = img.convert(need)
    return img

def _bytes_to_symbols(data: bytes, bpc: int):
    bits = np.unpackbits(np.frombuffer(data, dtype=np.uint8))
    pad = (-len(bits)) % bpc
    if pad:
        bits = np.concatenate([bits, np.zeros(pad, dtype=np.uint8)])
    bits = bits.reshape(-1, bpc)
    weights = (1 << np.arange(bpc)[::-1]).astype(np.uint8)
    return (bits * weights).sum(axis=1).astype(np.uint8)

def lsb_embed_transmission_package(cover_path: str, stego_path: str, 
                                 transmission_package: dict,
                                 channels: str = "RGB", bpc: int = 1):
    """將傳輸包嵌入LSB（保持原有LSB流程）"""
    payload = pickle.dumps(transmission_package, protocol=pickle.HIGHEST_PROTOCOL)

    header = len(payload).to_bytes(8, "big")
    data = header + payload

    img = Image.open(cover_path)
    img = _ensure_mode_for_channels(img, channels)
    arr = np.array(img, dtype=np.uint8)

    h, w = arr.shape[0], arr.shape[1]

    ch_idx = {"R":0, "G":1, "B":2, "A":3}
    idxs = [ch_idx[ch] for ch in channels]
    flat = arr[:, :, idxs].reshape(-1)

    cap_bits = len(flat) * bpc
    need_bits = len(data) * 8
    if need_bits > cap_bits:
        raise ValueError(f"容量不足：需 {len(data)} bytes，但可用 {cap_bits//8} bytes")

    symbols = _bytes_to_symbols(data, bpc)
    mask = 0xFF ^ ((1 << bpc) - 1)
    flat[:len(symbols)] = (flat[:len(symbols)] & mask) | symbols

    arr[:, :, idxs] = flat.reshape(h, w, len(idxs))
    out = Image.fromarray(arr, mode=img.mode)
    out.save(stego_path)

    print(f"🖼️ 傳輸包已嵌入隱寫影像: {stego_path}")

# FBM紋理生成（保持原有紋理生成功能）
def _gen_fbm_texture(width: int, height: int, octaves: int = 5,
                     persistence: float = 0.55, lacunarity: float = 2.0, seed: int | None = None):
    def one_channel(rng):
        acc = np.zeros((height, width), dtype=np.float32)
        amp, tot = 1.0, 0.0
        for k in range(octaves):
            gw = max(2, int(width / (lacunarity ** k)))
            gh = max(2, int(height / (lacunarity ** k)))
            grid = rng.random((gh, gw), dtype=np.float32)
            ch = Image.fromarray((grid * 255).astype(np.uint8), mode="L").resize(
                (width, height), resample=Image.BICUBIC
            )
            acc += (np.asarray(ch, dtype=np.float32) / 255.0) * amp
            tot += amp
            amp *= persistence
        acc = np.clip(acc / max(tot, 1e-6), 0.0, 1.0)
        return (acc * 255.0).astype(np.uint8)

    rng_r = np.random.default_rng(seed)
    rng_g = np.random.default_rng(None if seed is None else seed + 101)
    rng_b = np.random.default_rng(None if seed is None else seed + 211)

    r, g, b = one_channel(rng_r), one_channel(rng_g), one_channel(rng_b)
    img = np.stack([r, g, b], axis=-1)
    pil = Image.fromarray(img, mode="RGB").filter(ImageFilter.GaussianBlur(radius=0.4))
    pil = pil.filter(ImageFilter.UnsharpMask(radius=1.2, percent=80, threshold=3))
    return np.asarray(pil, dtype=np.uint8)

def generate_cover_for_transmission(cover_path: str, transmission_package: dict,
                                  channels: str = "RGB", bpc: int = 1,
                                  safety: float = 1.25, min_side: int = 512,
                                  aspect: float = 1.0, seed: int | None = None):
    """自動產生適合的載體影像"""
    payload_size = len(pickle.dumps(transmission_package, protocol=pickle.HIGHEST_PROTOCOL))

    cap_bits_per_pixel = len(channels) * bpc
    pixels_needed = math.ceil((payload_size * 8 * safety) / max(cap_bits_per_pixel, 1e-6))
    side = max(int(math.ceil(math.sqrt(pixels_needed))), min_side)

    w = int(round(side * math.sqrt(aspect)))
    h = max(1, int(round(side / max(math.sqrt(aspect), 1e-6))))

    tex = _gen_fbm_texture(w, h, seed=seed)
    Image.fromarray(tex, mode="RGB").save(cover_path)

    approx_bytes = (w*h*cap_bits_per_pixel)//8
    print(f"🧵 自動產生cover: {cover_path}（{w}×{h}，估可藏≈{format_size(int(approx_bytes))}）")

if __name__ == "__main__":
    sender = Sender("Test_Hospital_A")
    print("\n✅ 傳輸方模組測試完成")
