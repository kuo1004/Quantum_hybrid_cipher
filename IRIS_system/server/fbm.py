#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FBM (File Block Manager) - 檔案式區塊管理器
用於處理醫療影像的分塊加密與傳輸
"""

import os
import json
import hashlib
from typing import List, Tuple, Dict, Optional


class FileBlockManager:
    """
    檔案式區塊管理器
    負責將大型檔案分割成區塊，並管理區塊的元資料
    """
    
    def __init__(self, block_size: int = 1024 * 1024):
        """
        初始化區塊管理器
        
        Args:
            block_size: 區塊大小（bytes），預設 1MB
        """
        self.block_size = block_size
    
    def split_file(self, file_path: str, output_dir: Optional[str] = None) -> Dict:
        """
        將檔案分割成多個區塊
        
        Args:
            file_path: 原始檔案路徑
            output_dir: 區塊輸出目錄，預設為原檔案目錄下的 .blocks 子目錄
            
        Returns:
            dict: 包含區塊資訊的字典
            {
                "file_name": "原始檔名",
                "file_size": 檔案大小,
                "file_hash": "SHA256 雜湊",
                "block_size": 區塊大小,
                "total_blocks": 總區塊數,
                "blocks": [
                    {
                        "block_id": 0,
                        "block_path": "區塊檔案路徑",
                        "block_size": 實際大小,
                        "block_hash": "SHA256 雜湊"
                    },
                    ...
                ]
            }
            
        Raises:
            FileNotFoundError: 如果檔案不存在
            IOError: 如果讀取檔案失敗
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"檔案不存在: {file_path}")
        
        # 設定輸出目錄
        if output_dir is None:
            base_dir = os.path.dirname(file_path)
            file_name = os.path.basename(file_path)
            output_dir = os.path.join(base_dir, f".blocks_{file_name}")
        
        os.makedirs(output_dir, exist_ok=True)
        
        # 計算檔案雜湊
        file_hash = self._calculate_file_hash(file_path)
        file_size = os.path.getsize(file_path)
        
        # 開始分割
        blocks_info = []
        block_id = 0
        
        try:
            with open(file_path, 'rb') as f:
                while True:
                    # 讀取一個區塊
                    block_data = f.read(self.block_size)
                    if not block_data:
                        break
                    
                    # 儲存區塊
                    block_filename = f"block_{block_id:04d}.dat"
                    block_path = os.path.join(output_dir, block_filename)
                    
                    with open(block_path, 'wb') as block_file:
                        block_file.write(block_data)
                    
                    # 計算區塊雜湊
                    block_hash = hashlib.sha256(block_data).hexdigest()
                    
                    # 記錄區塊資訊
                    blocks_info.append({
                        "block_id": block_id,
                        "block_path": block_path,
                        "block_size": len(block_data),
                        "block_hash": block_hash
                    })
                    
                    block_id += 1
        
        except Exception as e:
            raise IOError(f"分割檔案失敗: {e}") from e
        
        # 組合元資料
        metadata = {
            "file_name": os.path.basename(file_path),
            "file_path": os.path.abspath(file_path),
            "file_size": file_size,
            "file_hash": file_hash,
            "block_size": self.block_size,
            "total_blocks": len(blocks_info),
            "blocks": blocks_info,
            "output_dir": output_dir
        }
        
        # 儲存元資料
        metadata_path = os.path.join(output_dir, "metadata.json")
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        print(f"✅ 檔案分割完成: {len(blocks_info)} 個區塊")
        print(f"   輸出目錄: {output_dir}")
        
        return metadata
    
    def merge_blocks(self, metadata: Dict, output_path: Optional[str] = None, 
                     verify: bool = True) -> str:
        """
        合併區塊為完整檔案
        
        Args:
            metadata: 區塊元資料（從 split_file 返回或從 metadata.json 讀取）
            output_path: 輸出檔案路徑，預設為原始檔名
            verify: 是否驗證合併後的檔案雜湊
            
        Returns:
            str: 合併後的檔案路徑
            
        Raises:
            ValueError: 如果區塊遺失或損壞
            IOError: 如果寫入檔案失敗
        """
        # 設定輸出路徑
        if output_path is None:
            output_path = os.path.join(
                os.path.dirname(metadata["output_dir"]),
                f"merged_{metadata['file_name']}"
            )
        
        # 確保輸出目錄存在
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        
        try:
            with open(output_path, 'wb') as output_file:
                for block_info in metadata["blocks"]:
                    block_path = block_info["block_path"]
                    
                    # 檢查區塊是否存在
                    if not os.path.exists(block_path):
                        raise ValueError(f"區塊遺失: {block_path}")
                    
                    # 讀取區塊
                    with open(block_path, 'rb') as block_file:
                        block_data = block_file.read()
                    
                    # 驗證區塊雜湊
                    if verify:
                        block_hash = hashlib.sha256(block_data).hexdigest()
                        if block_hash != block_info["block_hash"]:
                            raise ValueError(f"區塊損壞 (雜湊不符): {block_path}")
                    
                    # 寫入輸出檔案
                    output_file.write(block_data)
        
        except Exception as e:
            # 如果合併失敗，刪除不完整的輸出檔案
            if os.path.exists(output_path):
                os.remove(output_path)
            raise IOError(f"合併區塊失敗: {e}") from e
        
        # 驗證完整檔案
        if verify:
            merged_hash = self._calculate_file_hash(output_path)
            if merged_hash != metadata["file_hash"]:
                os.remove(output_path)
                raise ValueError("合併後的檔案雜湊不符，檔案可能損壞")
        
        print(f"✅ 區塊合併完成: {output_path}")
        return output_path
    
    def load_metadata(self, metadata_path: str) -> Dict:
        """
        從檔案載入元資料
        
        Args:
            metadata_path: metadata.json 的路徑
            
        Returns:
            dict: 元資料字典
            
        Raises:
            FileNotFoundError: 如果元資料檔案不存在
            json.JSONDecodeError: 如果 JSON 格式錯誤
        """
        if not os.path.exists(metadata_path):
            raise FileNotFoundError(f"元資料檔案不存在: {metadata_path}")
        
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        return metadata
    
    def cleanup_blocks(self, metadata: Dict) -> None:
        """
        清理區塊檔案
        
        Args:
            metadata: 區塊元資料
        """
        output_dir = metadata.get("output_dir")
        if output_dir and os.path.exists(output_dir):
            import shutil
            shutil.rmtree(output_dir)
            print(f"✅ 已清理區塊目錄: {output_dir}")
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """
        計算檔案的 SHA256 雜湊
        
        Args:
            file_path: 檔案路徑
            
        Returns:
            str: SHA256 雜湊值（hex）
        """
        sha256_hash = hashlib.sha256()
        
        with open(file_path, 'rb') as f:
            # 分塊讀取以處理大檔案
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        
        return sha256_hash.hexdigest()
    
    def get_block_info(self, metadata: Dict, block_id: int) -> Optional[Dict]:
        """
        獲取特定區塊的資訊
        
        Args:
            metadata: 元資料
            block_id: 區塊 ID
            
        Returns:
            dict: 區塊資訊，如果不存在則返回 None
        """
        for block in metadata["blocks"]:
            if block["block_id"] == block_id:
                return block
        return None


def demo():
    """示範 FBM 的使用"""
    print("="*70)
    print("📦 FileBlockManager 示範")
    print("="*70)
    
    # 創建測試檔案
    test_file = "test_image.dat"
    test_data = b"This is a test medical image data. " * 1000  # 約 35KB
    
    print(f"\n📋 創建測試檔案: {test_file}")
    with open(test_file, 'wb') as f:
        f.write(test_data)
    print(f"✅ 測試檔案大小: {len(test_data)} bytes")
    
    # 創建 FBM 實例
    fbm = FileBlockManager(block_size=10*1024)  # 10KB per block
    
    # 分割檔案
    print(f"\n📋 分割檔案...")
    metadata = fbm.split_file(test_file)
    print(f"   總區塊數: {metadata['total_blocks']}")
    print(f"   檔案雜湊: {metadata['file_hash'][:16]}...")
    
    # 合併區塊
    print(f"\n📋 合併區塊...")
    merged_file = fbm.merge_blocks(metadata, output_path="merged_test.dat")
    
    # 驗證
    print(f"\n📋 驗證...")
    original_hash = fbm._calculate_file_hash(test_file)
    merged_hash = fbm._calculate_file_hash(merged_file)
    
    if original_hash == merged_hash:
        print("✅ 驗證成功：原始檔案與合併檔案一致")
    else:
        print("❌ 驗證失敗：檔案不一致")
    
    # 清理
    print(f"\n📋 清理...")
    fbm.cleanup_blocks(metadata)
    os.remove(test_file)
    os.remove(merged_file)
    print("✅ 清理完成")
    
    print("\n" + "="*70)
    print("✅ 示範完成")
    print("="*70)


if __name__ == "__main__":
    demo()
