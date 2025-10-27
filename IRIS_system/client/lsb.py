#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LSB (Least Significant Bit) Steganography - LSB 隱寫術
用於在醫療影像中隱藏加密資訊
"""

import os
import json
import struct
from typing import Tuple, Optional
from PIL import Image
import numpy as np


class LSBSteganography:
    """
    LSB 隱寫術實作
    將資料隱藏在影像的最低有效位元中
    """
    
    def __init__(self):
        """初始化 LSB 隱寫術"""
        self.magic_header = b"IRIS"  # 用於識別隱寫影像
        self.version = 1
    
    def embed(self, carrier_image_path: str, secret_data: bytes, 
              output_path: str, metadata: Optional[dict] = None) -> str:
        """
        將秘密資料嵌入影像中
        
        Args:
            carrier_image_path: 載體影像路徑（PNG）
            secret_data: 要隱藏的資料（bytes）
            output_path: 輸出影像路徑（PNG）
            metadata: 可選的元資料（會一起嵌入）
            
        Returns:
            str: 輸出檔案路徑
            
        Raises:
            ValueError: 如果載體影像容量不足
            IOError: 如果檔案操作失敗
        """
        # 載入載體影像
        try:
            carrier = Image.open(carrier_image_path)
            
            # 轉換為 RGB（如果是 RGBA 或其他格式）
            if carrier.mode != 'RGB':
                carrier = carrier.convert('RGB')
            
            img_array = np.array(carrier)
        except Exception as e:
            raise IOError(f"無法載入載體影像: {e}") from e
        
        # 準備要嵌入的完整資料
        # 格式: [MAGIC][VERSION][METADATA_LEN][METADATA][DATA_LEN][DATA]
        full_data = self._prepare_data(secret_data, metadata)
        
        # 檢查容量
        max_capacity = self._calculate_capacity(img_array)
        if len(full_data) > max_capacity:
            raise ValueError(
                f"載體影像容量不足: 需要 {len(full_data)} bytes, "
                f"可用 {max_capacity} bytes"
            )
        
        # 嵌入資料
        stego_array = self._embed_data(img_array, full_data)
        
        # 儲存隱寫影像
        try:
            stego_image = Image.fromarray(stego_array)
            stego_image.save(output_path, 'PNG')
            print(f"✅ 資料已嵌入影像: {output_path}")
            print(f"   嵌入資料大小: {len(secret_data)} bytes")
            if metadata:
                print(f"   元資料: {list(metadata.keys())}")
        except Exception as e:
            raise IOError(f"無法儲存隱寫影像: {e}") from e
        
        return output_path
    
    def extract(self, stego_image_path: str) -> Tuple[bytes, Optional[dict]]:
        """
        從隱寫影像中提取秘密資料
        
        Args:
            stego_image_path: 隱寫影像路徑
            
        Returns:
            tuple: (secret_data, metadata)
                - secret_data: 提取的資料（bytes）
                - metadata: 元資料（dict 或 None）
                
        Raises:
            ValueError: 如果影像不包含隱寫資料或格式錯誤
            IOError: 如果檔案操作失敗
        """
        # 載入隱寫影像
        try:
            stego = Image.open(stego_image_path)
            if stego.mode != 'RGB':
                stego = stego.convert('RGB')
            img_array = np.array(stego)
        except Exception as e:
            raise IOError(f"無法載入隱寫影像: {e}") from e
        
        # 提取並解析資料
        try:
            secret_data, metadata = self._extract_data(img_array)
            print(f"✅ 資料已從影像提取")
            print(f"   提取資料大小: {len(secret_data)} bytes")
            if metadata:
                print(f"   元資料: {list(metadata.keys())}")
            return secret_data, metadata
        except Exception as e:
            raise ValueError(f"資料提取失敗: {e}") from e
    
    def _prepare_data(self, secret_data: bytes, metadata: Optional[dict]) -> bytes:
        """
        準備要嵌入的完整資料
        
        格式:
        [4 bytes] MAGIC ("IRIS")
        [1 byte]  VERSION
        [4 bytes] METADATA_LENGTH (如果有元資料)
        [N bytes] METADATA (JSON, 如果有)
        [4 bytes] DATA_LENGTH
        [N bytes] DATA
        """
        # 魔術標頭和版本
        result = self.magic_header + struct.pack('B', self.version)
        
        # 元資料（可選）
        if metadata:
            metadata_bytes = json.dumps(metadata).encode('utf-8')
            result += struct.pack('I', len(metadata_bytes))
            result += metadata_bytes
        else:
            result += struct.pack('I', 0)
        
        # 秘密資料長度和內容
        result += struct.pack('I', len(secret_data))
        result += secret_data
        
        return result
    
    def _embed_data(self, img_array: np.ndarray, data: bytes) -> np.ndarray:
        """
        將資料嵌入影像陣列的 LSB
        
        Args:
            img_array: 影像陣列 (H, W, 3)
            data: 要嵌入的資料
            
        Returns:
            np.ndarray: 嵌入資料後的影像陣列
        """
        # 複製影像陣列
        stego_array = img_array.copy()
        
        # 將資料轉換為位元串
        data_bits = ''.join(format(byte, '08b') for byte in data)
        
        # 將位元嵌入 LSB
        height, width, channels = stego_array.shape
        data_index = 0
        
        for i in range(height):
            for j in range(width):
                for k in range(channels):
                    if data_index < len(data_bits):
                        # 清除 LSB 並設定新值
                        stego_array[i, j, k] = (stego_array[i, j, k] & 0xFE) | int(data_bits[data_index])
                        data_index += 1
                    else:
                        return stego_array
        
        return stego_array
    
    def _extract_data(self, img_array: np.ndarray) -> Tuple[bytes, Optional[dict]]:
        """
        從影像陣列的 LSB 提取資料
        
        Args:
            img_array: 影像陣列
            
        Returns:
            tuple: (secret_data, metadata)
        """
        height, width, channels = img_array.shape
        
        # 提取位元
        bits = []
        for i in range(height):
            for j in range(width):
                for k in range(channels):
                    bits.append(str(img_array[i, j, k] & 1))
        
        # 轉換為 bytes
        bit_string = ''.join(bits)
        all_bytes = bytearray()
        for i in range(0, len(bit_string), 8):
            byte = bit_string[i:i+8]
            if len(byte) == 8:
                all_bytes.append(int(byte, 2))
        
        # 解析標頭
        offset = 0
        
        # 檢查魔術標頭
        magic = bytes(all_bytes[offset:offset+4])
        if magic != self.magic_header:
            raise ValueError("影像不包含有效的隱寫資料（魔術標頭不符）")
        offset += 4
        
        # 檢查版本
        version = all_bytes[offset]
        if version != self.version:
            raise ValueError(f"不支援的版本: {version}")
        offset += 1
        
        # 讀取元資料長度
        metadata_len = struct.unpack('I', bytes(all_bytes[offset:offset+4]))[0]
        offset += 4
        
        # 讀取元資料（如果有）
        metadata = None
        if metadata_len > 0:
            metadata_bytes = bytes(all_bytes[offset:offset+metadata_len])
            metadata = json.loads(metadata_bytes.decode('utf-8'))
            offset += metadata_len
        
        # 讀取資料長度
        data_len = struct.unpack('I', bytes(all_bytes[offset:offset+4]))[0]
        offset += 4
        
        # 讀取秘密資料
        secret_data = bytes(all_bytes[offset:offset+data_len])
        
        return secret_data, metadata
    
    def _calculate_capacity(self, img_array: np.ndarray) -> int:
        """
        計算影像的隱藏容量（bytes）
        
        Args:
            img_array: 影像陣列
            
        Returns:
            int: 可隱藏的位元組數
        """
        height, width, channels = img_array.shape
        total_bits = height * width * channels
        # 扣除標頭開銷 (4 + 1 + 4 + 4 = 13 bytes)
        return (total_bits // 8) - 13
    
    def check_capacity(self, image_path: str, data_size: int) -> Tuple[bool, int]:
        """
        檢查影像是否有足夠容量
        
        Args:
            image_path: 影像路徑
            data_size: 要隱藏的資料大小（bytes）
            
        Returns:
            tuple: (is_sufficient, available_capacity)
        """
        try:
            img = Image.open(image_path)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            img_array = np.array(img)
            
            capacity = self._calculate_capacity(img_array)
            return (data_size <= capacity, capacity)
        except Exception as e:
            raise IOError(f"無法檢查影像容量: {e}") from e
    
    def create_carrier(self, width: int, height: int, output_path: str, 
                      color: Tuple[int, int, int] = (255, 255, 255)) -> str:
        """
        創建一個載體影像
        
        Args:
            width: 寬度
            height: 高度
            output_path: 輸出路徑
            color: RGB 顏色，預設白色
            
        Returns:
            str: 輸出檔案路徑
        """
        img = Image.new('RGB', (width, height), color)
        img.save(output_path, 'PNG')
        print(f"✅ 已創建載體影像: {output_path} ({width}x{height})")
        
        capacity = self._calculate_capacity(np.array(img))
        print(f"   可隱藏容量: {capacity:,} bytes ({capacity/1024:.2f} KB)")
        
        return output_path


def demo():
    """示範 LSB 隱寫術的使用"""
    print("="*70)
    print("🔒 LSB Steganography 示範")
    print("="*70)
    
    lsb = LSBSteganography()
    
    # 創建載體影像
    print("\n📋 步驟 1: 創建載體影像")
    carrier_path = "carrier.png"
    lsb.create_carrier(800, 600, carrier_path)
    
    # 準備秘密資料
    print("\n📋 步驟 2: 準備秘密資料")
    secret_data = b"This is a secret medical record with sensitive patient information."
    metadata = {
        "patient_id": "P12345",
        "timestamp": "2025-10-26 10:30:00",
        "encrypted": True
    }
    print(f"   秘密資料: {len(secret_data)} bytes")
    print(f"   元資料: {metadata}")
    
    # 檢查容量
    print("\n📋 步驟 3: 檢查容量")
    is_sufficient, capacity = lsb.check_capacity(carrier_path, len(secret_data))
    print(f"   載體容量: {capacity:,} bytes")
    print(f"   需要容量: {len(secret_data)} bytes")
    print(f"   容量足夠: {'✅ 是' if is_sufficient else '❌ 否'}")
    
    # 嵌入資料
    print("\n📋 步驟 4: 嵌入秘密資料")
    stego_path = "stego.png"
    lsb.embed(carrier_path, secret_data, stego_path, metadata)
    
    # 提取資料
    print("\n📋 步驟 5: 提取秘密資料")
    extracted_data, extracted_metadata = lsb.extract(stego_path)
    
    # 驗證
    print("\n📋 步驟 6: 驗證")
    if extracted_data == secret_data:
        print("✅ 資料提取成功且一致")
    else:
        print("❌ 資料不一致")
    
    if extracted_metadata == metadata:
        print("✅ 元資料提取成功且一致")
    else:
        print("❌ 元資料不一致")
    
    # 清理
    print("\n📋 步驟 7: 清理")
    os.remove(carrier_path)
    os.remove(stego_path)
    print("✅ 清理完成")
    
    print("\n" + "="*70)
    print("✅ 示範完成")
    print("="*70)


if __name__ == "__main__":
    demo()
