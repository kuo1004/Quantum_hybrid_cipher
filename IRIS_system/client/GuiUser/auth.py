# -*- coding: utf-8 -*-
"""
auth.py - 登入與使用者認證模組（後端 API 版 - 修正版）
透過 CA 和後端 API 進行使用者驗證
"""
import customtkinter as ctk
from tkinter import messagebox
from .config import COLOR, FONT, Card, SolidBtn, PAD
from .api_client import get_api_client


class LoginWindow:
    """登入視窗類別（後端 API 版）"""

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
            # 支援多種狀態格式: 'ok', 'healthy'
            if health and (health.get('status') in ['ok', 'healthy']):
                self.backend_connected = True
                self._update_connection_status(True, "✅ 後端連線正常")
                print("✅ 成功連接到後端 Server")
            else:
                self.backend_connected = False
                self._update_connection_status(False, "❌ 後端連線失敗")
                print("❌ 無法連接到後端 Server")
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
        card.configure(width=460, height=620)
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
            text="醫療影像管理平台", 
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
        self.userentry.pack(fill="x", pady=(6, 14))

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

        # 連線狀態
        status_frame = ctk.CTkFrame(box, fg_color=COLOR["chip"], corner_radius=8)
        status_frame.pack(fill="x", pady=(16, 0))

        self.status_label = ctk.CTkLabel(
            status_frame,
            text="🔄 檢查後端連線中...",
            font=FONT["meta"],
            text_color=COLOR["inksubtle"]
        )
        self.status_label.pack(pady=8)

        # 重新連線按鈕
        reconnect_btn = ctk.CTkButton(
            status_frame,
            text="🔄 重新連線",
            command=self._check_backend_connection,
            height=32,
            corner_radius=8,
            fg_color=COLOR["primary"]
        )
        reconnect_btn.pack(pady=(0, 8))

        # 預設帳號提示
        info_frame = ctk.CTkFrame(box, fg_color=COLOR["chip"], corner_radius=8)
        info_frame.pack(fill="x", pady=(12, 0))

        ctk.CTkLabel(
            info_frame, 
            text="📋 IRIS 預設帳號", 
            font=ctk.CTkFont(size=12, weight="bold"), 
            text_color=COLOR["primary"]
        ).pack(pady=(8, 4))

        accounts = [
            "👨‍⚕️ 醫師: doctor1 / doctor1 (心臟內科)",
            "👨‍⚕️ 醫師: doctor2 / doctor2 (神經內科)",
            "👩‍⚕️ 護理師: nurse / nurse",
            "🔬 放射技師: radtech / radtech",
            "🔧 管理員: admin / admin"
        ]

        for acc in accounts:
            ctk.CTkLabel(
                info_frame, 
                text=acc, 
                font=FONT["meta"], 
                text_color=COLOR["inksubtle"]
            ).pack(pady=2)

        ctk.CTkLabel(
            info_frame,
            text="🔐 透過後端 API 認證",
            font=FONT["meta"],
            text_color=COLOR["primary"]
        ).pack(pady=(4, 8))

    def login(self):
        """執行登入驗證（透過後端 API）"""
        username = (self.userentry.get() or "").strip()
        password = (self.pwentry.get() or "").strip()

        if not username or not password:
            messagebox.showwarning("警告", "請輸入帳號和密碼")
            return

        # 檢查後端連線
        if not self.backend_connected:
            retry = messagebox.askyesno(
                "連線失敗",
                "無法連接到後端 Server\n\n是否重新嘗試連線？"
            )
            if retry:
                self._check_backend_connection()
                if not self.backend_connected:
                    messagebox.showerror("錯誤", "後端 Server 無法連線")
                    return
            else:
                return

        try:
            # 呼叫後端 API 進行登入驗證
            result = self.api_client.login(username, password)
            
            if not result:
                messagebox.showerror("登入失敗", "無法連接到後端 Server")
                return
            
            # 檢查登入狀態
            if result.get('status') == 'success':
                user_data = result.get('user')
                
                if not user_data:
                    messagebox.showerror("登入失敗", "後端回傳資料異常")
                    return
                
                # 檢查帳號是否啟用
                if not user_data.get('is_active', True):
                    messagebox.showerror(
                        "登入失敗", 
                        "帳號已停用\n\n請聯絡系統管理員"
                    )
                    return
                
                print(f"✅ 登入成功: {user_data.get('username')} ({user_data.get('role_name', 'Unknown')})")
                
                # 準備使用者資訊（標準化格式）
                user_info = {
                    'id': user_data.get('id'),
                    'username': user_data.get('username', username),
                    'full_name': user_data.get('full_name', username),
                    'email': user_data.get('email', ''),
                    'role': user_data.get('role_code', 'user'),
                    'role_name': user_data.get('role_name', '使用者'),
                    'clinical_dept_id': user_data.get('clinical_dept_id'),
                    'clinical_dept_name': user_data.get('clinical_dept_name', ''),
                    'employee_id': user_data.get('employee_id', ''),
                    'phone': user_data.get('phone', ''),
                    'is_active': user_data.get('is_active', True)
                }
                
                # 登入成功，呼叫回調函數
                self.on_login_success(user_info)
                
            elif result.get('status') == 'error':
                # 根據錯誤類型顯示不同訊息
                error_code = result.get('error_code', 'unknown')
                error_message = result.get('message', '登入失敗')
                
                if error_code == 'user_not_found':
                    messagebox.showerror("登入失敗", "帳號不存在")
                elif error_code == 'wrong_password':
                    messagebox.showerror("登入失敗", "密碼錯誤")
                elif error_code == 'account_disabled':
                    messagebox.showerror("登入失敗", "帳號已停用\n\n請聯絡系統管理員")
                else:
                    messagebox.showerror("登入失敗", error_message)
            else:
                messagebox.showerror("登入失敗", "後端回傳格式異常")

        except Exception as e:
            messagebox.showerror("錯誤", f"登入過程發生錯誤:\n\n{str(e)}")
            print(f"❌ 登入錯誤: {e}")
            import traceback
            traceback.print_exc()