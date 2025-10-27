# -*- coding: utf-8 -*-
"""
main.py - IRIS 主程式入口（本地暫存版）
"""
import customtkinter as ctk
from datetime import datetime
from GuiUser.config import init_fonts, COLOR, FONT, tabs_for_role, ROLE_ZH, Card, OutlineBtn, PAD, GAP
from GuiUser.auth import LoginWindow
from GuiUser.upload_tab import UploadTab
from GuiUser.images_tab import ImagesTab
from GuiUser.patients_tab import PatientsTab
from GuiUser.transmission_status_tab import TransmissionStatusTab
from GuiUser.api_client import get_api_client
from GuiUser.local_image_manager import get_local_image_manager

class MainApp:
    def __init__(self):
        # 1. 建立 root 視窗
        self.root = ctk.CTk()
        self.root.title("IRIS 智慧影像系統")
        self.root.geometry("1260x860")
        self.root.minsize(1120, 760)
        self.root.configure(fg_color=COLOR["bg"])

        # 2. 初始化字體
        init_fonts()

        # 3. 初始化 API Client
        self.api_client = get_api_client()
        
        # 4. 初始化本地影像管理器
        self.local_manager = get_local_image_manager()
        
        # 5. 註冊關閉時的清理函數
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 6. 檢查後端連接
        self.check_backend_connection()

        self.user = None
        self.tabs = {}

        self.show_login()

    def check_backend_connection(self):
        """檢查後端連接狀態"""
        try:
            health = self.api_client.health_check()
            if health:
                print("✅ 成功連接到 Hospital Server")
                print(f"   Server: {health.get('receiver_id', 'Unknown')}")
                print(f"   資料庫: {health.get('database', {}).get('image_count', 0)} 張影像")
            else:
                print("⚠️ 無法連接到 Hospital Server")
                print("   請確認 Server 是否正在運行")
        except Exception as e:
            print(f"⚠️ 後端連接檢查失敗: {e}")

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
                UploadTab(
                    self.tabview.tab(tab_name), 
                    self.user, 
                    self.toast, 
                    self.reload_images, 
                    self.switch_tab,
                    self.local_manager  # 傳入本地管理器
                )
            elif tab_name == "影像清單":
                self.tabs["images"] = ImagesTab(
                    self.tabview.tab(tab_name), 
                    self.user, 
                    self.root,
                    self.local_manager  # 傳入本地管理器
                )
            elif tab_name == "病人管理":
                PatientsTab(self.tabview.tab(tab_name), self.user, self.root)
            elif tab_name == "首頁":
                self.build_dashboard(self.tabview.tab(tab_name))
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
        
        # 顯示連接狀態
        status_frame = ctk.CTkFrame(wrap, fg_color="transparent")
        status_frame.pack(anchor="w", pady=(6, 0))
        
        health = self.api_client.health_check()
        if health:
            status_text = f"✅ 已連接到 Hospital Server | 資料庫: {health.get('database', {}).get('image_count', 0)} 張影像"
            status_color = COLOR["success"]
        else:
            status_text = "⚠️ 無法連接到 Hospital Server"
            status_color = COLOR["danger"]
        
        ctk.CTkLabel(
            status_frame, 
            text=status_text, 
            font=FONT["body"],
            text_color=status_color
        ).pack(anchor="w")
        
        # 顯示本地暫存統計
        stats = self.local_manager.get_stats()
        local_text = f"💾 本地暫存: {stats['total_images']} 張影像 ({stats['total_size_mb']} MB)"
        
        ctk.CTkLabel(
            status_frame, 
            text=local_text, 
            font=FONT["meta"],
            text_color=COLOR["primary"]
        ).pack(anchor="w", pady=(4, 0))
        
        ctk.CTkLabel(
            status_frame, 
            text="醫療影像管理系統（本地暫存版 - 關閉時自動清除）", 
            font=FONT["meta"],
            text_color=COLOR["inksubtle"]
        ).pack(anchor="w", pady=(4, 0))

    def toast(self, text, kind="info"):
        color = {"info": COLOR["primary"], "success": COLOR["success"], 
                 "danger": COLOR["danger"]}.get(kind, COLOR["primary"])
        bar = ctk.CTkFrame(self.root, fg_color=color)
        bar.place(relx=0.5, rely=0.02, anchor="n")
        ctk.CTkLabel(bar, text=text, font=FONT["meta"], text_color="white").pack(padx=12, pady=8)
        bar.after(2400, bar.destroy)

    def reload_images(self):
        """重新載入影像列表"""
        if "images" in self.tabs:
            self.tabs["images"].reload_images()

    def switch_tab(self, name):
        self.tabview.set(name)

    def logout(self):
        self.user = None
        self.show_login()

    def on_closing(self):
        """關閉程式時的清理"""
        print("\n🔄 正在關閉程式...")
        
        # 清理本地暫存
        try:
            stats = self.local_manager.get_stats()
            if stats['total_images'] > 0:
                print(f"📁 清理本地暫存: {stats['total_images']} 張影像 ({stats['total_size_mb']} MB)")
                self.local_manager.cleanup()
                print("✅ 本地暫存已清除")
            else:
                print("✅ 沒有需要清理的暫存")
        except Exception as e:
            print(f"⚠️ 清理本地暫存時發生錯誤: {e}")
        

        self.root.destroy()

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = MainApp()
    app.run()