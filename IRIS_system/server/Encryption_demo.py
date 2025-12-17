#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IRIS 加密系統監控 Demo
連接到真實的 CA Server 和 Hospital Server，展示實際的加密傳輸過程
"""

import os
import sys
import time
import json
import base64
import requests
import customtkinter as ctk
from threading import Thread
from datetime import datetime

# 嘗試導入本地模組
try:
    from sender import Sender
    from signature_utils import sign_bytes
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False


class IRISMonitorDemo:
    def __init__(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        self.root = ctk.CTk()
        self.root.title("🔐 IRIS 加密系統監控")
        self.root.geometry("1300x900")
        
        # 連接狀態
        self.ca_connected = False
        self.server_connected = False
        self.sender = None
        
        self.setup_ui()
        
    def setup_ui(self):
        """建立 UI"""
        # 主容器
        main = ctk.CTkFrame(self.root, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=30, pady=30)
        
        # 標題
        title = ctk.CTkLabel(
            main,
            text="🔐 IRIS 加密傳輸系統監控",
            font=("Arial", 32, "bold"),
            text_color="#3498db"
        )
        title.pack(pady=(0, 10))
        
        subtitle = ctk.CTkLabel(
            main,
            text="即時監控加密傳輸過程",
            font=("Arial", 18),
            text_color="#7f8c8d"
        )
        subtitle.pack(pady=(0, 30))
        
        # 連接設定區
        config_frame = ctk.CTkFrame(main, fg_color="#1e1e1e", corner_radius=15)
        config_frame.pack(fill="x", pady=(0, 20))
        
        ctk.CTkLabel(
            config_frame,
            text="⚙️ 系統連接設定",
            font=("Arial", 20, "bold"),
            text_color="#ecf0f1"
        ).pack(padx=20, pady=(20, 15))
        
        # CA Server 設定
        ca_row = ctk.CTkFrame(config_frame, fg_color="transparent")
        ca_row.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(
            ca_row,
            text="🏛️ CA Server:",
            font=("Arial", 16),
            width=150,
            anchor="w"
        ).pack(side="left")
        
        self.ca_host_entry = ctk.CTkEntry(
            ca_row,
            placeholder_text="localhost",
            font=("Arial", 14),
            width=200
        )
        self.ca_host_entry.pack(side="left", padx=5)
        self.ca_host_entry.insert(0, "localhost")
        
        self.ca_port_entry = ctk.CTkEntry(
            ca_row,
            placeholder_text="8001",
            font=("Arial", 14),
            width=100
        )
        self.ca_port_entry.pack(side="left", padx=5)
        self.ca_port_entry.insert(0, "8001")
        
        self.ca_status = ctk.CTkLabel(
            ca_row,
            text="⚪ 未連接",
            font=("Arial", 14),
            text_color="#95a5a6"
        )
        self.ca_status.pack(side="left", padx=20)
        
        # Hospital Server 設定
        server_row = ctk.CTkFrame(config_frame, fg_color="transparent")
        server_row.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(
            server_row,
            text="🏥 Hospital Server:",
            font=("Arial", 16),
            width=150,
            anchor="w"
        ).pack(side="left")
        
        self.server_host_entry = ctk.CTkEntry(
            server_row,
            placeholder_text="localhost",
            font=("Arial", 14),
            width=200
        )
        self.server_host_entry.pack(side="left", padx=5)
        self.server_host_entry.insert(0, "localhost")
        
        self.server_port_entry = ctk.CTkEntry(
            server_row,
            placeholder_text="5000",
            font=("Arial", 14),
            width=100
        )
        self.server_port_entry.pack(side="left", padx=5)
        self.server_port_entry.insert(0, "5000")
        
        self.server_status = ctk.CTkLabel(
            server_row,
            text="⚪ 未連接",
            font=("Arial", 14),
            text_color="#95a5a6"
        )
        self.server_status.pack(side="left", padx=20)
        
        # 連接按鈕
        self.connect_btn = ctk.CTkButton(
            config_frame,
            text="🔌 連接系統",
            command=self.connect_systems,
            font=("Arial", 16, "bold"),
            height=45,
            fg_color="#3498db",
            hover_color="#2980b9"
        )
        self.connect_btn.pack(padx=20, pady=(10, 20), fill="x")
        
        # 狀態顯示區
        self.status_frame = ctk.CTkFrame(main, fg_color="#1e1e1e", corner_radius=15)
        self.status_frame.pack(fill="x", pady=(0, 20))
        
        self.status_label = ctk.CTkLabel(
            self.status_frame,
            text="等待連接系統...",
            font=("Arial", 20, "bold"),
            text_color="#ecf0f1"
        )
        self.status_label.pack(pady=25)
        
        self.progress = ctk.CTkProgressBar(
            self.status_frame,
            width=900,
            height=15,
            corner_radius=8
        )
        self.progress.pack(pady=(0, 25))
        self.progress.set(0)
        
        # 展示區
        self.scroll_frame = ctk.CTkScrollableFrame(
            main,
            fg_color="#2b2b2b",
            corner_radius=15,
            scrollbar_button_color="#CCCCCC",
            scrollbar_button_hover_color="#999999"
        )
        self.scroll_frame.pack(fill="both", expand=True, pady=(0, 20))
        
        # 上傳按鈕
        self.upload_btn = ctk.CTkButton(
            main,
            text="📤 上傳測試影像 (加密傳輸)",
            command=self.upload_test_image,
            font=("Arial", 18, "bold"),
            height=55,
            corner_radius=15,
            fg_color="#27ae60",
            hover_color="#229954",
            state="disabled"
        )
        self.upload_btn.pack(fill="x")
        
    def update_status(self, text, progress=None):
        """更新狀態"""
        self.status_label.configure(text=text)
        if progress is not None:
            self.progress.set(progress)
        self.root.update()
        
    def add_info_card(self, icon, title, content, color="#3498db"):
        """添加資訊卡片"""
        card = ctk.CTkFrame(self.scroll_frame, fg_color="#1e1e1e", corner_radius=12)
        card.pack(fill="x", padx=15, pady=10)
        
        # 標題
        header = ctk.CTkLabel(
            card,
            text=f"{icon} {title}",
            font=("Arial", 20, "bold"),
            text_color=color,
            anchor="w"
        )
        header.pack(fill="x", padx=20, pady=(20, 10))
        
        # 內容
        content_label = ctk.CTkLabel(
            card,
            text=content,
            font=("Arial", 15),
            text_color="#ecf0f1",
            justify="left",
            anchor="w"
        )
        content_label.pack(fill="x", padx=30, pady=(0, 20))
        
        self.root.update()
        self.scroll_frame._parent_canvas.yview_moveto(1.0)
        
    def add_data_card(self, title, data_dict):
        """添加資料卡片"""
        card = ctk.CTkFrame(self.scroll_frame, fg_color="#34495e", corner_radius=12)
        card.pack(fill="x", padx=15, pady=8)
        
        ctk.CTkLabel(
            card,
            text=f"🔍 {title}",
            font=("Arial", 18, "bold"),
            text_color="#e67e22",
            anchor="w"
        ).pack(fill="x", padx=20, pady=(15, 10))
        
        for key, value in data_dict.items():
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=25, pady=3)
            
            ctk.CTkLabel(
                row,
                text=f"{key}:",
                font=("Arial", 14, "bold"),
                text_color="#bdc3c7",
                anchor="w",
                width=200
            ).pack(side="left")
            
            # 處理長字串
            if isinstance(value, str) and len(value) > 80:
                value = value[:80] + "..."
            
            ctk.CTkLabel(
                row,
                text=str(value),
                font=("Consolas", 13),
                text_color="#ecf0f1",
                anchor="w"
            ).pack(side="left", padx=10)
        
        ctk.CTkLabel(card, text="", height=15).pack()
        
        self.root.update()
        self.scroll_frame._parent_canvas.yview_moveto(1.0)
        
    def connect_systems(self):
        """連接系統"""
        self.connect_btn.configure(state="disabled")
        Thread(target=self._connect_systems_thread, daemon=True).start()
        
    def _connect_systems_thread(self):
        """連接系統執行緒"""
        # 清空展示區
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
        
        ca_host = self.ca_host_entry.get()
        ca_port = self.ca_port_entry.get()
        server_host = self.server_host_entry.get()
        server_port = self.server_port_entry.get()
        
        try:
            # 步驟 1: 連接 CA Server
            self.update_status("🔌 正在連接 CA Server...", 0.1)
            time.sleep(0.5)
            
            try:
                response = requests.get(
                    f"http://{ca_host}:{ca_port}/public_key",
                    timeout=5
                )
                
                if response.status_code == 200:
                    self.ca_connected = True
                    self.ca_status.configure(
                        text="🟢 已連接",
                        text_color="#27ae60"
                    )
                    
                    ca_public_key = response.text
                    
                    self.add_info_card(
                        "✅",
                        "CA Server 連接成功",
                        f"位址: {ca_host}:{ca_port}\n" +
                        f"CA 公鑰長度: {len(ca_public_key)} bytes",
                        "#27ae60"
                    )
                else:
                    raise Exception(f"HTTP {response.status_code}")
                    
            except Exception as e:
                self.ca_status.configure(
                    text="🔴 連接失敗",
                    text_color="#e74c3c"
                )
                self.add_info_card(
                    "❌",
                    "CA Server 連接失敗",
                    f"錯誤: {str(e)}\n請確認 CA Server 已啟動",
                    "#e74c3c"
                )
                self.connect_btn.configure(state="normal")
                return
            
            # 步驟 2: 連接 Hospital Server
            self.update_status("🔌 正在連接 Hospital Server...", 0.3)
            time.sleep(0.5)
            
            try:
                response = requests.get(
                    f"http://{server_host}:{server_port}/health",
                    timeout=5
                )
                
                if response.status_code == 200:
                    server_info = response.json()
                    self.server_connected = True
                    self.server_status.configure(
                        text="🟢 已連接",
                        text_color="#27ae60"
                    )
                    
                    self.add_info_card(
                        "✅",
                        "Hospital Server 連接成功",
                        f"位址: {server_host}:{server_port}\n" +
                        f"狀態: {server_info.get('status', 'unknown')}\n" +
                        f"Receiver ID: {server_info.get('receiver_id', 'N/A')}\n" +
                        f"資料庫影像數: {server_info.get('database', {}).get('image_count', 0)}",
                        "#27ae60"
                    )
                    
                    self.add_data_card("Server 詳細資訊", server_info)
                else:
                    raise Exception(f"HTTP {response.status_code}")
                    
            except Exception as e:
                self.server_status.configure(
                    text="🔴 連接失敗",
                    text_color="#e74c3c"
                )
                self.add_info_card(
                    "❌",
                    "Hospital Server 連接失敗",
                    f"錯誤: {str(e)}\n請確認 Server 已啟動",
                    "#e74c3c"
                )
                self.connect_btn.configure(state="normal")
                return
            
            # 步驟 3: 初始化 Client Sender
            if not CRYPTO_AVAILABLE:
                self.add_info_card(
                    "❌",
                    "加密模組未安裝",
                    "無法初始化 Sender\n請確認 sender.py 等檔案在同一目錄",
                    "#e74c3c"
                )
                self.connect_btn.configure(state="normal")
                return
            
            self.update_status("🔑 正在初始化 Client (生成密鑰)...", 0.5)
            time.sleep(0.5)
            
            self.sender = Sender("DemoClient_001")
            
            self.add_info_card(
                "🔐",
                "Client 初始化完成",
                f"Sender ID: {self.sender.sender_id}\n" +
                f"RSA 公鑰: {len(self.sender.get_public_key_pem())} bytes\n" +
                f"KEM 公鑰: {len(self.sender.kem_public_key)} bytes (ML-KEM-1024)",
                "#3498db"
            )
            
            # 步驟 4: 向 CA 註冊
            self.update_status("📝 正在向 CA 註冊...", 0.7)
            time.sleep(0.5)
            
            try:
                register_data = {
                    "party_id": self.sender.sender_id,
                    "public_key_pem": self.sender.get_public_key_pem().decode('utf-8'),
                    "kem_public_key_b64": base64.b64encode(self.sender.kem_public_key).decode('utf-8')
                }
                
                response = requests.post(
                    f"http://{ca_host}:{ca_port}/register",
                    json=register_data,
                    timeout=10
                )
                
                if response.status_code == 200:
                    self.sender.certificate = response.json()
                    self.sender.ca_public_key_pem = ca_public_key.encode('utf-8')
                    
                    self.add_info_card(
                        "📜",
                        "CA 註冊成功",
                        f"憑證 ID: {self.sender.certificate['certificate_info']['party_id']}\n" +
                        "✓ 憑證已簽發\n✓ 身份驗證就緒",
                        "#9b59b6"
                    )
                else:
                    raise Exception(f"HTTP {response.status_code}")
                    
            except Exception as e:
                self.add_info_card(
                    "❌",
                    "CA 註冊失敗",
                    f"錯誤: {str(e)}",
                    "#e74c3c"
                )
                self.connect_btn.configure(state="normal")
                return
            
            # 步驟 5: 獲取 Server 憑證
            self.update_status("📥 正在獲取 Server 憑證...", 0.85)
            time.sleep(0.5)
            
            try:
                response = requests.get(
                    f"http://{server_host}:{server_port}/get_server_certificate",
                    timeout=5
                )
                
                if response.status_code == 200:
                    server_cert = response.json()
                    self.server_certificate = server_cert
                    
                    self.add_info_card(
                        "✅",
                        "Server 憑證取得成功",
                        f"Server ID: {server_cert['certificate_info']['party_id']}",
                        "#27ae60"
                    )
                else:
                    raise Exception(f"HTTP {response.status_code}")
                    
            except Exception as e:
                self.add_info_card(
                    "⚠️",
                    "無法取得 Server 憑證",
                    f"錯誤: {str(e)}\n將嘗試無憑證上傳",
                    "#f39c12"
                )
                self.server_certificate = None
            
            # 完成
            self.update_status("✅ 系統連接完成！可以開始上傳", 1.0)
            
            # 啟用上傳按鈕
            self.upload_btn.configure(state="normal")
            self.connect_btn.configure(
                state="normal",
                text="🔄 重新連接"
            )
            
        except Exception as e:
            self.update_status(f"❌ 錯誤: {str(e)}", 0)
            self.connect_btn.configure(state="normal")
            import traceback
            traceback.print_exc()
    
    def upload_test_image(self):
        """上傳測試影像"""
        self.upload_btn.configure(state="disabled")
        Thread(target=self._upload_test_image_thread, daemon=True).start()
        
    def _upload_test_image_thread(self):
        """上傳執行緒"""
        try:
            server_host = self.server_host_entry.get()
            server_port = self.server_port_entry.get()
            
            # 生成測試影像
            self.update_status("📷 正在生成測試影像...", 0.1)
            test_image = b"IRIS_TEST_IMAGE_" + os.urandom(2048)
            
            self.add_info_card(
                "📄",
                "測試影像已生成",
                f"大小: {len(test_image)} bytes",
                "#e67e22"
            )
            
            # 簽章
            self.update_status("✍️ 正在簽署資料...", 0.2)
            signature = sign_bytes(self.sender.private_key, test_image)
            
            self.add_info_card(
                "✍️",
                "數位簽章完成",
                f"簽章長度: {len(signature)} bytes",
                "#e74c3c"
            )
            
            # 加密
            self.update_status("🔐 正在加密資料...", 0.4)
            
            app_meta = {
                "patient_id": 99999,
                "uploader_id": 1,
                "filename": "demo_test.jpg",
                "mime": "image/jpeg",
                "upload_time": time.time(),
                "modality_dept_code": "CR",
                "clinical_dept_code": "DEMO"
            }
            
            encrypt_start = time.perf_counter()
            package = self.sender.encrypt_and_prepare_transmission(
                plaintext_bytes=test_image,
                receiver_certificate=self.server_certificate,
                signature=signature,
                app_meta=app_meta
            )
            encrypt_time = (time.perf_counter() - encrypt_start) * 1000
            
            self.add_info_card(
                "🔒",
                "加密完成",
                f"⏱️ 耗時: {encrypt_time:.2f} ms\n" +
                f"封包大小: {len(json.dumps(package).encode())} bytes",
                "#27ae60"
            )
            
            # 展示加密資訊
            enc_data = package['enc_data']
            self.add_data_card("加密封包資訊", {
                "KEM 密鑰長度": f"{len(base64.b64decode(enc_data['kem_ciphertext_b64']))} bytes",
                "密文長度": f"{len(base64.b64decode(enc_data['ciphertext_b64']))} bytes",
                "IV": base64.b64decode(enc_data['iv_b64']).hex()[:32] + "...",
                "Tag": base64.b64decode(enc_data['tag_b64']).hex()[:32] + "..."
            })
            
            # 傳送到 Server
            self.update_status("📤 正在傳送到 Server...", 0.7)
            
            response = requests.post(
                f"http://{server_host}:{server_port}/upload",
                json=package,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                
                self.update_status("✅ 上傳成功！", 1.0)
                
                self.add_info_card(
                    "🎉",
                    "上傳成功！",
                    f"Image ID: {result.get('image_id', 'N/A')}\n" +
                    f"訊息: {result.get('message', 'Success')}\n\n" +
                    "✓ 加密傳輸完成\n" +
                    "✓ Server 已接收並解密\n" +
                    "✓ 資料已儲存至資料庫",
                    "#27ae60"
                )
            else:
                raise Exception(f"HTTP {response.status_code}: {response.text}")
            
            self.upload_btn.configure(state="normal")
            
        except Exception as e:
            self.update_status(f"❌ 上傳失敗: {str(e)}", 0)
            self.add_info_card(
                "❌",
                "上傳失敗",
                f"錯誤: {str(e)}",
                "#e74c3c"
            )
            self.upload_btn.configure(state="normal")
            import traceback
            traceback.print_exc()
    
    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = IRISMonitorDemo()
    app.run()