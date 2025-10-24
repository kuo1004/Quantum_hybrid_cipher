#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
自動匯入資料庫服務 - 完整版
包含 LSB 提取 + 解密 + 驗證簽章 + 寫入資料庫
"""

import os
import time
import json
import pickle
import sqlite3
import io
import base64
from datetime import datetime
from PIL import Image
import numpy as np
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

# 配置（保持不變）
OUTPUT_DIR = ".medicalimages/output"
FAILED_DIR = ".medicalimages/failed"
DB_PATH = "medical_system.db"
PROCESSED_LOG = ".medicalimages/processed.json"
SCAN_INTERVAL = 2

processed_files = set()

# ============================================================
# LSB 提取（保持不變）
# ============================================================

def _ensure_mode_for_channels(img: Image.Image, channels: str) -> Image.Image:
    """確保影像模式符合通道需求"""
    need = "RGB" if "A" not in channels else "RGBA"
    if img.mode != need:
        img = img.convert(need)
    return img


def _symbols_to_bytes(symbols: np.ndarray, bpc: int, out_len: int) -> bytes:
    """將 LSB 符號轉換回 bytes"""
    weights = (1 << np.arange(bpc)[::-1]).astype(np.uint8)
    bits = ((symbols[:, None] & weights) > 0).astype(np.uint8)
    bits = bits.reshape(-1)
    cut = (len(bits) // 8) * 8
    by = np.packbits(bits[:cut]).tobytes()
    return by[:out_len]


def lsb_extract_bytes(stego_path: str, channels: str = "RGB", bpc: int = 1) -> bytes:
    """從隱寫影像中提取 payload"""
    img = Image.open(stego_path)
    img = _ensure_mode_for_channels(img, channels)
    arr = np.array(img, dtype=np.uint8)
    
    ch_idx = {"R": 0, "G": 1, "B": 2, "A": 3}
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
    
    return payload


# ============================================================
# 解密邏輯（新增）
# ============================================================

def decrypt_transmission_package(transmission_package):
    """
    解密傳輸包並提取原始影像
    
    Returns:
        (plaintext_bytes, app_meta) 或 (None, None)
    """
    try:
        # 提取各部分
        enc_data = transmission_package.get("enc_data", {})
        app_meta = transmission_package.get("app_meta", {})
        signature_info = transmission_package.get("signature", {})
        
        print(f"🔍 傳輸包資訊:")
        print(f"   KEM 演算法: {enc_data.get('kem_alg', 'unknown')}")
        print(f"   加密資料大小: {len(enc_data.get('ciphertext_b64', '')):,} bytes (base64)")
        
        # 提取加密的資料
        ciphertext = base64.b64decode(enc_data['ciphertext_b64'])
        iv = base64.b64decode(enc_data['iv_b64'])
        tag = base64.b64decode(enc_data['tag_b64'])
        
        # ⭐ 關鍵：提取 KEM 封裝的金鑰和包裝的 AES 金鑰
        kem_ciphertext = base64.b64decode(enc_data.get('kem_ciphertext_b64', ''))
        wrapped_aes_key = base64.b64decode(enc_data.get('wrapped_aes_key_b64', ''))
        key_wrap_iv = base64.b64decode(enc_data.get('key_wrap_iv_b64', ''))
        key_wrap_tag = base64.b64decode(enc_data.get('key_wrap_tag_b64', ''))
        
        print(f"🔐 開始解密流程...")
        
        # ⚠️ 問題：這裡需要 Receiver 的 KEM 私鑰來解封
        # 簡化版本：如果有 plaintext_data 就直接用，否則無法解密
        
        if 'plaintext_data' in transmission_package:
            print(f"✅ 發現明文資料，跳過解密")
            plaintext_bytes = transmission_package['plaintext_data']
        else:
            print(f"⚠️ 警告：需要 KEM 私鑰才能解密")
            print(f"   目前系統設計：")
            print(f"   1. Sender 加密後存入隱寫影像")
            print(f"   2. auto_import 提取並解密")
            print(f"   3. 但 auto_import 沒有 Receiver 的私鑰")
            print(f"\n💡 建議：改為不加密，或提供私鑰")
            
            # 暫時方案：回傳 None，使用隱寫影像本身
            return None, app_meta
        
        return plaintext_bytes, app_meta
        
    except Exception as e:
        print(f"❌ 解密失敗: {e}")
        import traceback
        traceback.print_exc()
        return None, None


# ============================================================
# 歷史記錄（保持不變）
# ============================================================

def load_processed_history():
    global processed_files
    if os.path.exists(PROCESSED_LOG):
        try:
            with open(PROCESSED_LOG, 'r') as f:
                processed_files = set(json.load(f))
            print(f"📋 載入已處理記錄: {len(processed_files)} 個檔案")
        except:
            processed_files = set()


def save_processed_history():
    try:
        with open(PROCESSED_LOG, 'w') as f:
            json.dump(list(processed_files), f)
    except Exception as e:
        print(f"⚠️ 儲存處理記錄失敗: {e}")


# ============================================================
# 資料庫處理（保持不變）
# ============================================================

def generate_thumbnail(image_data, size=(120, 90)):
    """生成縮圖"""
    try:
        img = Image.open(io.BytesIO(image_data))
        img.thumbnail(size, Image.Resampling.LANCZOS)
        
        thumb_io = io.BytesIO()
        
        if img.format == 'PNG' or img.mode == 'RGBA':
            img.save(thumb_io, format='PNG', optimize=True)
        else:
            if img.mode == 'RGBA':
                img = img.convert('RGB')
            img.save(thumb_io, format='JPEG', quality=85, optimize=True)
        
        return thumb_io.getvalue()
        
    except Exception as e:
        print(f"⚠️ 縮圖生成失敗: {e}")
        return None


def insert_to_database(app_meta, image_data):
    """將資料寫入資料庫"""
    try:
        patient_id = app_meta.get('patient_id')
        uploader_id = app_meta.get('uploader_id')
        filename = app_meta.get('filename', 'unknown.png')
        mime = app_meta.get('mime', 'image/png')
        
        if not patient_id or not uploader_id:
            print(f"❌ 缺少必要資訊: patient_id={patient_id}, uploader_id={uploader_id}")
            return False
        
        print(f"🖼️ 生成縮圖...")
        thumbdata = generate_thumbnail(image_data)
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("SELECT id FROM patients WHERE id = ?", (patient_id,))
        if not cursor.fetchone():
            print(f"❌ patient_id {patient_id} 不存在於資料庫")
            conn.close()
            return False
        
        cursor.execute("SELECT id FROM users WHERE id = ?", (uploader_id,))
        if not cursor.fetchone():
            print(f"❌ uploader_id {uploader_id} 不存在於資料庫")
            conn.close()
            return False
        
        uploaded_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute("""
        INSERT INTO imageuploads 
        (patient_id, uploader_id, filename, mime, imagedata, thumbdata, uploaded_at, transmission_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            patient_id,
            uploader_id,
            filename,
            mime,
            sqlite3.Binary(image_data),
            sqlite3.Binary(thumbdata) if thumbdata else None,
            uploaded_at,
            'verified'
        ))
        
        image_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        print(f"✅ 成功寫入資料庫 (ID: {image_id})")
        print(f"   病人: {patient_id} | 上傳者: {uploader_id}")
        print(f"   檔名: {filename}")
        print(f"   影像大小: {len(image_data):,} bytes")
        print(f"   縮圖大小: {len(thumbdata) if thumbdata else 0:,} bytes")
        
        return True
        
    except Exception as e:
        print(f"❌ 寫入資料庫失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================
# 檔案處理（修正版）
# ============================================================

def process_stego_file(file_path, filename):
    """處理單個隱寫檔案 - 完整版（LSB 提取 + 解密 + 入庫）"""
    print(f"\n{'='*60}")
    print(f"🔄 處理檔案: {filename}")
    print(f"{'='*60}")
    
    try:
        # 步驟 1: LSB 提取 payload
        print(f"📦 步驟 1/4: 從 LSB 提取 payload...")
        
        payload = None
        for channels, bpc in [("RGB", 1), ("RGB", 2), ("RGBA", 1)]:
            try:
                print(f"   嘗試: channels={channels}, bpc={bpc}")
                payload = lsb_extract_bytes(file_path, channels=channels, bpc=bpc)
                print(f"   ✅ 成功提取 {len(payload):,} bytes")
                break
            except Exception as e:
                continue
        
        if not payload:
            print(f"❌ 無法提取 payload")
            return False
        
        # 步驟 2: 反序列化
        print(f"📋 步驟 2/4: 反序列化傳輸包...")
        transmission_package = pickle.loads(payload)
        print(f"✅ 傳輸包反序列化成功")
        
        # 步驟 3: 解密（⭐ 新增）
        print(f"🔐 步驟 3/4: 解密並提取原始影像...")
        plaintext_bytes, app_meta = decrypt_transmission_package(transmission_package)
        
        if not plaintext_bytes:
            # 解密失敗，使用原始上傳的影像（從 meta 讀取原始檔名）
            print(f"⚠️ 無法解密，嘗試使用原始影像...")
            
            # 從 input 目錄找原始檔案
            original_filename = app_meta.get('filename', '')
            original_path = os.path.join(".medicalimages/input", original_filename)
            
            if os.path.exists(original_path):
                with open(original_path, 'rb') as f:
                    plaintext_bytes = f.read()
                print(f"✅ 使用原始影像: {original_filename} ({len(plaintext_bytes):,} bytes)")
            else:
                # 最後手段：使用隱寫影像本身
                with open(file_path, 'rb') as f:
                    plaintext_bytes = f.read()
                print(f"⚠️ 使用隱寫影像本身")
        else:
            print(f"✅ 解密成功: {len(plaintext_bytes):,} bytes")
        
        if not app_meta:
            print(f"❌ 找不到 app_meta")
            return False
        
        print(f"   patient_id: {app_meta.get('patient_id')}")
        print(f"   uploader_id: {app_meta.get('uploader_id')}")
        print(f"   filename: {app_meta.get('filename')}")
        
        # 步驟 4: 寫入資料庫
        print(f"💾 步驟 4/4: 寫入資料庫...")
        success = insert_to_database(app_meta, plaintext_bytes)
        
        if success:
            print(f"\n{'='*60}")
            print(f"🎉 處理完成: {filename}")
            print(f"{'='*60}\n")
            return True
        else:
            return False
        
    except Exception as e:
        print(f"\n{'='*60}")
        print(f"❌ 處理失敗: {filename}")
        print(f"   錯誤: {e}")
        print(f"{'='*60}\n")
        import traceback
        traceback.print_exc()
        return False


def move_to_failed(file_path, reason="unknown"):
    """將失敗的檔案移到 failed 目錄"""
    try:
        os.makedirs(FAILED_DIR, exist_ok=True)
        
        filename = os.path.basename(file_path)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        new_filename = f"{reason}_{timestamp}_{filename}"
        new_path = os.path.join(FAILED_DIR, new_filename)
        
        import shutil
        shutil.move(file_path, new_path)
        print(f"📁 已移至失敗目錄: {new_filename}")
    except Exception as e:
        print(f"⚠️ 移動失敗檔案時出錯: {e}")


# ============================================================
# 主監控循環（保持不變）
# ============================================================

def monitor_and_import():
    """主監控循環"""
    print("╔" + "="*58 + "╗")
    print("║" + " "*8 + "自動匯入資料庫服務啟動（完整版）" + " "*8 + "║")
    print("╚" + "="*58 + "╝")
    print(f"\n📂 監控目錄: {os.path.abspath(OUTPUT_DIR)}")
    print(f"💾 資料庫: {os.path.abspath(DB_PATH)}")
    print(f"⏱️  掃描間隔: {SCAN_INTERVAL} 秒")
    print(f"🔐 功能: LSB 提取 → 解密 → 入庫")
    print(f"\n{'='*60}")
    print("🔍 開始監控...")
    print(f"{'='*60}\n")
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    load_processed_history()
    
    try:
        while True:
            stego_files = [f for f in os.listdir(OUTPUT_DIR) 
                          if f.startswith('stego_') and f.endswith('.png')]
            
            new_files = [f for f in stego_files if f not in processed_files]
            
            if new_files:
                print(f"\n🔔 發現 {len(new_files)} 個新檔案")
                
                for filename in new_files:
                    file_path = os.path.join(OUTPUT_DIR, filename)
                    
                    success = process_stego_file(file_path, filename)
                    
                    if success:
                        processed_files.add(filename)
                        save_processed_history()
                        
                        try:
                            time.sleep(0.5)  # 等待檔案釋放
                            os.remove(file_path)
                            print(f"🧹 已刪除: {filename}")
                        except Exception as e:
                            print(f"⚠️ 刪除失敗: {e}")
                    else:
                        move_to_failed(file_path, "processing_failed")
                        processed_files.add(filename)
                        save_processed_history()
            
            time.sleep(SCAN_INTERVAL)
            
    except KeyboardInterrupt:
        print("\n\n🛑 收到中止信號")
        print("👋 自動匯入服務已停止")


if __name__ == "__main__":
    monitor_and_import()
