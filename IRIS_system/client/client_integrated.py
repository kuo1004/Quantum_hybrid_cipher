#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
client_integrated.py - IRIS 醫療影像傳輸系統 Client 端
整合 Sender, Receiver 的完整 CLI 介面

功能:
1. 上傳加密影像到 Server
2. 從 Server 下載影像
3. 列出 Server 上的影像
4. CA 憑證管理
"""

import os
import sys
import time
import json
import base64
import requests
from datetime import datetime

# 本地模組
from sender import Sender
from receiver import Receiver
from certificate_authority import CertificateAuthority


class MedicalImageClient:
    """醫療影像傳輸 Client"""
    
    def __init__(self, client_id, ca_host, ca_port, server_host, server_port):
        self.client_id = client_id
        self.ca_host = ca_host
        self.ca_port = ca_port
        self.server_host = server_host
        self.server_port = server_port
        
        self.sender = None
        self.receiver = None
        self.ca = None
        
        # 本地目錄
        self.input_dir = ".medicalimages/input"
        self.output_dir = ".medicalimages/output"
        self.received_dir = ".medicalimages/received"
        
        for directory in [self.input_dir, self.output_dir, self.received_dir]:
            os.makedirs(directory, exist_ok=True)
    
    def init_client(self):
        """初始化 Client"""
        print("="*70)
        print("🏥 IRIS 醫療影像傳輸系統 - Client 端")
        print("="*70)
        print(f"Client ID: {self.client_id}")
        print(f"CA Server: {self.ca_host}:{self.ca_port}")
        print(f"Hospital Server: {self.server_host}:{self.server_port}")
        print("="*70)
        
        # 創建 Sender 和 Receiver
        print("\n📋 步驟 1: 創建 Sender 和 Receiver")
        self.sender = Sender(f"{self.client_id}_Sender")
        self.receiver = Receiver(f"{self.client_id}_Receiver")
        print("✅ 創建完成")
        
        # 連接 CA
        print("\n📋 步驟 2: 連接憑證機構 (CA)")
        
        if self._connect_to_ca():
            print(f"✅ 連接到 CA: {self.ca_host}:{self.ca_port}")
            
            ca_public_key_pem = self._get_ca_public_key()
            if not ca_public_key_pem:
                print("❌ 無法獲取 CA 公鑰")
                return False
            
            self.sender.ca_public_key_pem = ca_public_key_pem
            self.receiver.ca_public_key_pem = ca_public_key_pem
            
            self.sender.certificate = self._register_with_ca(self.sender)
            self.receiver.certificate = self._register_with_ca(self.receiver)
            
            if not self.sender.certificate or not self.receiver.certificate:
                print("❌ CA 註冊失敗")
                return False
                
        else:
            print("⚠️ 無法連接 CA，創建本地 CA")
            self.ca = CertificateAuthority("Local_Client_CA")
            self.sender.register_with_ca(self.ca)
            self.receiver.register_with_ca(self.ca)
        
        # 測試 Server
        print("\n📋 步驟 3: 測試 Hospital Server")
        if self._test_server_connection():
            print(f"✅ Server 連接正常")
        else:
            print(f"⚠️ 無法連接 Server")
        
        print("\n" + "="*70)
        print("✅ Client 初始化完成")
        print("="*70 + "\n")
        
        return True
    
    def _connect_to_ca(self):
        """連接 CA"""
        try:
            response = requests.get(
                f"http://{self.ca_host}:{self.ca_port}/public_key",
                timeout=5
            )
            return response.status_code == 200
        except:
            return False
    
    def _get_ca_public_key(self):
        """獲取 CA 公鑰"""
        try:
            response = requests.get(
                f"http://{self.ca_host}:{self.ca_port}/public_key",
                timeout=5
            )
            if response.status_code == 200:
                return response.content
            return None
        except:
            return None
    
    def _register_with_ca(self, entity):
        """向 CA 註冊"""
        try:
            public_key_pem = entity.get_public_key_pem().decode('utf-8')
            kem_public_key_b64 = base64.b64encode(entity.kem_public_key).decode('utf-8')
            
            party_id = entity.sender_id if hasattr(entity, 'sender_id') else entity.receiver_id
            
            register_data = {
                "party_id": party_id,
                "public_key_pem": public_key_pem,
                "kem_public_key_b64": kem_public_key_b64
            }
            
            response = requests.post(
                f"http://{self.ca_host}:{self.ca_port}/register",
                json=register_data,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code == 200:
                print(f"   ✅ 註冊成功: {party_id}")
                return response.json()
            else:
                print(f"   ❌ 註冊失敗: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            print(f"   ❌ 註冊失敗: {e}")
            return None
    
    def _test_server_connection(self):
        """測試 Server 連接"""
        try:
            response = requests.get(
                f"http://{self.server_host}:{self.server_port}/health",
                timeout=5
            )
            return response.status_code == 200
        except:
            return False
    
    def upload_image(self, image_path, patient_id, uploader_id):
        """上傳影像"""
        try:
            print(f"\n{'='*70}")
            print(f"📤 上傳影像")
            print(f"{'='*70}")
            print(f"檔案: {image_path}")
            print(f"病患 ID: {patient_id}")
            
            if not os.path.exists(image_path):
                print(f"❌ 檔案不存在")
                return False
            
            # 讀取影像
            print("\n📂 讀取影像...")
            with open(image_path, 'rb') as f:
                imagedata = f.read()
            print(f"✅ {len(imagedata)} bytes")
            
            # 獲取 Server 憑證
            print("\n🔐 獲取 Server 憑證...")
            server_certificate = self._get_server_certificate()
            if not server_certificate:
                print("❌ 無法獲取 Server 憑證")
                return False
            print("✅ 憑證獲取成功")
            
            # 準備元資料
            app_meta = {
                "patient_id": patient_id,
                "uploader_id": uploader_id,
                "filename": os.path.basename(image_path),
                "mime": self._get_mime_type(image_path),
                "upload_time": time.time()
            }
            
            # 簽章
            print("\n✍️ 簽署...")
            from signature_utils import sign_bytes
            signature = sign_bytes(self.sender.private_key, imagedata)
            
            # 加密
            print("\n🔒 加密...")
            transmission_package = self.sender.encrypt_and_prepare_transmission(
                plaintext_bytes=imagedata,
                receiver_certificate=server_certificate,
                signature=signature,
                app_meta=app_meta
            )
            
            # 上傳
            print("\n📡 傳送...")
            response = requests.post(
                f"http://{self.server_host}:{self.server_port}/upload",
                json={"transmission_package": transmission_package},
                headers={"Content-Type": "application/json"},
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"\n✅ 上傳成功")
                print(f"Image ID: {result.get('image_id')}\n")
                return True
            else:
                print(f"\n❌ 失敗: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            print(f"\n❌ 上傳失敗: {e}")
            return False
    
    def download_image(self, image_id, output_path=None):
        """下載影像"""
        try:
            print(f"\n{'='*70}")
            print(f"📥 下載影像")
            print(f"{'='*70}")
            print(f"Image ID: {image_id}")
            
            # 請求下載
            print("\n📡 發送請求...")
            response = requests.post(
                f"http://{self.server_host}:{self.server_port}/request_image",
                json={
                    "image_id": image_id,
                    "requester_certificate": self.receiver.certificate
                },
                headers={"Content-Type": "application/json"},
                timeout=60
            )
            
            if response.status_code != 200:
                print(f"❌ 失敗: HTTP {response.status_code}")
                return None
            
            result = response.json()
            transmission_package = result['transmission_package']
            print("✅ 接收到封包")
            
            # 設定輸出路徑
            if not output_path:
                output_path = os.path.join(
                    self.received_dir,
                    f"image_{image_id}_{int(time.time())}.dat"
                )
            
            # 解密
            print("\n🔓 解密...")
            decrypted_result = self.receiver.receive_and_decrypt(
                transmission_package,
                output_file_path=output_path,
                ca_public_key_pem=self.receiver.ca_public_key_pem
            )
            
            if not decrypted_result:
                print("❌ 解密失敗")
                return None
            
            plaintext, app_meta = decrypted_result
            
            print(f"\n✅ 下載成功")
            print(f"檔案: {output_path}")
            print(f"大小: {len(plaintext)} bytes\n")
            
            return output_path
            
        except Exception as e:
            print(f"\n❌ 下載失敗: {e}")
            return None
    
    def list_images(self, patient_id=None):
        """列出影像"""
        try:
            print(f"\n{'='*70}")
            print(f"📋 影像列表")
            print(f"{'='*70}")
            
            url = f"http://{self.server_host}:{self.server_port}/list_images"
            if patient_id:
                url += f"?patient_id={patient_id}"
            
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                print(f"❌ 失敗: HTTP {response.status_code}")
                return []
            
            result = response.json()
            images = result.get('images', [])
            
            print(f"\n找到 {len(images)} 張影像:")
            print(f"{'-'*70}")
            
            for img in images:
                print(f"ID: {img['id']:4d} | "
                      f"檔名: {img['filename']:30s} | "
                      f"病患: {img['patient_id']:3d} | "
                      f"時間: {img['uploaded_at']}")
            
            print(f"{'-'*70}\n")
            
            return images
            
        except Exception as e:
            print(f"❌ 失敗: {e}")
            return []
    
    def get_server_stats(self):
        """統計資訊"""
        try:
            print(f"\n{'='*70}")
            print(f"📊 Server 統計")
            print(f"{'='*70}")
            
            response = requests.get(
                f"http://{self.server_host}:{self.server_port}/stats",
                timeout=10
            )
            
            if response.status_code != 200:
                print(f"❌ 失敗: HTTP {response.status_code}")
                return None
            
            result = response.json()
            stats = result.get('statistics', {})
            
            print(f"總影像數: {stats.get('total_images', 0)}")
            print(f"總病患數: {stats.get('total_patients', 0)}")
            print(f"{'='*70}\n")
            
            return stats
            
        except Exception as e:
            print(f"❌ 失敗: {e}")
            return None
    
    def _get_server_certificate(self):
        """獲取 Server 憑證"""
        try:
            # 嘗試從 Server 獲取
            response = requests.get(
                f"http://{self.server_host}:{self.server_port}/get_certificate/Hospital_Server_Receiver",
                timeout=5
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('certificate')
            
            # 嘗試從 CA 獲取
            response = requests.get(
                f"http://{self.ca_host}:{self.ca_port}/get_certificate/Hospital_Server_Receiver",
                timeout=5
            )
            
            if response.status_code == 200:
                return response.json()
            
            return None
            
        except:
            return None
    
    def _get_mime_type(self, file_path):
        """判斷 MIME 類型"""
        ext = os.path.splitext(file_path)[1].lower()
        
        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.dcm': 'application/dicom',
            '.dat': 'application/octet-stream'
        }
        
        return mime_types.get(ext, 'application/octet-stream')
    
    def interactive_menu(self):
        """互動式選單"""
        while True:
            print("\n" + "="*70)
            print("🏥 IRIS 醫療影像傳輸系統 - Client 端")
            print("="*70)
            print(f"Client ID: {self.client_id}")
            print(f"Server: {self.server_host}:{self.server_port}")
            print("="*70)
            print("\n請選擇操作:")
            print("  1. 上傳影像")
            print("  2. 下載影像")
            print("  3. 列出影像")
            print("  4. 統計資訊")
            print("  5. 測試連接")
            print("  0. 離開")
            print()
            
            try:
                choice = input("請輸入選項 (0-5): ").strip()
                
                if choice == '0':
                    print("\n👋 再見！")
                    break
                
                elif choice == '1':
                    image_path = input("\n影像路徑: ").strip()
                    patient_id = input("病患 ID: ").strip()
                    uploader_id = input("上傳者 ID: ").strip()
                    
                    if image_path and patient_id and uploader_id:
                        self.upload_image(image_path, int(patient_id), int(uploader_id))
                    else:
                        print("❌ 參數不完整")
                
                elif choice == '2':
                    image_id = input("\n影像 ID: ").strip()
                    if image_id:
                        self.download_image(int(image_id))
                    else:
                        print("❌ 請輸入影像 ID")
                
                elif choice == '3':
                    patient_id = input("\n病患 ID (留空=全部): ").strip()
                    if patient_id:
                        self.list_images(int(patient_id))
                    else:
                        self.list_images()
                
                elif choice == '4':
                    self.get_server_stats()
                
                elif choice == '5':
                    print("\n🔍 測試連接...")
                    if self._test_server_connection():
                        print("✅ Server 正常")
                    else:
                        print("❌ Server 連接失敗")
                
                else:
                    print("❌ 無效選項")
                
            except KeyboardInterrupt:
                print("\n\n👋 再見！")
                break
            except Exception as e:
                print(f"\n❌ 錯誤: {e}")


def main():
    """主程式"""
    
    if len(sys.argv) < 6:
        print("使用方式: python client_integrated.py <client_id> <ca_host> <ca_port> <server_host> <server_port>")
        print("範例: python client_integrated.py DrWang localhost 8001 localhost 8200")
        sys.exit(1)
    
    client_id = sys.argv[1]
    ca_host = sys.argv[2]
    ca_port = int(sys.argv[3])
    server_host = sys.argv[4]
    server_port = int(sys.argv[5])
    
    client = MedicalImageClient(client_id, ca_host, ca_port, server_host, server_port)
    
    if not client.init_client():
        print("\n❌ Client 初始化失敗")
        sys.exit(1)
    
    try:
        client.interactive_menu()
    except KeyboardInterrupt:
        print("\n\n👋 程式結束")


if __name__ == "__main__":
    main()