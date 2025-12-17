# -*- coding: utf-8 -*-
"""
auth.py - 登入與使用者認證模組（後端 API 驗證版）

⚠️ 重要：此版本透過後端 API 進行使用者驗證，
         確保能取得完整的使用者資訊（包含 clinical_dept_id）
"""
import customtkinter as ctk
from tkinter import messagebox
from .config import COLOR, FONT, Card, SolidBtn, PAD
from .api_client import get_api_client


class LoginWindow:
    """登入視窗類別（後端 API 驗證版）"""

    def __init__(self, root, on_login_success):
        self.root = root
        self.on_login_success = on_login_success
        self.api_client = get_api_client()
        self.backend_connected = False
        self.setup_ui()
        self._check_backend_connection()

    def _check_backend_connection(self):
        """檢查後端連接狀態"""
        try:
            health = self.api_client.health_check()
            if health:
                self.backend_connected = True
                self._update_connection_status(True, "✅ Hospital Server 連線正常")
                print("✅ 成功連接到 Hospital Server")
            else:
                self.backend_connected = False
                self._update_connection_status(False, "❌ 無法連接到 Hospital Server")
                print("❌ 無法連接到 Hospital Server")
        except Exception as e:
            self.backend_connected = False
            self._update_connection_status(False, f"❌ 連線錯誤")
            print(f"❌ 後端連線錯誤: {e}")

    def _update_connection_status(self, connected, message):
        """更新連線狀態顯示"""
        if hasattr(self, 'status_label'):
            status_color = COLOR["success"] if connected else COLOR["danger"]
            self.status_label.configure(text=message, text_color=status_color)

    def setup_ui(self):
        """設置登入介面"""
        for w in self.root.winfo_children():
            w.destroy()

        wrap = ctk.CTkFrame(self.root, fg_color=COLOR["bg"])
        wrap.pack(fill="both", expand=True)

        card = Card(wrap)
        card.place(relx=0.5, rely=0.5, anchor="center")
        card.configure(width=480, height=680)
        card.pack_propagate(False)

        box = ctk.CTkFrame(card, fg_color=COLOR["surface"])
        box.pack(fill="both", expand=True, padx=PAD, pady=PAD)

        # Logo 和標題
        ctk.CTkLabel(
            box, 
            text="IRIS 智慧影像系統", 
            font=FONT["logo"], 
            text_color=COLOR["ink"]
        ).pack(anchor="w", pady=(0, 4))
        
        ctk.CTkLabel(
            box, 
            text="醫療影像管理平台 - 後端認證版", 
            font=FONT["body"], 
            text_color=COLOR["inksubtle"]
        ).pack(anchor="w", pady=(0, 20))

        # 使用者名稱
        ctk.CTkLabel(
            box, 
            text="使用者名稱", 
            font=FONT["meta"], 
            text_color=COLOR["inksubtle"]
        ).pack(anchor="w")
        
        self.userentry = ctk.CTkEntry(
            box, 
            placeholder_text="Username", 
            height=44, 
            corner_radius=12, 
            font=FONT["body"]
        )
        self.userentry.pack(fill="x", pady=(6, 12))
        self.userentry.bind("<Return>", lambda e: self.pwentry.focus())

        # 密碼
        ctk.CTkLabel(
            box, 
            text="密碼", 
            font=FONT["meta"], 
            text_color=COLOR["inksubtle"]
        ).pack(anchor="w")
        
        self.pwentry = ctk.CTkEntry(
            box, 
            placeholder_text="Password", 
            show="•", 
            height=44, 
            corner_radius=12, 
            font=FONT["body"]
        )
        self.pwentry.pack(fill="x", pady=(6, 18))
        self.pwentry.bind("<Return>", lambda e: self.login())

        # 登入按鈕
        SolidBtn(box, "登入", self.login).pack(fill="x")

        # 預設帳號提示
        info_frame = ctk.CTkFrame(box, fg_color=COLOR["chip"], corner_radius=8)
        info_frame.pack(fill="x", pady=(16, 0))

        ctk.CTkLabel(
            info_frame, 
            text="📋 IRIS 預設帳號（後端資料庫）", 
            font=ctk.CTkFont(size=12, weight="bold"), 
            text_color=COLOR["primary"]
        ).pack(pady=(8, 4))

        # 帳號提示 - 包含科別資訊
        accounts = [
            "👨‍⚕️ doctor1 / doctor1 (心臟內科)",
            "👨‍⚕️ doctor2 / doctor2 (神經內科)",
            "👩‍⚕️ nurse / nurse",
            "🔬 radtech / radtech",
            "🔧 admin / admin (系統管理員)"
        ]

        for acc in accounts:
            ctk.CTkLabel(
                info_frame, 
                text=acc, 
                font=FONT["meta"], 
                text_color=COLOR["inksubtle"]
            ).pack(pady=2)

        # 連線狀態
        self.status_label = ctk.CTkLabel(
            info_frame, 
            text="⏳ 檢查連線中...", 
            font=FONT["meta"], 
            text_color=COLOR["muted"]
        )
        self.status_label.pack(pady=(4, 8))

    def login(self):
        """執行登入驗證（透過後端 API）"""
        username = (self.userentry.get() or "").strip()
        password = (self.pwentry.get() or "").strip()

        if not username or not password:
            messagebox.showwarning("警告", "請輸入帳號和密碼")
            return

        if not self.backend_connected:
            # 嘗試重新連線
            self._check_backend_connection()
            if not self.backend_connected:
                messagebox.showerror(
                    "連線失敗", 
                    "無法連接到 Hospital Server\n\n請確認：\n1. Server 是否正在運行\n2. 網路連線是否正常"
                )
                return

        try:
            # 呼叫後端 API 驗證
            result = self.api_client.login(username, password)
            
            if not result:
                messagebox.showerror("登入失敗", "伺服器無回應")
                return
            
            if result.get('status') != 'success':
                # 處理不同的錯誤類型
                error_code = result.get('error_code', 'unknown')
                error_msg = result.get('message', '帳號或密碼錯誤')
                
                if error_code == 'user_not_found':
                    messagebox.showerror("登入失敗", "帳號不存在")
                elif error_code == 'wrong_password':
                    messagebox.showerror("登入失敗", "密碼錯誤")
                elif error_code == 'account_disabled':
                    messagebox.showerror("登入失敗", "帳號已停用，請聯繫管理員")
                else:
                    messagebox.showerror("登入失敗", error_msg)
                return

            # 登入成功，取得完整的使用者資訊
            user = result.get('user')
            
            if not user:
                messagebox.showerror("錯誤", "無法取得使用者資訊")
                return
            
            # ====== 關鍵：確保 role 欄位正確 ======
            # 後端可能回傳 role_code，需要映射到 config.py 的 role 格式
            if 'role_code' in user and 'role' not in user:
                user['role'] = user['role_code']
            
            # 確保必要欄位存在
            if 'role' not in user:
                user['role'] = 'viewer'  # 預設角色
            
            # 印出完整的使用者資訊（用於除錯）
            print(f"\n✅ 登入成功: {user.get('username')}")
            print(f"   角色: {user.get('role')} ({user.get('role_name', '-')})")
            print(f"   科別 ID: {user.get('clinical_dept_id', 'None')}")
            print(f"   科別名稱: {user.get('clinical_dept_name', '-')}")
            print(f"   完整資訊: {user}")
            
            # 登入成功，呼叫回調函數
            self.on_login_success(user)

        except Exception as e:
            messagebox.showerror("錯誤", f"登入失敗: {str(e)}")
            import traceback
            traceback.print_exc()