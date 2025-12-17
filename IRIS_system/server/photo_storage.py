#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
photo_storage.py - 加密/解密照片與影片儲存模組

功能：
1. 管理 encryption_photo 和 decryption_photo 資料夾
2. 將加密資料嵌入 LSB 隱寫圖片（可預覽）
3. 將加密資料生成 H.264 載體影片（可播放）
4. 儲存解密後的原始檔案
5. 程式結束時自動清理

加密檔案會生成：
- 圖片：一張「看起來正常的圖片」，但裡面藏有密文資料（LSB 隱寫）
- 影片：一個「可播放的載體影片」（H.264 testsrc）
"""

import os
import math
import atexit
import signal
import shutil
import subprocess
import numpy as np
from datetime import datetime
from typing import Optional, Tuple
from PIL import Image, ImageFilter


class PhotoStorageManager:
    """加密/解密照片與影片儲存管理器"""
    
    # 影片相關常數
    CARRIER_DURATION_SEC = 3  # 載體影片時長（秒）
    CARRIER_RESOLUTION = "320x240"  # 載體影片解析度
    CARRIER_FPS = 10  # 載體影片幀率
    
    def __init__(self, 
                 encryption_dir: str = "encryption_photo",
                 decryption_dir: str = "decryption_photo",
                 auto_cleanup: bool = True):
        """
        初始化照片儲存管理器
        
        Args:
            encryption_dir: 加密照片儲存目錄（LSB 隱寫圖 / 載體影片）
            decryption_dir: 解密照片儲存目錄
            auto_cleanup: 是否在程式結束時自動清理
        """
        self.encryption_dir = encryption_dir
        self.decryption_dir = decryption_dir
        self.auto_cleanup = auto_cleanup
        
        # FFmpeg 路徑
        self.ffmpeg = os.environ.get("FFMPEG_BIN") or shutil.which("ffmpeg") or "ffmpeg"
        self.ffprobe = os.environ.get("FFPROBE_BIN") or shutil.which("ffprobe") or "ffprobe"
        
        # 創建資料夾
        self._init_directories()
        
        # 註冊自動清理
        if auto_cleanup:
            atexit.register(self.cleanup)
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _init_directories(self):
        """初始化資料夾"""
        for dir_path in [self.encryption_dir, self.decryption_dir]:
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)
                print(f"📁 已創建資料夾: {dir_path}")
            else:
                print(f"📁 資料夾已存在: {dir_path}")
    
    def _signal_handler(self, signum, frame):
        """處理中斷信號"""
        print(f"\n⚠️ 收到信號 {signum}，正在清理...")
        self.cleanup()
        exit(0)
    
    def _generate_filename(self, original_filename: str, suffix: str, ext: str = None) -> str:
        """生成帶時間戳的檔案名稱"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        name, original_ext = os.path.splitext(original_filename)
        
        if ext is None:
            ext = original_ext
        
        return f"{timestamp}_{name}_{suffix}{ext}"
    
    def _has_ffmpeg(self) -> bool:
        """檢查是否有 FFmpeg"""
        try:
            result = subprocess.run(
                [self.ffmpeg, "-version"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False
    
    # ============================================================
    # LSB 隱寫相關函數（圖片）
    # ============================================================
    
    def _gen_fbm_texture(self, width: int, height: int, octaves: int = 5,
                         persistence: float = 0.55, lacunarity: float = 2.0, 
                         seed: int = None) -> np.ndarray:
        """生成 FBM 紋理作為載體圖片"""
        if seed is None:
            seed = int(datetime.now().timestamp() * 1000) % (2**31)
        
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
        rng_g = np.random.default_rng(seed + 101)
        rng_b = np.random.default_rng(seed + 211)
        r, g, b = one_channel(rng_r), one_channel(rng_g), one_channel(rng_b)
        
        img = np.stack([r, g, b], axis=-1)
        pil = Image.fromarray(img, mode="RGB").filter(ImageFilter.GaussianBlur(radius=0.4))
        pil = pil.filter(ImageFilter.UnsharpMask(radius=1.2, percent=80, threshold=3))
        return np.asarray(pil, dtype=np.uint8)
    
    def _bytes_to_symbols(self, data: bytes, bpc: int) -> np.ndarray:
        """將 bytes 轉換為 LSB 符號"""
        bits = np.unpackbits(np.frombuffer(data, dtype=np.uint8))
        pad = (-len(bits)) % bpc
        if pad:
            bits = np.concatenate([bits, np.zeros(pad, dtype=np.uint8)])
        bits = bits.reshape(-1, bpc)
        weights = (1 << np.arange(bpc)[::-1]).astype(np.uint8)
        return (bits * weights).sum(axis=1).astype(np.uint8)
    
    def _create_stego_image(self, ciphertext: bytes, channels: str = "RGB", 
                            bpc: int = 1, safety: float = 1.25, 
                            min_side: int = 256) -> Image.Image:
        """創建 LSB 隱寫圖片"""
        header = len(ciphertext).to_bytes(8, "big")
        data = header + ciphertext
        
        cap_bits_per_pixel = len(channels) * bpc
        pixels_needed = math.ceil((len(data) * 8 * safety) / max(cap_bits_per_pixel, 1e-6))
        side = max(int(math.ceil(math.sqrt(pixels_needed))), min_side)
        
        w = h = side
        
        tex = self._gen_fbm_texture(w, h)
        arr = tex.copy()
        
        ch_idx = {"R": 0, "G": 1, "B": 2}
        idxs = [ch_idx[ch] for ch in channels]
        flat = arr[:, :, idxs].reshape(-1)
        
        symbols = self._bytes_to_symbols(data, bpc)
        mask = 0xFF ^ ((1 << bpc) - 1)
        flat[:len(symbols)] = (flat[:len(symbols)] & mask) | symbols
        
        arr[:, :, idxs] = flat.reshape(h, w, len(idxs))
        
        return Image.fromarray(arr, mode="RGB")
    
    # ============================================================
    # 載體影片生成（使用 FFmpeg）
    # ============================================================
    
    def _generate_carrier_video(self, output_path: str, 
                                duration_sec: int = None,
                                resolution: str = None,
                                fps: int = None) -> bool:
        """
        使用 FFmpeg 產生 H.264 載體影片（testsrc 測試畫面）
        
        Returns:
            成功返回 True，失敗返回 False
        """
        if not self._has_ffmpeg():
            print("⚠️ 找不到 FFmpeg，無法產生載體影片")
            return False
        
        duration_sec = duration_sec or self.CARRIER_DURATION_SEC
        resolution = resolution or self.CARRIER_RESOLUTION
        fps = fps or self.CARRIER_FPS
        
        cmd = [
            self.ffmpeg, "-y",
            "-f", "lavfi",
            "-i", f"testsrc=duration={duration_sec}:size={resolution}:rate={fps}",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-an",
            output_path
        ]
        
        try:
            subprocess.run(
                cmd,
                capture_output=True,
                timeout=30,
                check=True
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"⚠️ FFmpeg 產生載體影片失敗: {e}")
            return False
        except subprocess.TimeoutExpired:
            print("⚠️ FFmpeg 產生載體影片超時")
            return False
        except Exception as e:
            print(f"⚠️ 產生載體影片時發生錯誤: {e}")
            return False
    
    # ============================================================
    # 公開方法
    # ============================================================
    
    def save_encrypted_photo(self, 
                            ciphertext: bytes, 
                            original_filename: str,
                            create_stego: bool = True,
                            output_type: str = "image") -> Optional[str]:
        """
        儲存加密照片/影片
        
        Args:
            ciphertext: 加密的密文資料
            original_filename: 原始檔案名稱
            create_stego: True=創建隱寫檔案，False=儲存純密文
            output_type: "image"=LSB 隱寫圖片, "video"=載體影片, "auto"=自動判斷
            
        Returns:
            儲存的檔案路徑
        """
        try:
            # 自動判斷類型
            if output_type == "auto":
                ext = os.path.splitext(original_filename)[1].lower()
                if ext in ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv']:
                    output_type = "video"
                else:
                    output_type = "image"
            
            if create_stego:
                if output_type == "video":
                    # 創建載體影片
                    filename = self._generate_filename(original_filename, "encrypted", ".mp4")
                    filepath = os.path.join(self.encryption_dir, filename)
                    
                    success = self._generate_carrier_video(filepath)
                    
                    if success:
                        print(f"📁 加密影片已儲存（載體影片）: {filepath}")
                        print(f"   密文大小: {len(ciphertext):,} bytes")
                        print(f"   影片時長: {self.CARRIER_DURATION_SEC}s")
                        print(f"   影片解析度: {self.CARRIER_RESOLUTION}")
                    else:
                        # 如果影片產生失敗，改用圖片
                        print("⚠️ 影片產生失敗，改用 LSB 隱寫圖片")
                        return self.save_encrypted_photo(
                            ciphertext, original_filename, 
                            create_stego=True, output_type="image"
                        )
                else:
                    # 創建 LSB 隱寫圖片
                    filename = self._generate_filename(original_filename, "encrypted", ".png")
                    filepath = os.path.join(self.encryption_dir, filename)
                    
                    stego_img = self._create_stego_image(ciphertext)
                    stego_img.save(filepath, "PNG")
                    
                    print(f"📁 加密照片已儲存（LSB 隱寫圖）: {filepath}")
                    print(f"   密文大小: {len(ciphertext):,} bytes")
                    print(f"   圖片尺寸: {stego_img.size[0]}x{stego_img.size[1]}")
            else:
                # 儲存純密文
                filename = self._generate_filename(original_filename, "encrypted", ".bin")
                filepath = os.path.join(self.encryption_dir, filename)
                
                with open(filepath, 'wb') as f:
                    f.write(ciphertext)
                
                print(f"📁 加密照片已儲存（純密文）: {filepath}")
                print(f"   大小: {len(ciphertext):,} bytes")
            
            return filepath
            
        except Exception as e:
            print(f"⚠️ 儲存加密照片失敗: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def save_decrypted_photo(self, 
                            plaintext: bytes, 
                            original_filename: str) -> Optional[str]:
        """儲存解密照片"""
        try:
            filename = self._generate_filename(original_filename, "decrypted")
            filepath = os.path.join(self.decryption_dir, filename)
            
            with open(filepath, 'wb') as f:
                f.write(plaintext)
            
            print(f"📁 解密照片已儲存: {filepath}")
            print(f"   大小: {len(plaintext):,} bytes")
            
            return filepath
            
        except Exception as e:
            print(f"⚠️ 儲存解密照片失敗: {e}")
            return None
    
    def save_both(self, 
                  ciphertext: bytes, 
                  plaintext: bytes, 
                  original_filename: str,
                  create_stego: bool = True,
                  output_type: str = "image") -> Tuple[Optional[str], Optional[str]]:
        """同時儲存加密和解密照片"""
        encrypted_path = self.save_encrypted_photo(
            ciphertext, original_filename, create_stego, output_type
        )
        decrypted_path = self.save_decrypted_photo(plaintext, original_filename)
        return encrypted_path, decrypted_path
    
    def cleanup(self):
        """清理所有照片"""
        print("\n🧹 正在清理照片資料夾...")
        
        total_deleted = 0
        
        for dir_path in [self.encryption_dir, self.decryption_dir]:
            if os.path.exists(dir_path):
                try:
                    file_count = 0
                    for filename in os.listdir(dir_path):
                        file_path = os.path.join(dir_path, filename)
                        if os.path.isfile(file_path):
                            os.remove(file_path)
                            file_count += 1
                    
                    total_deleted += file_count
                    print(f"   ✅ {dir_path}: 已刪除 {file_count} 個檔案")
                    
                except Exception as e:
                    print(f"   ⚠️ 清理 {dir_path} 時發生錯誤: {e}")
        
        print(f"🧹 照片資料夾清理完成，共刪除 {total_deleted} 個檔案\n")
    
    def get_file_count(self) -> Tuple[int, int]:
        """取得目前照片數量 (加密, 解密)"""
        enc_count = len([f for f in os.listdir(self.encryption_dir) 
                        if os.path.isfile(os.path.join(self.encryption_dir, f))]) if os.path.exists(self.encryption_dir) else 0
        dec_count = len([f for f in os.listdir(self.decryption_dir) 
                        if os.path.isfile(os.path.join(self.decryption_dir, f))]) if os.path.exists(self.decryption_dir) else 0
        return enc_count, dec_count
    
    def list_files(self) -> Tuple[list, list]:
        """列出所有照片檔案"""
        enc_files = sorted(os.listdir(self.encryption_dir)) if os.path.exists(self.encryption_dir) else []
        dec_files = sorted(os.listdir(self.decryption_dir)) if os.path.exists(self.decryption_dir) else []
        return enc_files, dec_files


# 全域實例
_storage_manager = None

def get_storage_manager() -> PhotoStorageManager:
    """取得全域的照片儲存管理器"""
    global _storage_manager
    if _storage_manager is None:
        _storage_manager = PhotoStorageManager()
    return _storage_manager


# ============================================================
# 測試
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("PhotoStorageManager 測試（圖片 + 影片）")
    print("=" * 60)
    
    storage = PhotoStorageManager()
    
    print(f"\n📋 FFmpeg 可用: {storage._has_ffmpeg()}")
    
    fake_ciphertext = os.urandom(10000)
    fake_plaintext = b"Original medical image..." * 100
    
    # 測試圖片
    print("\n" + "-" * 40)
    print("測試 1: LSB 隱寫圖片")
    print("-" * 40)
    enc_path = storage.save_encrypted_photo(
        fake_ciphertext, "xray.png", 
        create_stego=True, output_type="image"
    )
    
    # 測試影片
    print("\n" + "-" * 40)
    print("測試 2: 載體影片")
    print("-" * 40)
    enc_video = storage.save_encrypted_photo(
        fake_ciphertext, "ultrasound.mp4", 
        create_stego=True, output_type="video"
    )
    
    # 測試解密
    print("\n" + "-" * 40)
    print("測試 3: 解密照片")
    print("-" * 40)
    dec_path = storage.save_decrypted_photo(fake_plaintext, "xray.png")
    
    enc_count, dec_count = storage.get_file_count()
    print(f"\n📋 檔案數量: 加密={enc_count}, 解密={dec_count}")
    
    input("\n按 Enter 清理並結束...")
    storage.cleanup()
    print("✅ 完成")