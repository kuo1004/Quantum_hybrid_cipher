# -*- coding: utf-8 -*-
"""
api_client.py - 後端 API 連接模組
處理所有與 Server 的通訊
"""

import requests
import base64
from typing import Optional, Dict, List, Any
from .config import get_api_url, API_CONFIG


class APIClient:
    """後端 API Client"""
    
    def __init__(self):
        self.timeout = API_CONFIG['TIMEOUT']
        self.session = requests.Session()
    
    # ============================================================
    # 健康檢查
    # ============================================================
    
    def health_check(self) -> Optional[Dict]:
        """檢查 Server 健康狀態"""
        try:
            response = self.session.get(
                get_api_url('/health'),
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return response.json()
            return None
            
        except Exception as e:
            print(f"健康檢查失敗: {e}")
            return None
    
    # ============================================================
    # 影像管理
    # ============================================================
    
    def list_images(self, patient_id: Optional[int] = None, 
                   limit: int = 100, offset: int = 0) -> Optional[Dict]:
        """
        列出影像清單
        
        Args:
            patient_id: 病患 ID（可選）
            limit: 回傳數量限制
            offset: 偏移量
            
        Returns:
            包含影像列表的字典，失敗返回 None
        """
        try:
            params = {
                'limit': limit,
                'offset': offset
            }
            
            if patient_id is not None:
                params['patient_id'] = patient_id
            
            response = self.session.get(
                get_api_url('/list_images'),
                params=params,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return response.json()
            
            print(f"列出影像失敗: HTTP {response.status_code}")
            return None
            
        except Exception as e:
            print(f"列出影像失敗: {e}")
            return None
    
    def download_image(self, image_id: int, requester_certificate: Dict) -> Optional[bytes]:
        """
        下載影像
        
        Args:
            image_id: 影像 ID
            requester_certificate: 請求者憑證
            
        Returns:
            影像二進制數據，失敗返回 None
        """
        try:
            request_data = {
                'image_id': image_id,
                'requester_certificate': requester_certificate
            }
            
            response = self.session.post(
                get_api_url('/request_image'),
                json=request_data,
                timeout=60  # 下載可能需要較長時間
            )
            
            if response.status_code != 200:
                print(f"下載影像失敗: HTTP {response.status_code}")
                return None
            
            result = response.json()
            transmission_package = result.get('transmission_package')
            
            if not transmission_package:
                print("回應中缺少 transmission_package")
                return None
            
            return transmission_package
            
        except Exception as e:
            print(f"下載影像失敗: {e}")
            return None
    
    def upload_image(self, transmission_package: Dict) -> Optional[Dict]:
        """
        上傳加密影像
        
        Args:
            transmission_package: 完整的加密傳輸封包
            
        Returns:
            包含 image_id 的結果字典，失敗返回 None
        """
        try:
            request_data = {
                'transmission_package': transmission_package
            }
            
            response = self.session.post(
                get_api_url('/upload'),
                json=request_data,
                headers={'Content-Type': 'application/json'},
                timeout=60  # 上傳可能需要較長時間
            )
            
            if response.status_code == 200:
                return response.json()
            
            print(f"上傳影像失敗: HTTP {response.status_code}")
            print(f"回應: {response.text}")
            return None
            
        except Exception as e:
            print(f"上傳影像失敗: {e}")
            return None
    
    # ============================================================
    # 新增：影像獲取功能（用於前端顯示）
    # ============================================================
    
    def get_image_thumbnail(self, image_id: int) -> Optional[bytes]:
        """
        獲取影像縮圖（走加密通道）
        
        Args:
            image_id: 影像 ID
        
        Returns:
            縮圖的二進位資料（JPEG 格式），失敗返回 None
        """
        try:
            request_data = {
                'image_id': image_id
            }
            
            response = self.session.post(
                get_api_url('/get_thumbnail'),
                json=request_data,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get('status') == 'success':
                    # Base64 解碼
                    thumbnail_b64 = result.get('thumbnail')
                    if thumbnail_b64:
                        return base64.b64decode(thumbnail_b64)
            else:
                print(f"獲取縮圖失敗: HTTP {response.status_code}")
            
            return None
            
        except Exception as e:
            print(f"獲取縮圖失敗: {e}")
            return None
    
    def get_image_full(self, image_id: int) -> Optional[Dict]:
        """
        獲取完整影像（走加密通道）
        
        Args:
            image_id: 影像 ID
        
        Returns:
            {
                "status": "success",
                "image_data": str (Base64),
                "mime": str,
                "filename": str
            }
            失敗返回 None
        """
        try:
            request_data = {
                'image_id': image_id
            }
            
            response = self.session.post(
                get_api_url('/get_image'),
                json=request_data,
                timeout=30  # 完整影像可能較大
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get('status') == 'success':
                    return result
            else:
                print(f"獲取完整影像失敗: HTTP {response.status_code}")
            
            return None
            
        except Exception as e:
            print(f"獲取完整影像失敗: {e}")
            return None
    
    def get_patient_images(self, patient_id: int, include_thumbnails: bool = True) -> Optional[Dict]:
        """
        獲取病患的所有影像（包含縮圖）
        
        Args:
            patient_id: 病患 ID
            include_thumbnails: 是否包含縮圖（預設 True）
        
        Returns:
            {
                "status": "success",
                "patient_id": int,
                "patient_name": str,
                "patient_mrn": str,
                "images": [
                    {
                        "id": int,
                        "filename": str,
                        "mime": str,
                        "uploaded_at": str,
                        "thumbnail": str (Base64, optional)
                    }
                ],
                "count": int
            }
            失敗返回 None
        """
        try:
            params = {
                'patient_id': patient_id,
                'include_thumbnails': 'true' if include_thumbnails else 'false'
            }
            
            response = self.session.get(
                get_api_url('/get_patient_images'),
                params=params,
                timeout=self.timeout * 2  # 可能需要較長時間
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get('status') == 'success':
                    return result
            else:
                print(f"獲取病患影像失敗: HTTP {response.status_code}")
            
            return None
            
        except Exception as e:
            print(f"獲取病患影像失敗: {e}")
            return None
    
    # ============================================================
    # 病患管理（透過 Server API）
    # ============================================================
    
    def list_patients(self, keyword: str = "") -> List[Dict]:
        """
        列出病患清單
        
        Args:
            keyword: 搜尋關鍵字
            
        Returns:
            病患列表
        """
        try:
            params = {}
            if keyword:
                params['keyword'] = keyword
            
            response = self.session.get(
                get_api_url('/patients'),
                params=params,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Server 直接回傳 list，不是包在物件中
                if isinstance(result, list):
                    return result
                
                # 如果是物件格式（向下相容）
                return result.get('patients', [])
            
            print(f"列出病患失敗: HTTP {response.status_code}")
            return []
            
        except Exception as e:
            print(f"列出病患失敗: {e}")
            return []
    
    def get_patient(self, patient_id: int) -> Optional[Dict]:
        """
        獲取單一病患資訊
        
        Args:
            patient_id: 病患 ID
            
        Returns:
            病患資訊字典，失敗返回 None
        """
        try:
            response = self.session.get(
                get_api_url(f'/patients/{patient_id}'),
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Server 直接回傳病患物件，不是包在 'patient' 中
                if isinstance(result, dict) and 'id' in result:
                    return result
                
                # 如果是包裝格式（向下相容）
                return result.get('patient')
            
            return None
            
        except Exception as e:
            print(f"獲取病患資訊失敗: {e}")
            return None
    
    def create_patient(self, patient_data: Dict) -> Optional[Dict]:
        """
        創建新病患
        
        Args:
            patient_data: 病患資料
            
        Returns:
            創建結果，包含新病患 ID
        """
        try:
            response = self.session.post(
                get_api_url('/patients'),
                json=patient_data,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return response.json()
            
            print(f"創建病患失敗: HTTP {response.status_code}")
            return None
            
        except Exception as e:
            print(f"創建病患失敗: {e}")
            return None
    
    def delete_patient(self, patient_id: int) -> Optional[Dict]:
        """
        刪除病患
        
        Args:
            patient_id: 病患 ID
        
        Returns:
            刪除結果，失敗返回 None
        """
        try:
            response = self.session.delete(
                get_api_url(f'/patients/{patient_id}'),
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return response.json()
            
            print(f"刪除病患失敗: HTTP {response.status_code}")
            return None
            
        except Exception as e:
            print(f"刪除病患失敗: {e}")
            return None
    
    # ============================================================
    # 統計資訊
    # ============================================================
    
    def get_stats(self) -> Optional[Dict]:
        """獲取系統統計資訊"""
        try:
            response = self.session.get(
                get_api_url('/stats'),
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('statistics')
            
            return None
            
        except Exception as e:
            print(f"獲取統計失敗: {e}")
            return None
    
    # ============================================================
    # 憑證管理
    # ============================================================
    
    def get_server_certificate(self, party_id: str = "Hospital_Server_Receiver") -> Optional[Dict]:
        """
        獲取 Server 憑證
        
        Args:
            party_id: 參與方 ID
            
        Returns:
            憑證字典，失敗返回 None
        """
        try:
            response = self.session.get(
                get_api_url(f'/get_certificate/{party_id}'),
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('certificate')
            
            return None
            
        except Exception as e:
            print(f"獲取 Server 憑證失敗: {e}")
            return None
    
    def close(self):
        """關閉連接"""
        self.session.close()


# 全域 API Client 實例
_api_client = None

def get_api_client() -> APIClient:
    """獲取 API Client 單例"""
    global _api_client
    if _api_client is None:
        _api_client = APIClient()
    return _api_client