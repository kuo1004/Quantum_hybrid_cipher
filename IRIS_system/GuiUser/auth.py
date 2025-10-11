# -*- coding: utf-8 -*-
"""
auth.py - 登入與使用者認證模組
"""
import customtkinter as ctk
from tkinter import messagebox
from .database import connect_db
from .config import COLOR, FONT, Card, SolidBtn, PAD

class LoginWindow:
    """登入視窗類別"""

    def __init__(self, root, on_login_success):
        self.root = root
        self.on_login_success = on_login_success
        self.setup_ui()

    def setup_ui(self):
        """設置登入介面"""
        for w in self.root.winfo_children():
            w.destroy()

        wrap = ctk.CTkFrame(self.root, fg_color=COLOR["bg"])
        wrap.pack(fill="both", expand=True)

        card = Card(wrap)
        card.place(relx=0.5, rely=0.5, anchor="center")
        card.configure(width=460, height=500)
        card.pack_propagate(False)

        box = ctk.CTkFrame(card, fg_color=COLOR["surface"])
        box.pack(fill="both", expand=True, padx=PAD, pady=PAD)

        ctk.CTkLabel(box, text="IRIS 智慧影像系統", font=FONT["logo"], 
                    text_color=COLOR["ink"]).pack(anchor="w")
        ctk.CTkLabel(box, text="醫療影像管理平台", font=FONT["body"], 
                    text_color=COLOR["inksubtle"]).pack(anchor="w", pady=(2, 12))

        ctk.CTkLabel(box, text="使用者名稱", font=FONT["meta"], 
                    text_color=COLOR["inksubtle"]).pack(anchor="w")
        self.userentry = ctk.CTkEntry(box, placeholder_text="Username", height=44, 
                                     corner_radius=12, font=FONT["body"])
        self.userentry.pack(fill="x", pady=(6, 14))

        ctk.CTkLabel(box, text="密碼", font=FONT["meta"], 
                    text_color=COLOR["inksubtle"]).pack(anchor="w")
        self.pwentry = ctk.CTkEntry(box, placeholder_text="Password", show="•", 
                                   height=44, corner_radius=12, font=FONT["body"])
        self.pwentry.pack(fill="x", pady=(6, 18))
        self.pwentry.bind("<Return>", lambda e: self.login())

        SolidBtn(box, "登入", self.login).pack(fill="x")

        # 預設帳號提示
        info_frame = ctk.CTkFrame(box, fg_color=COLOR["chip"], corner_radius=8)
        info_frame.pack(fill="x", pady=(16, 0))

        ctk.CTkLabel(info_frame, text="📋 預設帳號 (帳號/密碼)", 
                    font=ctk.CTkFont(size=12, weight="bold"), 
                    text_color=COLOR["primary"]).pack(pady=(8, 4))

        accounts = [
            "👨‍⚕️ 醫師: doctor1 / 123",
            "🔬 放射師: radiologist1 / 123",
            "👩‍⚕️ 護理師: nurse1 / 123",
            "🔧 管理員: admin / 123"
        ]

        for acc in accounts:
            ctk.CTkLabel(info_frame, text=acc, font=FONT["meta"], 
                        text_color=COLOR["inksubtle"]).pack(pady=2)

        ctk.CTkLabel(info_frame, text="🎬 支援影片直接播放", 
                    font=FONT["meta"], 
                    text_color=COLOR["success"]).pack(pady=(4, 8))

    def login(self):
        """執行登入驗證"""
        u = (self.userentry.get() or "").strip()
        p = (self.pwentry.get() or "").strip()

        if not u or not p:
            messagebox.showwarning("警告", "請輸入帳號和密碼")
            return

        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, username, password, role FROM users WHERE UPPER(username)=UPPER(?) LIMIT 1",
                (u,)
            )
            row = cursor.fetchone()
            conn.close()

            if not row:
                messagebox.showerror("登入失敗", f"找不到使用者: {u}")
                return

            uid, uname, storedpw, roleraw = row

            if (storedpw or "") != p:
                messagebox.showerror("登入失敗", "密碼錯誤")
                return

            role = (roleraw or "nurse").strip().lower()
            user_info = {"id": uid, "role": role, "username": uname}

            # 登入成功，呼叫回調函數
            self.on_login_success(user_info)

        except Exception as e:
            messagebox.showerror("錯誤", f"登入失敗: {str(e)}")
