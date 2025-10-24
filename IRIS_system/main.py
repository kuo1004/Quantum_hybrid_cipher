# -*- coding: utf-8 -*-
"""
main.py - IRIS 主程式入口（修正版 v2）
"""
import customtkinter as ctk
from datetime import datetime
from GuiUser.database import init_database
from GuiUser.config import init_fonts, COLOR, FONT, tabs_for_role, ROLE_ZH, Card, OutlineBtn, PAD, GAP
from GuiUser.auth import LoginWindow
from GuiUser.upload_tab import UploadTab
from GuiUser.images_tab import ImagesTab
from GuiUser.patients_tab import PatientsTab
from GuiUser.transmission_status_tab import TransmissionStatusTab

class MainApp:
    def __init__(self):
        # 1. 先初始化資料庫
        init_database()

        # 2. 建立 root 視窗
        self.root = ctk.CTk()
        self.root.title("IRIS 智慧影像系統")
        self.root.geometry("1260x860")
        self.root.minsize(1120, 760)
        self.root.configure(fg_color=COLOR["bg"])

        # 3. 在建立 root 後初始化字體（重要！）
        init_fonts()

        self.user = None
        self.tabs = {}

        self.show_login()

    def show_login(self):
        LoginWindow(self.root, self.on_login_success)

    def on_login_success(self, user_info):
        self.user = user_info
        self.show_main()

    def show_main(self):
        for w in self.root.winfo_children():
            w.destroy()

        # 頂部
        top = ctk.CTkFrame(self.root, fg_color=COLOR["bg"], height=76)
        top.pack(fill="x", padx=PAD, pady=(PAD, 0))
        top.pack_propagate(False)

        left = ctk.CTkFrame(top, fg_color="transparent")
        left.pack(side="left")
        ctk.CTkLabel(left, text="IRIS 智慧影像系統", font=FONT["logo"]).pack(anchor="w")
        ctk.CTkLabel(left, text=datetime.now().strftime("%Y-%m-%d %H:%M"), 
                    font=FONT["meta"]).pack(anchor="w")

        right = ctk.CTkFrame(top, fg_color="transparent")
        right.pack(side="right")

        chip = ctk.CTkFrame(right, fg_color=COLOR["chip"], corner_radius=999)
        chip.pack(side="right", padx=(0, 8))

        rolezh = ROLE_ZH.get(self.user["role"], self.user["role"])
        ctk.CTkLabel(chip, text=f"{self.user['username']} ({rolezh})", 
                    font=FONT["meta"], text_color=COLOR["primary"]).pack(padx=12, pady=8)

        OutlineBtn(right, "登出", self.logout, w=88, h=36).pack(side="right", padx=(0, 8))

        # 標籤頁
        self.tabview = ctk.CTkTabview(self.root, segmented_button_fg_color=COLOR["surfacealt"])
        self.tabview.pack(fill="both", expand=True, padx=PAD, pady=(PAD, PAD))

        for tab_name in tabs_for_role(self.user["role"]):
            self.tabview.add(tab_name)

            if tab_name == "上傳影像":
                UploadTab(self.tabview.tab(tab_name), self.user, 
                         self.toast, self.reload_images, self.switch_tab)
            elif tab_name == "影像清單":
                self.tabs["images"] = ImagesTab(self.tabview.tab(tab_name), self.user, self.root)
            elif tab_name == "病人管理":
                PatientsTab(self.tabview.tab(tab_name), self.user, self.root)
            elif tab_name == "首頁":
                self.build_dashboard(self.tabview.tab(tab_name))
            # 在 main.py 的 show_main 方法中
            elif tab_name == "傳輸狀態":
                self.tabs["transmission"] = TransmissionStatusTab(
                    self.tabview.tab(tab_name), 
                    self.user
                )


    def build_dashboard(self, root):
        card = Card(root)
        card.pack(fill="x", pady=(0, GAP))

        wrap = ctk.CTkFrame(card, fg_color=COLOR["surface"])
        wrap.pack(fill="x", padx=PAD, pady=PAD)

        rolezh = ROLE_ZH.get(self.user["role"], self.user["role"])
        ctk.CTkLabel(wrap, text=f"歡迎, {self.user['username']} ({rolezh})", 
                    font=FONT["h1"]).pack(anchor="w")
        ctk.CTkLabel(wrap, text="醫療影像管理系統 (支援影片播放)", font=FONT["body"]).pack(anchor="w", pady=(6, 0))

    def toast(self, text, kind="info"):
        color = {"info": COLOR["primary"], "success": COLOR["success"], 
                 "danger": COLOR["danger"]}.get(kind, COLOR["primary"])
        bar = ctk.CTkFrame(self.root, fg_color=color)
        bar.place(relx=0.5, rely=0.02, anchor="n")
        ctk.CTkLabel(bar, text=text, font=FONT["meta"], text_color="white").pack(padx=12, pady=8)
        bar.after(2400, bar.destroy)

    def reload_images(self):
        if "images" in self.tabs:
            self.tabs["images"].reload_images()

    def switch_tab(self, name):
        self.tabview.set(name)

    def logout(self):
        self.user = None
        self.show_login()

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = MainApp()
    app.run()