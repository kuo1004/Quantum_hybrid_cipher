#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IRIS 加密流程展示 GUI - 最終正確版
根據實際 sender.py 的封包結構 (enc_data 巢狀結構)
"""

import os
import time
import json
import base64
import customtkinter as ctk
from threading import Thread

# 導入加密模組
try:
    from sender import Sender
    from receiver import Receiver
    from certificate_authority import CertificateAuthority
    from signature_utils import sign_bytes
    MODULES_AVAILABLE = True
except ImportError as e:
    MODULES_AVAILABLE = False
    print(f"❌ 模組導入失敗: {e}")


class EncryptionDemoGUI:
    def __init__(self):
        # 設定主題
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        # 建立主視窗
        self.root = ctk.CTk()
        self.root.title("🔐 IRIS 加密流程展示")
        self.root.geometry("1000x800")
        
        # 建立滾動框架
        self.scroll_frame = ctk.CTkScrollableFrame(
            self.root,
            fg_color="transparent",
            scrollbar_button_color="#CCCCCC",
            scrollbar_button_hover_color="#999999"
        )
        self.scroll_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # 標題
        title = ctk.CTkLabel(
            self.scroll_frame,
            text="🔐 IRIS 醫療影像加密系統 - 完整流程展示",
            font=("Arial", 24, "bold")
        )
        title.pack(pady=(0, 20))
        
        if not MODULES_AVAILABLE:
            error_label = ctk.CTkLabel(
                self.scroll_frame,
                text="❌ 錯誤：無法導入必要模組\n請確認 sender.py, receiver.py 等檔案都在同一目錄",
                font=("Arial", 14),
                text_color="red"
            )
            error_label.pack(pady=20)
            return
        
        # 開始按鈕
        self.start_btn = ctk.CTkButton(
            self.scroll_frame,
            text="▶ 開始展示加密流程",
            command=self.start_demo,
            font=("Arial", 16, "bold"),
            height=50,
            fg_color="#2ECC71",
            hover_color="#27AE60"
        )
        self.start_btn.pack(pady=10, fill="x")
        
        # 展示區域
        self.content_frame = ctk.CTkFrame(self.scroll_frame, fg_color="#2b2b2b")
        self.content_frame.pack(fill="both", expand=True, pady=10)
        
    def add_section(self, title, items, color="#3498db"):
        """新增一個展示區塊"""
        section = ctk.CTkFrame(self.content_frame, fg_color="#1e1e1e", corner_radius=10)
        section.pack(fill="x", padx=10, pady=10)
        
        # 標題
        header = ctk.CTkLabel(
            section,
            text=title,
            font=("Arial", 18, "bold"),
            text_color=color,
            anchor="w"
        )
        header.pack(fill="x", padx=15, pady=(15, 10))
        
        # 內容
        for item in items:
            if isinstance(item, tuple):
                label, value = item
                row = ctk.CTkFrame(section, fg_color="transparent")
                row.pack(fill="x", padx=20, pady=3)
                
                ctk.CTkLabel(
                    row,
                    text=label,
                    font=("Consolas", 12, "bold"),
                    text_color="#ecf0f1",
                    anchor="w"
                ).pack(side="left")
                
                ctk.CTkLabel(
                    row,
                    text=value,
                    font=("Consolas", 11),
                    text_color="#bdc3c7",
                    anchor="w"
                ).pack(side="left", padx=(10, 0))
            else:
                ctk.CTkLabel(
                    section,
                    text=item,
                    font=("Arial", 12),
                    text_color="#ecf0f1",
                    anchor="w"
                ).pack(fill="x", padx=20, pady=3)
        
        ctk.CTkLabel(section, text="", height=10).pack()
        
    def add_key_display(self, title, key_data):
        """新增金鑰展示"""
        section = ctk.CTkFrame(self.content_frame, fg_color="#1e1e1e", corner_radius=10)
        section.pack(fill="x", padx=10, pady=10)
        
        # 標題
        header = ctk.CTkLabel(
            section,
            text=title,
            font=("Arial", 16, "bold"),
            text_color="#e67e22",
            anchor="w"
        )
        header.pack(fill="x", padx=15, pady=(15, 10))
        
        # 金鑰資訊
        if isinstance(key_data, bytes):
            hex_str = key_data.hex()
            size = len(key_data)
        else:
            hex_str = str(key_data)
            size = len(hex_str)
        
        # 長度
        size_label = ctk.CTkLabel(
            section,
            text=f"📏 長度: {size} bytes",
            font=("Arial", 12),
            text_color="#3498db",
            anchor="w"
        )
        size_label.pack(fill="x", padx=20, pady=5)
        
        # 預覽框
        preview_frame = ctk.CTkFrame(section, fg_color="#34495e", corner_radius=5)
        preview_frame.pack(fill="x", padx=20, pady=5)
        
        # 每行顯示 64 個字元
        chunk_size = 64
        for i in range(0, min(len(hex_str), 256), chunk_size):
            chunk = hex_str[i:i+chunk_size]
            ctk.CTkLabel(
                preview_frame,
                text=chunk,
                font=("Consolas", 10),
                text_color="#ecf0f1",
                anchor="w"
            ).pack(fill="x", padx=10, pady=2)
        
        if len(hex_str) > 256:
            ctk.CTkLabel(
                preview_frame,
                text="...",
                font=("Consolas", 10),
                text_color="#95a5a6",
                anchor="w"
            ).pack(fill="x", padx=10, pady=2)
        
        ctk.CTkLabel(section, text="", height=10).pack()
    
    def start_demo(self):
        """開始執行 Demo"""
        self.start_btn.configure(state="disabled", text="⏳ 執行中...")
        
        # 清空內容
        for widget in self.content_frame.winfo_children():
            widget.destroy()
        
        # 在新執行緒中執行
        Thread(target=self.run_demo, daemon=True).start()
    
    def run_demo(self):
        """執行加密流程"""
        try:
            # 階段 1: 初始化
            self.add_section(
                "📋 階段 1: 系統初始化",
                ["正在初始化 CA、Client、Server..."],
                "#9b59b6"
            )
            
            ca = CertificateAuthority("Taiwan_Medical_CA")
            sender = Sender("RadTech_Client_001")
            receiver = Receiver("Hospital_Server_001")
            
            self.add_section(
                "✅ 初始化完成",
                [
                    "• CA (憑證機構) ✓",
                    "• Client (放射科技師) ✓",
                    "• Server (醫院伺服器) ✓"
                ],
                "#2ecc71"
            )
            
            # 階段 2: 展示金鑰
            self.add_section(
                "🔑 階段 2: 金鑰生成結果",
                [
                    "Client 端:",
                    f"  • RSA 公鑰長度: {len(sender.get_public_key_pem())} bytes",
                    f"  • KEM 公鑰長度: {len(sender.kem_public_key)} bytes (ML-KEM-1024)",
                    "",
                    "Server 端:",
                    f"  • RSA 公鑰長度: {len(receiver.get_public_key_pem())} bytes",
                    f"  • KEM 公鑰長度: {len(receiver.kem_public_key)} bytes (ML-KEM-1024)"
                ],
                "#3498db"
            )
            
            self.add_key_display("🔐 Client KEM 公鑰", sender.kem_public_key)
            self.add_key_display("🔐 Server KEM 公鑰", receiver.kem_public_key)
            
            # 階段 3: CA 註冊
            self.add_section(
                "📋 階段 3: CA 註冊與憑證發放",
                ["正在向 CA 註冊..."],
                "#9b59b6"
            )
            
            sender.register_with_ca(ca)
            receiver.register_with_ca(ca)
            
            self.add_section(
                "✅ CA 註冊完成",
                [
                    f"Client 憑證 ID: {sender.certificate['certificate_info']['party_id']}",
                    f"Server 憑證 ID: {receiver.certificate['certificate_info']['party_id']}"
                ],
                "#2ecc71"
            )
            
            # 階段 4: 準備測試資料
            self.add_section(
                "📋 階段 4: 準備測試資料",
                ["生成模擬醫療影像資料..."],
                "#9b59b6"
            )
            
            test_image = b"IRIS_MEDICAL_IMAGE_" + os.urandom(2048)
            
            self.add_section(
                "✅ 測試資料已準備",
                [f"原始資料大小: {len(test_image)} bytes"],
                "#2ecc71"
            )
            
            self.add_key_display("📄 原始資料預覽", test_image)
            
            # 階段 5: 數位簽章
            self.add_section(
                "📋 階段 5: 數位簽章",
                ["使用 Client 私鑰簽署資料..."],
                "#9b59b6"
            )
            
            signature = sign_bytes(sender.private_key, test_image)
            
            self.add_section(
                "✅ 簽章完成",
                [
                    f"簽章演算法: RSA-PSS with SHA-256",
                    f"簽章長度: {len(signature)} bytes"
                ],
                "#2ecc71"
            )
            
            self.add_key_display("✍️ 數位簽章", signature)
            
            # 階段 6: 加密
            self.add_section(
                "📋 階段 6: 執行加密",
                ["正在加密資料..."],
                "#9b59b6"
            )
            
            app_meta = {
                "patient_id": 12345,
                "uploader_id": 1,
                "filename": "chest_xray.jpg",
                "mime": "image/jpeg"
            }
            
            start = time.perf_counter()
            package = sender.encrypt_and_prepare_transmission(
                plaintext_bytes=test_image,
                receiver_certificate=receiver.certificate,
                signature=signature,
                app_meta=app_meta
            )
            encrypt_time = (time.perf_counter() - start) * 1000
            
            self.add_section(
                "✅ 加密完成",
                [
                    f"⏱️ 加密耗時: {encrypt_time:.2f} ms",
                    f"加密演算法: AES-256-GCM",
                    f"密鑰封裝: ML-KEM-1024"
                ],
                "#2ecc71"
            )
            
            # 階段 7: 展示加密結果
            # ⭐⭐⭐ 關鍵：從 enc_data 取得資料 ⭐⭐⭐
            enc_data = package['enc_data']
            encap_key = base64.b64decode(enc_data['kem_ciphertext_b64'])
            wrapped_key = base64.b64decode(enc_data['wrapped_aes_key_b64'])
            ciphertext = base64.b64decode(enc_data['ciphertext_b64'])
            iv = base64.b64decode(enc_data['iv_b64'])
            tag = base64.b64decode(enc_data['tag_b64'])
            
            self.add_section(
                "🔒 階段 7: 加密封包結構",
                [
                    "完整的傳輸封包包含:",
                    "├─ enc_data (加密資料區)",
                    "│   ├─ kem_ciphertext_b64",
                    "│   ├─ wrapped_aes_key_b64",
                    "│   ├─ ciphertext_b64",
                    "│   └─ iv_b64, tag_b64...",
                    "├─ signature (數位簽章)",
                    "├─ app_meta (應用層資料)",
                    "└─ sender_cert_b64",
                    "",
                    f"📦 總封包大小: {len(json.dumps(package).encode())} bytes"
                ],
                "#e67e22"
            )
            
            self.add_key_display("1️⃣ KEM 封裝密鑰", encap_key)
            self.add_key_display("2️⃣ 加密後的 AES 金鑰", wrapped_key)
            
            self.add_section(
                "3️⃣ AES-GCM 參數",
                [
                    ("IV:", iv.hex()),
                    ("Tag:", tag.hex())
                ],
                "#e67e22"
            )
            
            self.add_key_display("4️⃣ 密文", ciphertext)
            
            # 階段 8: 解密
            self.add_section(
                "📋 階段 8: 執行解密",
                ["正在解密資料..."],
                "#9b59b6"
            )
            
            start = time.perf_counter()
            decrypted, meta = receiver.decrypt_and_extract_transmission(
                package,
                ca.get_ca_public_key_pem()
            )
            decrypt_time = (time.perf_counter() - start) * 1000
            
            self.add_section(
                "✅ 解密完成",
                [f"⏱️ 解密耗時: {decrypt_time:.2f} ms"],
                "#2ecc71"
            )
            
            # 階段 9: 驗證
            if decrypted == test_image:
                self.add_section(
                    "✅ 階段 9: 完整性驗證成功",
                    [
                        "🎉 解密資料與原始資料完全一致！",
                        "",
                        f"原始大小: {len(test_image)} bytes",
                        f"解密大小: {len(decrypted)} bytes",
                        f"匹配度: 100%"
                    ],
                    "#27ae60"
                )
            else:
                self.add_section(
                    "❌ 驗證失敗",
                    ["資料不一致"],
                    "#e74c3c"
                )
            
            # 總結
            self.add_section(
                "📊 性能與安全性總結",
                [
                    "⚡ 性能:",
                    f"  • 加密: {encrypt_time:.2f} ms",
                    f"  • 解密: {decrypt_time:.2f} ms",
                    "",
                    "🔒 安全特性:",
                    "  ✓ RSA-2048 數位簽章",
                    "  ✓ ML-KEM-1024 量子安全",
                    "  ✓ AES-256-GCM 加密",
                    "  ✓ CA 憑證驗證",
                    "  ✓ 端到端加密"
                ],
                "#9b59b6"
            )
            
            self.start_btn.configure(
                state="normal",
                text="✅ 完成！點擊重新執行",
                fg_color="#27ae60"
            )
            
        except Exception as e:
            self.add_section(
                "❌ 發生錯誤",
                [f"錯誤: {str(e)}"],
                "#e74c3c"
            )
            self.start_btn.configure(state="normal", text="▶ 重新開始")
            import traceback
            traceback.print_exc()
    
    def run(self):
        """執行程式"""
        self.root.mainloop()


if __name__ == "__main__":
    app = EncryptionDemoGUI()
    app.run()