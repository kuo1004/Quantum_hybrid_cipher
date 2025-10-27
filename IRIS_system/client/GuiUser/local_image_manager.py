# -*- coding: utf-8 -*-
"""
local_image_manager.py - 本地影像暫存管理模組（簡化版）
支援：病患姓名、MRN、上傳時間
"""
import os
import json
import shutil
from datetime import datetime
from pathlib import Path

class LocalImageManager:
    """管理本地暫存的影像（簡化版）"""
    
    def __init__(self, base_dir="medicalimages"):
        """
        初始化本地影像管理器
        
        Args:
            base_dir: 暫存目錄名稱
        """
        self.base_dir = Path(base_dir)
        self.metadata_file = self.base_dir / "metadata.json"
        
        # 創建暫存目錄
        self.base_dir.mkdir(exist_ok=True)
        
        # 載入或初始化 metadata
        self.metadata = self._load_metadata()
    
    def _load_metadata(self):
        """載入 metadata"""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️ 載入 metadata 失敗: {e}")
                return {"images": []}
        return {"images": []}
    
    def _save_metadata(self):
        """儲存 metadata"""
        try:
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ 儲存 metadata 失敗: {e}")
    
    def add_image(self, image_path, patient_id, patient_name=None, mrn=None, upload_time=None):
        """
        加入新影像到暫存
        
        Args:
            image_path: 原始影像路徑
            patient_id: 病患編號
            patient_name: 病患姓名
            mrn: MRN (Medical Record Number)
            upload_time: 上傳時間
        
        Returns:
            dict: 影像資訊
        """
        try:
            # 生成唯一 ID
            image_id = len(self.metadata["images"]) + 1
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 取得原始檔案名稱和副檔名
            original_filename = os.path.basename(image_path)
            file_ext = os.path.splitext(original_filename)[1]
            
            # 新檔案名稱
            new_filename = f"{patient_id}_{timestamp}{file_ext}"
            new_path = self.base_dir / new_filename
            
            # 複製檔案到暫存目錄
            shutil.copy2(image_path, new_path)
            
            # 建立 metadata
            image_info = {
                "id": image_id,
                "filename": original_filename,
                "local_filename": new_filename,
                "local_path": str(new_path),
                "patient_id": patient_id,
                "patient_name": patient_name or "未知",
                "mrn": mrn or "-",
                "upload_time": upload_time or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "uploaded_at": datetime.now().isoformat(),
                "timestamp": timestamp,
                "file_size": os.path.getsize(new_path),
                "status": "local"  # local = 本地暫存, uploaded = 已上傳
            }
            
            # 加入到 metadata
            self.metadata["images"].append(image_info)
            self._save_metadata()
            
            print(f"✅ 影像已暫存: {new_filename}")
            return image_info
            
        except Exception as e:
            print(f"❌ 暫存影像失敗: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_all_images(self):
        """取得所有暫存影像"""
        return self.metadata.get("images", [])
    
    def get_image_by_id(self, image_id):
        """根據 ID 取得影像資訊"""
        for img in self.metadata["images"]:
            if img["id"] == image_id:
                return img
        return None
    
    def search_images(self, keyword=None):
        """
        搜尋影像
        
        Args:
            keyword: 搜尋關鍵字（病患編號、姓名、MRN）
        
        Returns:
            list: 符合條件的影像列表
        """
        if not keyword:
            return self.get_all_images()
        
        results = []
        keyword_lower = keyword.lower()
        
        for img in self.metadata["images"]:
            if (keyword_lower in str(img.get("patient_id", "")).lower() or
                keyword_lower in str(img.get("patient_name", "")).lower() or
                keyword_lower in str(img.get("mrn", "")).lower()):
                results.append(img)
        
        return results
    
    def update_status(self, image_id, status):
        """
        更新影像狀態
        
        Args:
            image_id: 影像 ID
            status: 新狀態（local, uploaded, error）
        """
        for img in self.metadata["images"]:
            if img["id"] == image_id:
                img["status"] = status
                img["updated_at"] = datetime.now().isoformat()
                self._save_metadata()
                return True
        return False
    
    def remove_image(self, image_id):
        """刪除特定影像"""
        try:
            for i, img in enumerate(self.metadata["images"]):
                if img["id"] == image_id:
                    # 刪除檔案
                    file_path = Path(img["local_path"])
                    if file_path.exists():
                        os.remove(file_path)
                    
                    # 從 metadata 移除
                    self.metadata["images"].pop(i)
                    self._save_metadata()
                    
                    print(f"✅ 影像已刪除: {img['local_filename']}")
                    return True
            
            return False
            
        except Exception as e:
            print(f"❌ 刪除影像失敗: {e}")
            return False
    
    def clear_all(self):
        """清空所有暫存影像"""
        try:
            # 刪除所有影像檔案
            for img in self.metadata["images"]:
                file_path = Path(img["local_path"])
                if file_path.exists():
                    os.remove(file_path)
            
            # 清空 metadata
            self.metadata = {"images": []}
            self._save_metadata()
            
            print("✅ 所有暫存影像已清除")
            return True
            
        except Exception as e:
            print(f"❌ 清除暫存影像失敗: {e}")
            return False
    
    def cleanup(self):
        """清理並刪除整個暫存目錄"""
        try:
            if self.base_dir.exists():
                shutil.rmtree(self.base_dir)
                print("✅ 暫存目錄已完全刪除")
                return True
            return True
            
        except Exception as e:
            print(f"❌ 清理暫存目錄失敗: {e}")
            return False
    
    def get_stats(self):
        """取得統計資訊"""
        images = self.metadata.get("images", [])
        total_size = sum(img.get("file_size", 0) for img in images)
        
        return {
            "total_images": len(images),
            "total_size": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "local_count": sum(1 for img in images if img.get("status") == "local"),
            "uploaded_count": sum(1 for img in images if img.get("status") == "uploaded"),
        }


# 單例模式：全域唯一的管理器實例
_local_image_manager = None

def get_local_image_manager():
    """取得本地影像管理器的單例實例"""
    global _local_image_manager
    if _local_image_manager is None:
        _local_image_manager = LocalImageManager()
    return _local_image_manager