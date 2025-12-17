# -*- coding: utf-8 -*-
"""
api_client.py - 後端 API 連接模組（IRIS 資料庫整合版）
處理所有與 Server 的通訊
"""

import requests
import base64
from typing import Optional, Dict, List, Any
from .config import get_api_url, API_CONFIG


class APIClient:
    """後端 API Client（IRIS 資料庫整合版）"""
    
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
    # 使用者認證
    # ============================================================
    
    def login(self, username: str, password: str) -> Optional[Dict]:
        """
        使用者登入驗證（透過後端 API）
        
        Args:
            username: 使用者名稱
            password: 密碼
        
        Returns:
            {
                'status': 'success',
                'user': {
                    'id': 1,
                    'username': 'doctor1',
                    'full_name': '張心臟',
                    'email': 'doctor1@hospital.com',
                    'role_code': 'doctor',
                    'role_name': '醫師',
                    'clinical_dept_id': 1,
                    'clinical_dept_name': '心臟內科',
                    'employee_id': 'EMP001',
                    'phone': '02-1234-5678',
                    'is_active': True
                },
                'token': 'xxx' (optional)
            }
            
            失敗時:
            {
                'status': 'error',
                'error_code': 'user_not_found' | 'wrong_password' | 'account_disabled',
                'message': '錯誤訊息'
            }
        """
        try:
            login_data = {
                'username': username,
                'password': password
            }
            
            response = self.session.post(
                get_api_url('/login'),
                json=login_data,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                # 認證失敗
                try:
                    error_data = response.json()
                    return error_data
                except:
                    return {
                        'status': 'error',
                        'error_code': 'unauthorized',
                        'message': '認證失敗'
                    }
            else:
                print(f"登入失敗: HTTP {response.status_code}")
                return {
                    'status': 'error',
                    'error_code': 'server_error',
                    'message': f'伺服器錯誤 (HTTP {response.status_code})'
                }
            
        except Exception as e:
            print(f"登入請求失敗: {e}")
            return None
    
    def logout(self, user_id: int) -> Optional[Dict]:
        """
        使用者登出（記錄登出事件）
        
        Args:
            user_id: 使用者 ID
        
        Returns:
            登出結果
        """
        try:
            logout_data = {
                'user_id': user_id
            }
            
            response = self.session.post(
                get_api_url('/logout'),
                json=logout_data,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return response.json()
            
            return None
            
        except Exception as e:
            print(f"登出請求失敗: {e}")
            return None
    
    # ============================================================
    # 影像管理
    # ============================================================
    
    def list_images(self, patient_id: Optional[int] = None, 
                   clinical_dept_id: Optional[int] = None,
                   modality_dept_id: Optional[int] = None,
                   limit: int = 100, offset: int = 0) -> Optional[Dict]:
        """
        列出影像清單（支援 IRIS 資料庫科別篩選）
        
        Args:
            patient_id: 病患 ID（可選）
            clinical_dept_id: 臨床科別 ID（可選）
            modality_dept_id: 影像檢查科別 ID（可選）
            limit: 回傳數量限制
            offset: 偏移量
            
        Returns:
            包含影像列表的字典，失敗返回 None
            {
                'status': 'success',
                'images': [
                    {
                        'id': 1,
                        'patient_id': 1,
                        'patient_name': '王大明',
                        'mrn': 'MRN20240001',
                        'filename': 'chest_xray.jpg',
                        'file_type': 'image',
                        'mime_type': 'image/jpeg',
                        'file_size': 1234567,
                        'modality_dept_name': 'CR',
                        'clinical_dept_name': '心臟內科',
                        'uploader_name': '張醫師',
                        'uploaded_at': '2024-11-02 12:34:56',
                        'status': 'completed',
                        ...
                    },
                    ...
                ]
            }
        """
        try:
            params = {
                'limit': limit,
                'offset': offset
            }
            
            if patient_id is not None:
                params['patient_id'] = patient_id
            
            if clinical_dept_id is not None:
                params['clinical_dept_id'] = clinical_dept_id
            
            if modality_dept_id is not None:
                params['modality_dept_id'] = modality_dept_id
            
            response = self.session.get(
                get_api_url('/list_images'),
                params=params,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return response.json()
            
           # print(f"列出影像失敗: HTTP {response.status_code}")
            return None
            
        except Exception as e:
           # print(f"列出影像失敗: {e}")
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
        上傳加密影像（支援 IRIS 資料庫科別資訊）
        
        Args:
            transmission_package: 完整的加密傳輸封包
                包含 app_meta: {
                    'patient_id': int,
                    'uploader_id': int,
                    'filename': str,
                    'mime': str,
                    'modality_dept_code': str (可選),
                    'clinical_dept_code': str (可選),
                    ...
                }
            
        Returns:
            包含 image_id 的結果字典，失敗返回 None
            {
                'status': 'success',
                'image_id': 123,
                'message': '上傳成功'
            }
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
    '''
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
    '''
    
    def get_image_data(self, image_id: int) -> Optional[bytes]:
        """
        取得影像二進位資料（解密後）
        
        Args:
            image_id: 影像 ID
        
        Returns:
            影像二進位資料，失敗返回 None
        """
        try:
            response = self.session.get(
                get_api_url(f'/images/{image_id}/data'),
                timeout=30
            )
            
            if response.status_code == 200:
                return response.content
            
            print(f"取得影像資料失敗: HTTP {response.status_code}")
            return None
            
        except Exception as e:
            print(f"取得影像資料失敗: {e}")
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
    
    def delete_image(self, image_id: int) -> Optional[Dict]:
        """
        刪除影像
        
        Args:
            image_id: 影像 ID
        
        Returns:
            刪除結果，失敗返回 None
        """
        try:
            response = self.session.delete(
                get_api_url(f'/images/{image_id}'),
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return response.json()
            
            print(f"刪除影像失敗: HTTP {response.status_code}")
            return None
            
        except Exception as e:
            print(f"刪除影像失敗: {e}")
            return None
    
    # ============================================================
    # 病患管理（透過 Server API）- IRIS 資料庫整合
    # ============================================================
    
    def list_patients(self, keyword: str = "", clinical_dept_id: Optional[int] = None) -> Optional[Dict]:
        """
        列出病患清單（支援 IRIS 資料庫完整資訊）
        
        Args:
            keyword: 搜尋關鍵字（姓名、MRN、身分證）
            clinical_dept_id: 臨床科別 ID（可選）
            
        Returns:
            {
                'status': 'success',
                'patients': [
                    {
                        'id': 1,
                        'name': '王大明',
                        'mrn': 'MRN20240001',
                        'patient_id': 'PAT20240001',
                        'national_id': 'A123456789',
                        'birthday': '1975-03-15',
                        'gender': 'M',
                        'blood_type': 'A+',
                        'phone': '02-2345-6789',
                        'mobile': '0912-345-678',
                        'email': 'wang@email.com',
                        'address': '...',
                        'emergency_contact': '王小華',
                        'emergency_phone': '0923-456-789',
                        'doctor_name': '張心臟',
                        'clinical_dept_name': '心臟內科',
                        'insurance_id': 'INS001-2024',
                        'notes': '有高血壓病史',
                        ...
                    },
                    ...
                ]
            }
        """
        try:
            params = {}
            if keyword:
                params['keyword'] = keyword
            if clinical_dept_id is not None:
                params['clinical_dept_id'] = clinical_dept_id
            
            response = self.session.get(
                get_api_url('/patients'),
                params=params,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # 統一回傳格式（支援不同 Server 端格式）
                if isinstance(result, dict):
                    # 新格式: {'status': 'success', 'patients': [...]}
                    if 'patients' in result:
                        return result
                    # 舊格式: 直接是 list
                    elif isinstance(result, list):
                        return {'status': 'success', 'patients': result}
                elif isinstance(result, list):
                    # Server 直接回傳 list
                    return {'status': 'success', 'patients': result}
                
                return {'status': 'success', 'patients': []}
            
            print(f"列出病患失敗: HTTP {response.status_code}")
            return None
            
        except Exception as e:
            print(f"列出病患失敗: {e}")
            return None
    
    def get_patient(self, patient_id: int) -> Optional[Dict]:
        """
        獲取單一病患資訊（IRIS 資料庫完整資訊）
        
        Args:
            patient_id: 病患 ID
            
        Returns:
            病患完整資訊字典，失敗返回 None
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
        創建新病患（支援 IRIS 資料庫完整欄位）
        
        Args:
            patient_data: 病患資料
                {
                    'name': '姓名',
                    'mrn': '病歷號',
                    'patient_id': '病患ID',
                    'national_id': '身分證',
                    'birthday': '生日 (YYYY-MM-DD)',
                    'gender': 'M/F/O',
                    'blood_type': '血型',
                    'phone': '電話',
                    'mobile': '手機',
                    'email': 'Email',
                    'address': '地址',
                    'emergency_contact': '緊急聯絡人',
                    'emergency_phone': '緊急電話',
                    'insurance_id': '保險ID',
                    'notes': '備註',
                    ...
                }
            
        Returns:
            創建結果，包含新病患 ID
            {
                'status': 'success',
                'patient_id': 123
            }
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
    
    # 向下相容的別名
    def add_patient(self, patient_data: Dict) -> Optional[Dict]:
        """add_patient 是 create_patient 的別名（向下相容）"""
        return self.create_patient(patient_data)
    
    def update_patient(self, patient_id: int, patient_data: Dict) -> Optional[Dict]:
        """
        更新病患資料
        
        Args:
            patient_id: 病患 ID
            patient_data: 要更新的病患資料
        
        Returns:
            更新結果，失敗返回 None
        """
        try:
            response = self.session.put(
                get_api_url(f'/patients/{patient_id}'),
                json=patient_data,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return response.json()
            
            print(f"更新病患失敗: HTTP {response.status_code}")
            return None
            
        except Exception as e:
            print(f"更新病患失敗: {e}")
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
    # IRIS 資料庫專屬：科別管理
    # ============================================================
    
    def list_clinical_departments(self) -> Optional[Dict]:
        """
        列出臨床科別
        
        Returns:
            {
                'status': 'success',
                'departments': [
                    {
                        'id': 1,
                        'code': 'CARD',
                        'name': '心臟內科',
                        'description': '心血管疾病診治',
                        'head_doctor': '張心臟醫師',
                        'phone': '02-1234-5678',
                        'location': '3樓A區',
                        ...
                    },
                    ...
                ]
            }
        """
        try:
            response = self.session.get(
                get_api_url('/departments/clinical'),
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return response.json()
            
            print(f"列出臨床科別失敗: HTTP {response.status_code}")
            return None
            
        except Exception as e:
            print(f"列出臨床科別失敗: {e}")
            return None
    
    def list_modality_departments(self) -> Optional[Dict]:
        """
        列出影像檢查科別
        
        Returns:
            {
                'status': 'success',
                'departments': [
                    {
                        'id': 1,
                        'code': 'CT',
                        'name': '電腦斷層掃描',
                        'description': 'Computed Tomography',
                        ...
                    },
                    ...
                ]
            }
        """
        try:
            response = self.session.get(
                get_api_url('/departments/modality'),
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return response.json()
            
            print(f"列出影像檢查科別失敗: HTTP {response.status_code}")
            return None
            
        except Exception as e:
            print(f"列出影像檢查科別失敗: {e}")
            return None
    
    # ============================================================
    # IRIS 資料庫專屬：使用者管理
    # ============================================================
    
    def list_users(self, role_id: Optional[int] = None) -> Optional[Dict]:
        """
        列出使用者
        
        Args:
            role_id: 角色 ID（可選）
        
        Returns:
            使用者列表
        """
        try:
            params = {}
            if role_id is not None:
                params['role_id'] = role_id
            
            response = self.session.get(
                get_api_url('/users'),
                params=params,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return response.json()
            
            return None
            
        except Exception as e:
            print(f"列出使用者失敗: {e}")
            return None
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        """
        取得使用者資訊
        
        Args:
            user_id: 使用者 ID
        
        Returns:
            使用者資訊
        """
        try:
            response = self.session.get(
                get_api_url(f'/users/{user_id}'),
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return response.json()
            
            return None
            
        except Exception as e:
            print(f"取得使用者資訊失敗: {e}")
            return None
    
    # ============================================================
    # IRIS 資料庫專屬：審計日誌
    # ============================================================
    
    def list_audit_logs(self, user_id: Optional[int] = None, 
                       action: Optional[str] = None,
                       limit: int = 100) -> Optional[Dict]:
        """
        列出審計日誌
        
        Args:
            user_id: 使用者 ID（可選）
            action: 動作類型（可選）
            limit: 限制筆數
        
        Returns:
            審計日誌列表
        """
        try:
            params = {'limit': limit}
            if user_id is not None:
                params['user_id'] = user_id
            if action:
                params['action'] = action
            
            response = self.session.get(
                get_api_url('/audit_logs'),
                params=params,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return response.json()
            
            return None
            
        except Exception as e:
            print(f"列出審計日誌失敗: {e}")
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
    
    def get_statistics(self) -> Optional[Dict]:
        """
        取得系統統計資訊（IRIS 資料庫版本）
        
        Returns:
            {
                'status': 'success',
                'statistics': {
                    'total_patients': 100,
                    'total_images': 500,
                    'total_users': 20,
                    'images_today': 10,
                    'images_this_week': 50,
                    'images_this_month': 200,
                    'by_modality': {...},
                    'by_clinical_dept': {...},
                    ...
                }
            }
        """
        try:
            response = self.session.get(
                get_api_url('/statistics'),
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return response.json()
            
            return None
            
        except Exception as e:
            print(f"取得統計資訊失敗: {e}")
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
    def get_image_full(self, image_id):
        """
        獲取完整影像資料
        
        Args:
            image_id: 影像 ID
            
        Returns:
            bytes: 影像資料，失敗則回傳 None
        """
        try:
            print(f"📥 請求完整影像: image_id={image_id}")
            
            response = requests.post(
                get_api_url('/get_image'),
                json={"image_id": image_id},
                timeout=30
            )
            
            if response.status_code == 200:
                print(f"✅ 影像下載成功: {len(response.content)} bytes")
                return response.content
            else:
                print(f"❌ 獲取影像失敗: HTTP {response.status_code}")
                error_text = response.text[:200] if response.text else "No error message"
                print(f"   錯誤訊息: {error_text}")
                return None
                
        except requests.exceptions.Timeout:
            print(f"❌ 獲取影像逾時")
            return None
        except requests.exceptions.RequestException as e:
            print(f"❌ 網路請求錯誤: {e}")
            return None
        except Exception as e:
            print(f"❌ 獲取影像錯誤: {e}")
            import traceback
            traceback.print_exc()
            return None


# 全域 API Client 實例
_api_client = None

def get_api_client() -> APIClient:
    """獲取 API Client 單例"""
    global _api_client
    if _api_client is None:
        _api_client = APIClient()
    return _api_client