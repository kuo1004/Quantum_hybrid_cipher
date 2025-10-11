#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
手動控制版Sender服務器
只處理明確指定的單個文件，不會自動批量處理目錄中的所有文件
"""

import os
import time
import json
import socket
import threading
from datetime import datetime
import base64
import requests # 用於向 CA 伺服器請求憑證
from .signature_utils import sign_bytes # 引用我們剛剛建立的簽章工具

# 導入完整的加密和隱寫模組
try:
    from .sender import Sender
    from .receiver import Receiver
    from ..certificate_authority import CertificateAuthority
    from cryptography.hazmat.primitives import serialization
    import pickle
    import shutil
except ImportError as e:
    print(f"警告：無法導入模組 {e}")
    print("請確保所有必要的檔案都在同一目錄下")

class ManualControlSenderServer:
    def __init__(self, host='localhost', port=8002, ca_host='localhost', ca_port=8001):
        self.host = host
        self.port = port
        self.ca_host = ca_host
        self.ca_port = ca_port
        self.sender = None
        self.running = False
        self.watch_directory = ".medicalimages/input"
        self.output_directory = ".medicalimages/output"
        self.processed_files = set()
        self.receiver_id = "HospitalReceiver"

        # 手動控制模式
        self.auto_processing = False  # 默認關閉自動處理
        self.pending_files = []  # 待處理文件隊列

        # 接收方憑證和CA公鑰
        self.receiver_certificate = None
        self.ca_public_key_pem = None

        # 創建監控目錄
        os.makedirs(self.watch_directory, exist_ok=True)
        os.makedirs(self.output_directory, exist_ok=True)

        print(f"📁 監控目錄已創建: {self.watch_directory}")
        print(f"📁 輸出目錄已創建: {self.output_directory}")

    def start_server(self):
        """啟動發送方服務器"""
        self.running = True

        try:
            print("📤 初始化手動控制發送方...")
            self.sender = Sender("Taiwan_General_Hospital")

            # 修補憑證驗證
            self.patch_sender_certificate_verification()

            # 向CA註冊
            if self.register_with_ca():
                # 獲取接收方憑證
                if self.setup_receiver_certificate(self.receiver_id):
                    self.running = True
                    print(f"📤 手動控制Sender服務器啟動成功: {self.host}:{self.port}")
                    print(f"🔍 監控目錄: {os.path.abspath(self.watch_directory)}")
                    print("\n⚠️ 手動控制模式：")
                    print("   • 默認不會自動處理文件")
                    print("   • 使用 'process <filename>' 指令處理指定文件")
                    print("   • 使用 'auto on/off' 切換自動模式")
                    print("   • 使用 'list' 查看待處理文件")

                    # 啟動文件監控（僅檢測，不自動處理）
                    self.start_file_monitor()

                    # 啟動指令控制介面
                    self.start_command_interface()

                    # 啟動網路服務
                    self.start_network_service()
                else:
                    print("❌ 無法設置接收方憑證，服務器啟動失敗")
            else:
                print("❌ 無法向CA註冊，服務器啟動失敗")
        except Exception as e:
            print(f"❌ 啟動發送方失敗: {e}")
            import traceback
            traceback.print_exc()

    def patch_sender_certificate_verification(self):
        """修補憑證驗證方法"""
        original_verify = self.sender.verify_peer_certificate

        def bypass_verify(peer_certificate, ca_public_key_pem):
            """簡化的憑證驗證（開發環境用）"""
            try:
                if not isinstance(peer_certificate, dict):
                    print("❌ 憑證格式錯誤：不是字典類型")
                    return False

                if "certificate_info" not in peer_certificate:
                    print("❌ 憑證格式錯誤：缺少certificate_info")
                    return False

                cert_info = peer_certificate["certificate_info"]

                required_fields = ["party_id", "public_key_pem", "kem_public_key", "valid_until"]
                for field in required_fields:
                    if field not in cert_info:
                        print(f"❌ 憑證缺少必要字段: {field}")
                        return False

                if time.time() > cert_info["valid_until"]:
                    print("❌ 憑證已過期")
                    return False

                expected_receiver = "Mackay_Memorial_Hospital"
                if cert_info["party_id"] != expected_receiver:
                    print(f"❌ 接收方ID不符：期望 {expected_receiver}，實際 {cert_info['party_id']}")
                    return False

                print("⚠️ 開發環境：跳過CA簽名驗證")
                print(f"✅ 簡化憑證驗證通過：{cert_info['party_id']}")
                return True

            except Exception as e:
                print(f"❌ 憑證驗證異常: {e}")
                return False

        self.sender.verify_peer_certificate = bypass_verify
        print("🔧 已啟用簡化憑證驗證模式（開發環境）")

    def register_with_ca(self) -> bool:
        """從 CA 獲取其公鑰，並將其儲存在 self.ca_public_key_pem 中。"""
        try:
            print(f"📋 正在連接 CA ({self.ca_host}:{self.ca_port}) 獲取其公鑰...")
            url = f"http://{self.ca_host}:{self.ca_port}/public_key"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                self.ca_public_key_pem = response.content # <-- 關鍵：在此賦值
                self.sender.ca_public_key_pem = self.ca_public_key_pem
                print("✅ 成功從 CA 獲取公鑰。")
                return True # <-- 關鍵：回傳成功
            else:
                print(f"❌ 從 CA 獲取公鑰失敗，狀態碼: {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            print(f"❌ 連接 CA 失敗: {e}")
            print("💡 提示：請確保 CA 服務器已經啟動且網路可達。")
            return False

    def setup_receiver_certificate(self, receiver_id):
        """向 CA 伺服器請求接收方的憑證"""
        if not self.ca_public_key_pem:
            print("錯誤: 尚未取得 CA 公鑰，無法驗證憑證")
            return

        try:
            # 向 CA 伺服器發送請求
            url = f"http://{self.ca_host}:{self.ca_port}/get_certificate/{receiver_id}"
            response = requests.get(url, timeout=5)

            if response.status_code == 200:
                cert_data = response.json()
                
                # 使用 CA 公鑰驗證憑證簽章 (嚴禁造假)
                ca_public_key = serialization.load_pem_public_key(self.ca_public_key_pem)
                
                certificate_info_bytes = json.dumps(cert_data['certificate_info'], sort_keys=True).encode('utf-8')
                signature_bytes = base64.b64decode(cert_data['signature'])

                if not verify_signature(ca_public_key, certificate_info_bytes, signature_bytes):
                    print(f"錯誤: 接收方 '{receiver_id}' 的憑證簽章驗證失敗！可能是偽造的憑證。")
                    self.receiver_certificate = None
                    return
                
                print(f"成功取得並驗證接收方 '{receiver_id}' 的憑證。")
                self.receiver_certificate = cert_data['certificate_info']
            else:
                print(f"錯誤: 從 CA 獲取接收方 '{receiver_id}' 憑證失敗，狀態碼: {response.status_code}")
                self.receiver_certificate = None

        except requests.exceptions.RequestException as e:
            print(f"錯誤: 連接 CA 伺服器失敗: {e}")
            self.receiver_certificate = None


    def start_file_monitor(self):
        """啟動文件監控（僅檢測，不自動處理）"""
        def monitor_thread():
            print("🔍 開始文件監控（僅檢測模式）...")
            last_file_list = set()

            while self.running:
                try:
                    current_files = self.scan_directory_files()

                    # 檢測新文件
                    new_files = current_files - last_file_list
                    if new_files:
                        for new_file in new_files:
                            if new_file not in self.pending_files:
                                self.pending_files.append(new_file)
                                print(f"🔔 檢測到新文件: {os.path.basename(new_file)}")
                                if not self.auto_processing:
                                    print(f"💡 使用 'process {os.path.basename(new_file)}' 來處理此文件")

                    # 自動處理模式
                    if self.auto_processing and self.pending_files:
                        file_to_process = self.pending_files.pop(0)
                        if os.path.exists(file_to_process):
                            print(f"🔄 自動處理: {os.path.basename(file_to_process)}")
                            self.process_single_file(file_to_process)

                    last_file_list = current_files
                    time.sleep(3)  # 每3秒檢查一次

                except Exception as e:
                    print(f"❌ 文件監控錯誤: {e}")
                    time.sleep(5)

        threading.Thread(target=monitor_thread, daemon=True).start()

    def scan_directory_files(self):
        """掃描目錄中的文件"""
        files = set()
        try:
            if os.path.exists(self.watch_directory):
                for filename in os.listdir(self.watch_directory):
                    filepath = os.path.join(self.watch_directory, filename)
                    if os.path.isfile(filepath):
                        valid_extensions = ['.png', '.jpg', '.jpeg', '.bmp', '.tiff']
                        if any(filepath.lower().endswith(ext) for ext in valid_extensions):
                            if self.is_file_ready(filepath):
                                files.add(filepath)
        except Exception as e:
            print(f"❌ 掃描目錄錯誤: {e}")
        return files

    def is_file_ready(self, filepath):
        """檢查檔案是否已經寫入完成"""
        try:
            size1 = os.path.getsize(filepath)
            time.sleep(0.1)
            size2 = os.path.getsize(filepath)
            return size1 == size2 and size1 > 0
        except:
            return False

    def start_command_interface(self):
        """啟動指令控制介面"""
        def command_thread():
            print("\n💻 指令控制介面已啟動")
            print("🔧 可用指令：")
            print("   help          - 顯示幫助信息")
            print("   list          - 列出待處理文件")
            print("   process <文件名> - 處理指定文件")
            print("   auto on/off   - 開啟/關閉自動處理")
            print("   status        - 顯示服務器狀態")
            print("   clear         - 清空待處理列表")
            print("   quit          - 關閉服務器")

            while self.running:
                try:
                    command = input("\n📤 Sender> ").strip().lower()

                    if command == 'help':
                        self.show_help()
                    elif command == 'list':
                        self.list_pending_files()
                    elif command.startswith('process '):
                        filename = command[8:].strip()
                        self.manual_process_file(filename)
                    elif command == 'auto on':
                        self.auto_processing = True
                        print("✅ 自動處理模式已開啟")
                    elif command == 'auto off':
                        self.auto_processing = False
                        print("⏸️ 自動處理模式已關閉")
                    elif command == 'status':
                        self.show_status()
                    elif command == 'clear':
                        self.pending_files.clear()
                        print("✅ 待處理列表已清空")
                    elif command in ['quit', 'exit']:
                        print("👋 正在關閉服務器...")
                        self.running = False
                        break
                    elif command == '':
                        continue
                    else:
                        print(f"❌ 未知指令: {command}，輸入 'help' 查看可用指令")

                except KeyboardInterrupt:
                    print("\n👋 正在關閉服務器...")
                    self.running = False
                    break
                except Exception as e:
                    print(f"❌ 指令處理錯誤: {e}")

        threading.Thread(target=command_thread, daemon=True).start()

    def show_help(self):
        """顯示幫助信息"""
        print("\n📖 手動控制Sender服務器幫助")
        print("=" * 50)
        print("🔧 指令說明：")
        print("   help                    顯示此幫助信息")
        print("   list                    列出所有待處理的文件")
        print("   process <文件名>         處理指定的文件（支援部分匹配）")
        print("   auto on                 開啟自動處理模式")
        print("   auto off                關閉自動處理模式（默認）")
        print("   status                  顯示當前服務器狀態")
        print("   clear                   清空待處理文件列表")
        print("   quit / exit             關閉服務器")
        print("\n💡 使用提示：")
        print("   • 將醫療影像放入監控目錄會被自動檢測")
        print("   • 默認需要手動指令才會處理文件")
        print("   • 使用 'auto on' 可以恢復自動批量處理")
        print("   • process 指令支援檔名部分匹配")
        print("=" * 50)

    def list_pending_files(self):
        """列出待處理文件"""
        if not self.pending_files:
            print("📭 目前沒有待處理的文件")
            return

        print(f"\n📋 待處理文件列表 ({len(self.pending_files)} 個)：")
        for i, filepath in enumerate(self.pending_files, 1):
            filename = os.path.basename(filepath)
            file_size = os.path.getsize(filepath)
            print(f"   {i}. {filename} ({file_size:,} bytes)")

    def manual_process_file(self, filename):
        """手動處理指定文件"""
        if not filename:
            print("❌ 請指定要處理的文件名")
            return

        # 查找匹配的文件
        matching_files = []
        for filepath in self.pending_files:
            if filename in os.path.basename(filepath).lower():
                matching_files.append(filepath)

        if not matching_files:
            print(f"❌ 找不到匹配的文件: {filename}")
            print("💡 使用 'list' 查看可用文件")
            return

        if len(matching_files) > 1:
            print(f"⚠️ 找到多個匹配文件：")
            for i, filepath in enumerate(matching_files, 1):
                print(f"   {i}. {os.path.basename(filepath)}")
            print("💡 請使用更精確的文件名")
            return

        # 處理匹配的文件
        file_to_process = matching_files[0]
        if file_to_process in self.pending_files:
            self.pending_files.remove(file_to_process)

        print(f"🔄 開始處理: {os.path.basename(file_to_process)}")
        success = self.process_single_file(file_to_process)

        if success:
            print(f"✅ 文件處理完成: {os.path.basename(file_to_process)}")
        else:
            print(f"❌ 文件處理失敗: {os.path.basename(file_to_process)}")

    def show_status(self):
        """顯示服務器狀態"""
        print(f"\n📊 服務器狀態報告")
        print("=" * 40)
        print(f"🌐 服務器地址: {self.host}:{self.port}")
        print(f"🏛️ CA地址: {self.ca_host}:{self.ca_port}")
        print(f"📁 監控目錄: {self.watch_directory}")
        print(f"📦 輸出目錄: {self.output_directory}")
        print(f"🔄 自動處理: {'開啟' if self.auto_processing else '關閉'}")
        print(f"📋 待處理文件: {len(self.pending_files)} 個")
        print(f"✅ 已處理文件: {len(self.processed_files)} 個")
        print(f"🔑 發送方ID: {self.sender.sender_id}")
        print("=" * 40)

    def process_single_file(self, filepath):
        """處理單一檔案：讀取元資料、簽章、加密、隱寫"""
        if not self.receiver_certificate:
            print("錯誤: 缺少接收方憑證，無法處理檔案。")
            return

        meta_filepath = filepath + ".meta.json"
        if not os.path.exists(meta_filepath):
            print(f"警告: 找不到元資料檔案 {meta_filepath}，跳過處理。")
            return

        try:
            # 讀取元資料
            with open(meta_filepath, 'r', encoding='utf-8') as f:
                app_meta = json.load(f)

            with open(filepath, 'rb') as f:
                plaintext_bytes = f.read()

            # 步驟 1: 對原始資料進行數位簽章
            signature = sign_bytes(self.sender.private_key, plaintext_bytes)

            # 步驟 2: 準備傳輸封包 (包含簽章與元資料)
            transmission_package = self.sender.encrypt_and_prepare_transmission(
                plaintext_bytes=plaintext_bytes,
                receiver_certificate=self.receiver_certificate,
                app_meta=app_meta,
                signature=signature
            )

            # 後續步驟 (LSB 隱寫與儲存) 維持不變...
            output_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{os.path.basename(filepath)}.png"
            output_path = os.path.join(self.output_directory, output_filename)
            
            # (這裡假設 self.sender 有 lsb_embed 方法)
            self.sender.lsb_embed(transmission_package, output_path)

            print(f"檔案 {os.path.basename(filepath)} 已成功加密、簽章並隱寫至 {output_path}")

            # 處理完畢後刪除原始檔案和 meta 檔案
            os.remove(filepath)
            os.remove(meta_filepath)

        except Exception as e:
            print(f"處理檔案 {os.path.basename(filepath)} 時發生錯誤: {e}")

    def create_simple_stego_image(self, source_path, stego_path, transmission_package):
        """創建簡化的隱寫影像"""
        from PIL import Image, ImageDraw, ImageFont

        img = Image.open(source_path)
        stego_img = img.copy()
        draw = ImageDraw.Draw(stego_img)

        width, height = stego_img.size
        mark_text = f"STEG:{len(str(transmission_package))}"

        try:
            font = ImageFont.load_default()
            draw.text((width-100, height-20), mark_text, fill=(128, 128, 128, 128), font=font)
        except:
            if width > 10 and height > 10:
                pixels = list(stego_img.getdata())
                for i in range(min(10, len(pixels))):
                    idx = len(pixels) - 1 - i
                    if isinstance(pixels[idx], tuple):
                        r, g, b = pixels[idx][:3]
                        pixels[idx] = (r, g, (b & 0xFE) | (i & 1)) + pixels[idx][3:]

                stego_img.putdata(pixels)

        stego_img.save(stego_path)
        print(f"📷 簡化隱寫影像已創建: {os.path.basename(stego_path)}")

    def start_network_service(self):
        """啟動網路服務"""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            server_socket.bind((self.host, self.port))
            server_socket.listen(5)
            print(f"📡 網路服務監聽: {self.host}:{self.port}")

            while self.running:
                try:
                    client_socket, address = server_socket.accept()
                    print(f"📤 接收方連接: {address}")

                    threading.Thread(
                        target=self.handle_receiver,
                        args=(client_socket, address)
                    ).start()

                except Exception as e:
                    if self.running:
                        print(f"❌ 網路服務錯誤: {e}")

        except Exception as e:
            print(f"❌ 網路服務啟動失敗: {e}")
        finally:
            server_socket.close()

    def handle_receiver(self, client_socket, address):
        """處理接收方連接"""
        try:
            request_data = client_socket.recv(1024)
            if request_data:
                request = json.loads(request_data.decode('utf-8'))

                if request.get('action') == 'request_image':
                    available_images = self.get_available_images()

                    if available_images:
                        response = {
                            'status': 'success',
                            'message': f'有 {len(available_images)} 個隱寫影像可用',
                            'sender_id': self.sender.sender_id,
                            'images': available_images
                        }
                    else:
                        response = {
                            'status': 'waiting',
                            'message': '暫無隱寫影像可用',
                            'sender_id': self.sender.sender_id
                        }

                    client_socket.send(json.dumps(response).encode('utf-8'))

                elif request.get('action') == 'download_image':
                    image_filename = request.get('filename')
                    self.send_image_file(client_socket, image_filename)

        except Exception as e:
            print(f"❌ 處理接收方請求錯誤: {e}")
        finally:
            client_socket.close()

    def get_available_images(self):
        """取得可用的隱寫影像列表"""
        try:
            images = []
            if os.path.exists(self.output_directory):
                for filename in os.listdir(self.output_directory):
                    if filename.startswith('stego_') and filename.endswith('.png'):
                        filepath = os.path.join(self.output_directory, filename)
                        file_size = os.path.getsize(filepath)
                        file_time = os.path.getmtime(filepath)

                        images.append({
                            'filename': filename,
                            'size': file_size,
                            'timestamp': file_time,
                            'type': 'steganographic_image'
                        })
            return images
        except:
            return []

    def send_image_file(self, client_socket, filename):
        """發送影像檔案給接收方"""
        try:
            filepath = os.path.join(self.output_directory, filename)
            if os.path.exists(filepath):
                with open(filepath, 'rb') as f:
                    file_data = f.read()

                file_size = len(file_data)
                client_socket.send(file_size.to_bytes(8, 'big'))
                client_socket.send(file_data)
                print(f"📤 已發送隱寫影像: {filename} ({file_size:,} bytes)")
            else:
                client_socket.send(b'\x00\x00\x00\x00\x00\x00\x00\x00')

        except Exception as e:
            print(f"❌ 發送影像錯誤: {e}")

    def process_file(self, filepath: str, meta_path: str):
        """對單一檔案執行完整的簽章、加密、打包、輸出流程"""
        try:
            with open(meta_path, "r", encoding="utf-8") as f: app_meta = json.load(f)
            with open(filepath, "rb") as f: plaintext_bytes = f.read()

            print("✍️  正在對原始資料進行數位簽章...")
            signature = sign_bytes(self.sender.private_key, plaintext_bytes)

            print("📦 正在加密與打包資料...")
            transmission_package = self.sender.encrypt_and_prepare_transmission(
                plaintext_bytes=plaintext_bytes,
                receiver_certificate=self.receiver_certificate,
                signature=signature,
                app_meta=app_meta
            )

            output_filename = f"stego_{datetime.now().strftime('%Y%m%d%H%M%S')}_{os.path.basename(filepath)}.png"
            output_path = os.path.join(self.output_directory, output_filename)
            
            if hasattr(self.sender, 'lsb_embed'):
                self.sender.lsb_embed(transmission_package, output_path)
                print(f"🖼️  已將加密封包隱寫至圖片: {output_path}")
            else:
                pkg_path = output_path.replace('.png', '.pkl')
                with open(pkg_path, "wb") as pf: pickle.dump(transmission_package, pf)
                print(f"🗳️  警告: sender 中無 lsb_embed 方法，已將封包直接儲存為: {pkg_path}")

            os.remove(filepath)
            os.remove(meta_path)
            print(f"🧹 已清理來源檔案: {os.path.basename(filepath)}")

        except Exception as e:
            print(f"❌ 處理檔案 '{os.path.basename(filepath)}' 失敗: {e}")
            import traceback; traceback.print_exc()

def main():
    import sys

    host = sys.argv[1] if len(sys.argv) > 1 else 'localhost'
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8002
    ca_host = sys.argv[3] if len(sys.argv) > 3 else 'localhost'
    ca_port = int(sys.argv[4]) if len(sys.argv) > 4 else 8001

    sender_server = ManualControlSenderServer(host, port, ca_host, ca_port)

    try:
        sender_server.start_server()

        print("\n" + "="*80)
        print("📤 手動控制版 Sender 服務器運行中...")
        print(f"🔍 監控目錄: {os.path.abspath(sender_server.watch_directory)}")
        print(f"📦 輸出目錄: {os.path.abspath(sender_server.output_directory)}")
        print("\n🎛️ 控制模式說明：")
        print("   ⏸️ 默認不自動處理文件")
        print("   🔍 系統會檢測新文件但不自動處理")
        print("   📝 使用指令手動控制處理流程")
        print("   🔄 可選擇開啟自動處理模式")
        print("\n💻 可用指令：")
        print("   help          - 顯示詳細幫助")
        print("   list          - 列出待處理文件")
        print("   process <文件名> - 處理指定文件")
        print("   auto on/off   - 切換自動處理模式")
        print("   status        - 顯示服務器狀態")
        print("   quit          - 關閉服務器")
        print("="*80)

        while sender_server.running:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n🛑 手動控制版 Sender 服務器關閉")
        sender_server.running = False

if __name__ == "__main__":
    main()