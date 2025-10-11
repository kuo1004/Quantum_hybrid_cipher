# hybrid_lsb_kem.py
import os, time, math, pickle, base64
import numpy as np
from PIL import Image, ImageFilter
import oqs
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

# ========== AES-GCM ==========
def aes_gcm_encrypt(data: bytes, key: bytes):
    iv = os.urandom(12)
    enc = Cipher(algorithms.AES(key), modes.GCM(iv), backend=default_backend()).encryptor()
    ct = enc.update(data) + enc.finalize()
    return iv, enc.tag, ct

def aes_gcm_decrypt(iv: bytes, tag: bytes, ct: bytes, key: bytes):
    dec = Cipher(algorithms.AES(key), modes.GCM(iv, tag), backend=default_backend()).decryptor()
    return dec.update(ct) + dec.finalize()

# ========== 混合加密（檔案版，保留） ==========
def hybrid_encrypt(input_image_path, encrypted_image_path, encrypted_key_path, kem_alg="ML-KEM-1024"):
    img = Image.open(input_image_path)
    mode, size = img.mode, img.size
    raw = img.tobytes()
    print(f"📷 圖像模式={mode}, 尺寸={size}, bytes={len(raw)}")

    t0 = time.perf_counter()
    aes_key = os.urandom(32)
    iv, tag, ciphertext = aes_gcm_encrypt(raw, aes_key)

    kem = oqs.KeyEncapsulation(kem_alg)
    pk = kem.generate_keypair()
    with oqs.KeyEncapsulation(kem_alg) as encap:
        encapsulated_key, shared = encap.encap_secret(pk)
    aes_key_encrypted = bytes(a ^ b for a, b in zip(aes_key, shared[:32]))
    t1 = time.perf_counter()

    Image.frombytes(mode, size, ciphertext).save(encrypted_image_path)
    with open(encrypted_key_path, "wb") as f:
        pickle.dump({
            "encapsulated_key": encapsulated_key,
            "aes_key_encrypted": aes_key_encrypted,
            "iv": iv, "tag": tag,
            "mode": mode, "size": size,
            "kem_alg": kem_alg
        }, f, protocol=pickle.HIGHEST_PROTOCOL)

    print(f"📁 加密影像: {encrypted_image_path}")
    print(f"🔐 金鑰封裝: {encrypted_key_path}")
    print(f"🕐 混合加密耗時: {t1 - t0:.4f}s")
    return kem, (t1 - t0)

def hybrid_decrypt(encrypted_image_path, encrypted_key_path, output_image_path, kem_priv):
    with open(encrypted_key_path, "rb") as f:
        kp = pickle.load(f)
    iv, tag = kp["iv"], kp["tag"]
    mode, size = kp["mode"], kp["size"]
    encapsulated_key, aes_key_enc = kp["encapsulated_key"], kp["aes_key_encrypted"]

    ct = Image.open(encrypted_image_path).tobytes()
    t0 = time.perf_counter()
    shared = kem_priv.decap_secret(encapsulated_key)
    aes_key = bytes(a ^ b for a, b in zip(aes_key_enc, shared[:32]))
    pt = aes_gcm_decrypt(iv, tag, ct, aes_key)
    t1 = time.perf_counter()

    Image.frombytes(mode, size, pt).save(output_image_path)
    print(f"📁 解密影像: {output_image_path}")
    print(f"🕐 混合解密耗時: {t1 - t0:.4f}s")
    return (t1 - t0)

# ========== 純 LSB 工具（PNG/BMP 無損格式） ==========
# 參數：channels 可選 "R" / "G" / "B" / "RGB" / "RGBA"，bpc=1~2 建議
def _ensure_mode_for_channels(img: Image.Image, channels: str) -> Image.Image:
    need = "RGB" if "A" not in channels else "RGBA"
    if img.mode != need:
        img = img.convert(need)
    return img

def lsb_capacity_bytes(image_path: str, channels: str = "RGB", bpc: int = 1, header_bytes: int = 8) -> int:
    w, h = Image.open(image_path).size
    c = len(channels)
    cap_bits = w * h * c * bpc
    return max(cap_bits // 8 - header_bytes, 0)

def _bytes_to_symbols(data: bytes, bpc: int) -> np.ndarray:
    bits = np.unpackbits(np.frombuffer(data, dtype=np.uint8))
    pad = (-len(bits)) % bpc
    if pad:
        bits = np.concatenate([bits, np.zeros(pad, dtype=np.uint8)])
    bits = bits.reshape(-1, bpc)
    # 將每組 bpc bits 轉成 0..(2^bpc-1)
    weights = (1 << np.arange(bpc)[::-1]).astype(np.uint8)
    return (bits * weights).sum(axis=1).astype(np.uint8)

def _symbols_to_bytes(symbols: np.ndarray, bpc: int, out_len: int) -> bytes:
    weights = (1 << np.arange(bpc)[::-1]).astype(np.uint8)
    bits = ((symbols[:, None] & weights) > 0).astype(np.uint8)
    bits = bits.reshape(-1)
    cut = (len(bits) // 8) * 8
    by = np.packbits(bits[:cut]).tobytes()
    return by[:out_len]

def lsb_embed_bytes(cover_path: str, stego_path: str, payload: bytes,
                    channels: str = "RGB", bpc: int = 1):
    assert bpc in (1, 2, 3, 4), "bpc 建議 1 或 2"
    header = len(payload).to_bytes(8, "big")  # 8 bytes 長度
    data = header + payload

    img = Image.open(cover_path)
    img = _ensure_mode_for_channels(img, channels)
    arr = np.array(img, dtype=np.uint8)
    h, w = arr.shape[0], arr.shape[1]

    # 展平成選定 channel 的 1D 陣列
    ch_idx = {"R":0, "G":1, "B":2, "A":3}
    idxs = [ch_idx[ch] for ch in channels]
    flat = arr[:, :, idxs].reshape(-1)

    # 容量檢查
    cap_bits = len(flat) * bpc
    need_bits = len(data) * 8
    if need_bits > cap_bits:
        need_bytes = len(data)
        raise ValueError(f"容量不足：需 {need_bytes} bytes，但可用 {cap_bits//8} bytes（試著提高影像尺寸、channels 或 bpc）")

    symbols = _bytes_to_symbols(data, bpc)
    mask = 0xFF ^ ((1 << bpc) - 1)
    flat[:len(symbols)] = (flat[:len(symbols)] & mask) | symbols

    # 回寫並輸出 PNG（或 BMP）
    arr[:, :, idxs] = flat.reshape(h, w, len(idxs))
    out = Image.fromarray(arr, mode=img.mode)
    out.save(stego_path)  # 建議用 PNG/BMP
    print(f"🖼️ 已輸出隱寫影像: {stego_path}")

def lsb_extract_bytes(stego_path: str, channels: str = "RGB", bpc: int = 1) -> bytes:
    img = Image.open(stego_path)
    img = _ensure_mode_for_channels(img, channels)
    arr = np.array(img, dtype=np.uint8)
    ch_idx = {"R":0, "G":1, "B":2, "A":3}
    idxs = [ch_idx[ch] for ch in channels]
    flat = arr[:, :, idxs].reshape(-1)

    # 先讀 8 bytes 長度
    n_symbols_for_len = (8 * 8 + bpc - 1) // bpc
    mask = (1 << bpc) - 1
    len_symbols = flat[:n_symbols_for_len] & mask
    header = _symbols_to_bytes(len_symbols, bpc, 8)
    L = int.from_bytes(header, "big")
    # 再讀 payload
    n_symbols_for_payload = (L * 8 + bpc - 1) // bpc
    symbols = flat[n_symbols_for_len : n_symbols_for_len + n_symbols_for_payload] & mask
    payload = _symbols_to_bytes(symbols, bpc, L)
    return payload

# ========== 自動產生 cover（高紋理 FBM） ==========
def _gen_fbm_texture(width: int, height: int, octaves: int = 5,
                     persistence: float = 0.55, lacunarity: float = 2.0, seed: int | None = None):
    def one_channel(rng):
        acc = np.zeros((height, width), dtype=np.float32)
        amp, tot = 1.0, 0.0
        for k in range(octaves):
            gw = max(2, int(width  / (lacunarity ** k)))
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

def estimate_bpp(channels: str = "RGB", bpc: int = 1) -> float:
    return len(channels) * bpc  # 每像素可藏的 bits（理論值）

def generate_cover_for_payload(cover_path: str, needed_bytes_b64: int,
                               channels: str = "RGB", bpc: int = 1,
                               safety: float = 1.25, min_side: int = 512,
                               aspect: float = 1.0, seed: int | None = None):
    # Base64 長度 ≈ 需 bits；粗估容量
    cap_bits_per_pixel = estimate_bpp(channels, bpc)
    pixels_needed = math.ceil((needed_bytes_b64 * 8 * safety) / max(cap_bits_per_pixel, 1e-6))
    side = max(int(math.ceil(math.sqrt(pixels_needed))), min_side)
    w = int(round(side * math.sqrt(aspect)))
    h = max(1, int(round(side / max(math.sqrt(aspect), 1e-6))))

    tex = _gen_fbm_texture(w, h, seed=seed)
    Image.fromarray(tex, mode="RGB").save(cover_path)
    approx_bytes = (w*h*cap_bits_per_pixel)//8
    print(f"🧵 自動產生 cover: {cover_path}（{w}×{h}，估可藏≈{int(approx_bytes)} bytes；channels={channels}, bpc={bpc}）")

# ========== Payload 打包/解包 ==========
def _pack_payload(ciphertext: bytes, kp: dict) -> bytes:
    blob = {
        "ciphertext": ciphertext,
        "iv": kp["iv"], "tag": kp["tag"],
        "mode": kp["mode"], "size": kp["size"],
        "kem_alg": kp["kem_alg"],
        "encapsulated_key": kp["encapsulated_key"],
        "aes_key_encrypted": kp["aes_key_encrypted"],
        "v": 1,
    }
    return pickle.dumps(blob, protocol=pickle.HIGHEST_PROTOCOL)

def _unpack_payload(bb: bytes):
    return pickle.loads(bb)

# ======== Debug utilities (NEW) ========
def _print_key_debug(title: str, b: bytes, show_b64: bool = True, preview_bytes: int = 64):
    print(f"{title}: {len(b)} bytes")
    hx = b[:preview_bytes].hex()
    if len(b) > preview_bytes:
        hx += f"... (+{len(b) - preview_bytes} bytes)"
    print(f"  hex: {hx}")
    if show_b64:
        b64 = base64.b64encode(b).decode()
        if len(b64) > 120:
            b64 = b64[:120] + "..."
        print(f"  b64: {b64}")

def debug_print_keys_from_stego(stego_path: str, channels: str = "RGB", bpc: int = 1):
    """直接從 stego 圖片抽出 payload，印出 encapsulated_key 與 aes_key_encrypted。"""
    payload = lsb_extract_bytes(stego_path, channels=channels, bpc=bpc)
    blob = _unpack_payload(payload)
    print(f"\n🔎 Extracted keys from stego (alg={blob.get('kem_alg','?')})")
    _print_key_debug("📦 encapsulated_key", blob["encapsulated_key"])
    _print_key_debug("🧩 aes_key_encrypted", blob["aes_key_encrypted"])

# ========== 混合加密 + LSB 內嵌 ==========
def hybrid_encrypt_and_embed_lsb(input_image_path: str,
                                 cover_image_path: str,
                                 stego_image_path: str,
                                 kem_alg: str = "ML-KEM-1024",
                                 channels: str = "RGB",
                                 bpc: int = 1,
                                 debug_keys: bool = True):  # NEW
    img = Image.open(input_image_path)
    mode, size = img.mode, img.size
    raw = img.tobytes()
    print(f"📷 圖像模式={mode}, 尺寸={size}, bytes={len(raw)}")

    t0 = time.perf_counter()
    aes_key = os.urandom(32)
    iv, tag, ct = aes_gcm_encrypt(raw, aes_key)

    kem = oqs.KeyEncapsulation(kem_alg)
    pk = kem.generate_keypair()
    with oqs.KeyEncapsulation(kem_alg) as encap:
        encapsulated_key, shared = encap.encap_secret(pk)
    aes_key_encrypted = bytes(a ^ b for a, b in zip(aes_key, shared[:32]))

    # --- NEW: 在真正寫入 LSB 前把 key 打印出來做記錄 ---
    if debug_keys:
        print("\n🔑 Keys to be embedded via LSB")
        _print_key_debug("🔐 AES session key", aes_key, show_b64=False)
        _print_key_debug("📦 encapsulated_key", encapsulated_key)
        _print_key_debug("🧩 aes_key_encrypted", aes_key_encrypted)

    kp = {
        "encapsulated_key": encapsulated_key,
        "aes_key_encrypted": aes_key_encrypted,
        "iv": iv, "tag": tag,
        "mode": mode, "size": size,
        "kem_alg": kem_alg
    }
    payload = _pack_payload(ct, kp)

    # 內嵌（可先檢查容量）
    cap = lsb_capacity_bytes(cover_image_path, channels=channels, bpc=bpc, header_bytes=8)
    need = len(payload)
    print(f"\n🧮 LSB 容量檢查：可用≈{cap} bytes，需要≈{need} bytes")
    lsb_embed_bytes(cover_image_path, stego_image_path, payload, channels=channels, bpc=bpc)

    t1 = time.perf_counter()
    print(f"🕐 加密+LSB 內嵌耗時: {t1 - t0:.4f}s")

    # --- NEW: 立刻從 stego 回讀一次 key，確認一致 ---
    if debug_keys:
        debug_print_keys_from_stego(stego_image_path, channels=channels, bpc=bpc)

    return kem

def hybrid_extract_and_decrypt_from_lsb(stego_image_path: str,
                                        output_image_path: str,
                                        kem_priv,
                                        channels: str = "RGB",
                                        bpc: int = 1):
    t0 = time.perf_counter()
    payload = lsb_extract_bytes(stego_image_path, channels=channels, bpc=bpc)
    blob = _unpack_payload(payload)

    ct = blob["ciphertext"]
    iv, tag = blob["iv"], blob["tag"]
    mode, size = blob["mode"], tuple(blob["size"])
    encapsulated_key = blob["encapsulated_key"]
    aes_key_encrypted = blob["aes_key_encrypted"]

    shared = kem_priv.decap_secret(encapsulated_key)
    aes_key = bytes(a ^ b for a, b in zip(aes_key_encrypted, shared[:32]))
    pt = aes_gcm_decrypt(iv, tag, ct, aes_key)
    Image.frombytes(mode, size, pt).save(output_image_path)

    t1 = time.perf_counter()
    print(f"📁 解密影像: {output_image_path}")
    print(f"🕐 取出+解密耗時: {t1 - t0:.4f}s")

# ========== Demo ==========
if __name__ == "__main__":
    # 檔案版（與你原流程一致）
    original = "input.png"
    enc_img, key_pkl, dec_img = "hybrid_encrypted.png", "hybrid_key.pkl", "hybrid_decrypted.png"
    print("\n【混合加密 測試（檔案版）】")
    kem_obj, _ = hybrid_encrypt(original, enc_img, key_pkl)
    _ = hybrid_decrypt(enc_img, key_pkl, dec_img, kem_obj)
    ok = (Image.open(original).tobytes() == Image.open(dec_img).tobytes())
    print("🔍 驗證（檔案版）:", "✅ 正確" if ok else "❌ 失敗")

    # LSB 版（手動 cover）
    cover = "cover.png"       # 建議 RGB/PNG，尺寸與紋理越高越好
    stego = "stego_lsb.png"
    if os.path.exists(cover):
        print("\n【混合加密 + LSB（手動 cover）】")
        kem2 = hybrid_encrypt_and_embed_lsb(
            original, cover, stego, kem_alg="ML-KEM-1024",
            channels="RGB", bpc=1, debug_keys=True
        )
        out1 = "stego_lsb_decrypted.png"
        hybrid_extract_and_decrypt_from_lsb(stego, out1, kem2, channels="RGB", bpc=1)
        ok2 = (Image.open(original).tobytes() == Image.open(out1).tobytes())
        print("🔍 驗證（LSB 手動 cover）:", "✅ 正確" if ok2 else "❌ 失敗")

        # 若需要手動再印一次（函式內已自動印過，這行可保留為註解）
        # debug_print_keys_from_stego(stego, channels="RGB", bpc=1)
    else:
        print("\n⚠️ 找不到 cover.png，改用自動產生 cover 的示範")

    # LSB 版（自動 cover）
    print("\n【混合加密 + LSB（自動 cover）】")
    stego_auto = "stego_lsb_auto.png"
    # 先產 payload 大小，估需求 → 自動產生 cover
    img = Image.open(original); raw = img.tobytes()
    aes_key = os.urandom(32); iv, tag, ct = aes_gcm_encrypt(raw, aes_key)
    kem = oqs.KeyEncapsulation("ML-KEM-1024"); pk = kem.generate_keypair()
    with oqs.KeyEncapsulation("ML-KEM-1024") as encap:
        encapsulated_key, shared = encap.encap_secret(pk)
    kp = {"encapsulated_key": encapsulated_key, "aes_key_encrypted": bytes(a ^ b for a,b in zip(aes_key, shared[:32])),
          "iv": iv, "tag": tag, "mode": img.mode, "size": img.size, "kem_alg": "ML-KEM-1024"}
    payload = _pack_payload(ct, kp)
    b64_len = len(base64.b64encode(payload))

    auto_cover = "auto_cover.png"
    generate_cover_for_payload(auto_cover, b64_len, channels="RGB", bpc=1,
                               safety=1.3, min_side=1024, aspect=1.0, seed=42)

    kem3 = hybrid_encrypt_and_embed_lsb(original, auto_cover, stego_auto,
                                        kem_alg="ML-KEM-1024", channels="RGB", bpc=1, debug_keys=True)
    out2 = "stego_lsb_auto_decrypted.png"
    hybrid_extract_and_decrypt_from_lsb(stego_auto, out2, kem3, channels="RGB", bpc=1)
    ok3 = (Image.open(original).tobytes() == Image.open(out2).tobytes())
    print("🔍 驗證（LSB 自動 cover）:", "✅ 正確" if ok3 else "❌ 失敗")

    # 若需要手動再印一次（函式內已自動印過，這行可保留為註解）
    # debug_print_keys_from_stego(stego_auto, channels="RGB", bpc=1)
