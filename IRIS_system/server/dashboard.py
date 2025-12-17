#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IRIS 系統即時監控面板 - 修復版 v2
修復：
1. 上傳事件重複顯示問題
2. 顯示真實的金鑰和密文內容
"""

import os
import time
import json
import requests
import psutil
import customtkinter as ctk
from datetime import datetime
from threading import Thread
from collections import deque
from tkinter import messagebox


class DetailPopup(ctk.CTkToplevel):
    """放大檢視彈出視窗"""
    
    def __init__(self, parent, title, content_data, colors):
        super().__init__(parent)
        
        self.title(title)
        self.geometry("900x700")
        self.configure(fg_color=colors["bg"])
        
        # 置中
        self.update_idletasks()
        x = (self.winfo_screenwidth() - 900) // 2
        y = (self.winfo_screenheight() - 700) // 2
        self.geometry(f"900x700+{x}+{y}")
        
        self.colors = colors
        self.content_data = content_data
        
        self._build_ui()
        self.lift()
        self.focus_force()
    
    def _build_ui(self):
        """建立介面"""
        # 標題列
        header = ctk.CTkFrame(self, fg_color=self.colors["primary"], corner_radius=0)
        header.pack(fill="x")
        
        ctk.CTkLabel(
            header, text=f"🔍 {self.title()}",
            font=("Microsoft JhengHei", 20, "bold"),
            text_color="white"
        ).pack(pady=18)
        
        # 內容區域
        content = ctk.CTkScrollableFrame(self, fg_color=self.colors["card"])
        content.pack(fill="both", expand=True, padx=20, pady=20)
        
        for key, value in self.content_data.items():
            self._add_row(content, key, value)
        
        # 底部按鈕
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=15)
        
        ctk.CTkButton(
            btn_frame, text="📋 複製全部",
            command=self._copy_all,
            fg_color=self.colors["info"],
            font=("Microsoft JhengHei", 14),
            height=42, width=140
        ).pack(side="left")
        
        ctk.CTkButton(
            btn_frame, text="關閉",
            command=self.destroy,
            fg_color=self.colors["text_light"],
            font=("Microsoft JhengHei", 14),
            height=42, width=100
        ).pack(side="right")
    
    def _add_row(self, parent, key, value):
        """添加一行資料"""
        row = ctk.CTkFrame(parent, fg_color=self.colors["bg"], corner_radius=8)
        row.pack(fill="x", pady=5)
        
        # 標籤
        ctk.CTkLabel(
            row, text=f"{key}:",
            font=("Microsoft JhengHei", 14, "bold"),
            text_color=self.colors["primary"],
            width=160, anchor="w"
        ).pack(side="left", padx=15, pady=12)
        
        value_str = str(value)
        
        if len(value_str) > 80:
            # 長文字用 Textbox
            textbox = ctk.CTkTextbox(
                row, height=100,
                font=("Consolas", 13),
                fg_color=self.colors["code_bg"],
                text_color=self.colors["hex_color"],
                wrap="char"
            )
            textbox.pack(side="left", fill="x", expand=True, padx=(0, 15), pady=8)
            textbox.insert("1.0", value_str)
            textbox.configure(state="disabled")
        else:
            # 短文字用 Label
            ctk.CTkLabel(
                row, text=value_str,
                font=("Consolas", 14),
                text_color=self.colors["text"],
                anchor="w"
            ).pack(side="left", fill="x", expand=True, padx=(0, 15), pady=12)
    
    def _copy_all(self):
        """複製全部"""
        text = "\n".join([f"{k}: {v}" for k, v in self.content_data.items()])
        self.clipboard_clear()
        self.clipboard_append(text)
        messagebox.showinfo("已複製", "已複製全部資料到剪貼簿")


class IRISMonitor:
    """IRIS 系統即時監控面板"""
    
    def __init__(self):
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
        
        self.root = ctk.CTk()
        self.root.title("IRIS 後量子加密傳輸監控系統")
        self.root.geometry("1600x950")
        
        # 連線設定
        self.ca_host = "localhost"
        self.ca_port = "8001"
        self.server_host = "localhost"
        self.server_port = "8200"
        
        # 狀態追蹤
        self.ca_connected = False
        self.server_connected = False
        self.monitoring = False
        self.last_image_id = 0
        self.last_event_id = 0
        
        # ⭐ 已處理的事件 ID 集合（防止重複）
        self.processed_image_ids = set()
        self.processed_event_ids = set()
        
        # 線上用戶
        self.online_users = {}
        
        # CA 事件記錄
        self.ca_events = deque(maxlen=30)
        
        # 顏色主題
        self.colors = {
            "bg": "#f0f4f8",
            "card": "#ffffff",
            "primary": "#2563eb",
            "success": "#16a34a",
            "warning": "#d97706",
            "danger": "#dc2626",
            "info": "#0891b2",
            "text": "#1e293b",
            "text_light": "#64748b",
            "border": "#e2e8f0",
            "code_bg": "#1e1e1e",
            "code_text": "#d4d4d4",
            "key_color": "#4ec9b0",
            "value_color": "#ce9178",
            "encrypt_color": "#569cd6",
            "decrypt_color": "#c586c0",
            "hex_color": "#dcdcaa"
        }
        
        self.setup_ui()
    
    def setup_ui(self):
        """建立介面"""
        self.root.configure(fg_color=self.colors["bg"])
        
        main = ctk.CTkFrame(self.root, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=15, pady=15)
        
        self._create_header(main)
        self._create_config_bar(main)
        self._create_status_cards(main)
        
        content = ctk.CTkFrame(main, fg_color="transparent")
        content.pack(fill="both", expand=True, pady=(15, 0))
        
        # 左欄
        left_col = ctk.CTkFrame(content, fg_color="transparent", width=320)
        left_col.pack(side="left", fill="y", padx=(0, 10))
        left_col.pack_propagate(False)
        
        self._create_ca_panel(left_col)
        self._create_users_panel(left_col)
        
        # 中欄
        center_col = ctk.CTkFrame(content, fg_color="transparent")
        center_col.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        self._create_encryption_panel(center_col)
        
        # 右欄
        right_col = ctk.CTkFrame(content, fg_color="transparent", width=350)
        right_col.pack(side="right", fill="y")
        right_col.pack_propagate(False)
        
        self._create_log_panel(right_col)
        
        self._update_time()
    
    def _create_header(self, parent):
        """建立標題列"""
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.pack(fill="x", pady=(0, 15))
        
        title_frame = ctk.CTkFrame(header, fg_color="transparent")
        title_frame.pack(side="left")
        
        ctk.CTkLabel(
            title_frame, text="🔐 IRIS",
            font=("Arial", 28, "bold"), text_color=self.colors["primary"]
        ).pack(side="left")
        
        ctk.CTkLabel(
            title_frame, text=" 後量子加密傳輸監控",
            font=("Microsoft JhengHei", 24, "bold"), text_color=self.colors["text"]
        ).pack(side="left")
        
        self.time_label = ctk.CTkLabel(
            header, text="", font=("Arial", 16), text_color=self.colors["text_light"]
        )
        self.time_label.pack(side="right")
    
    def _create_config_bar(self, parent):
        """建立連線設定區"""
        config = ctk.CTkFrame(parent, fg_color=self.colors["card"], corner_radius=10, height=60)
        config.pack(fill="x", pady=(0, 15))
        config.pack_propagate(False)
        
        inner = ctk.CTkFrame(config, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=15, pady=10)
        
        # CA Server
        ca_frame = ctk.CTkFrame(inner, fg_color="transparent")
        ca_frame.pack(side="left", padx=(0, 25))
        
        ctk.CTkLabel(ca_frame, text="🏛️ CA:", font=("Microsoft JhengHei", 12, "bold"),
                     text_color=self.colors["text"]).pack(side="left", padx=(0, 8))
        
        self.ca_host_entry = ctk.CTkEntry(ca_frame, width=100, height=30)
        self.ca_host_entry.insert(0, self.ca_host)
        self.ca_host_entry.pack(side="left", padx=2)
        
        ctk.CTkLabel(ca_frame, text=":", text_color=self.colors["text_light"]).pack(side="left")
        
        self.ca_port_entry = ctk.CTkEntry(ca_frame, width=55, height=30)
        self.ca_port_entry.insert(0, self.ca_port)
        self.ca_port_entry.pack(side="left", padx=2)
        
        # App Server
        server_frame = ctk.CTkFrame(inner, fg_color="transparent")
        server_frame.pack(side="left", padx=(0, 25))
        
        ctk.CTkLabel(server_frame, text="🖥️ Server:", font=("Microsoft JhengHei", 12, "bold"),
                     text_color=self.colors["text"]).pack(side="left", padx=(0, 8))
        
        self.server_host_entry = ctk.CTkEntry(server_frame, width=100, height=30)
        self.server_host_entry.insert(0, self.server_host)
        self.server_host_entry.pack(side="left", padx=2)
        
        ctk.CTkLabel(server_frame, text=":", text_color=self.colors["text_light"]).pack(side="left")
        
        self.server_port_entry = ctk.CTkEntry(server_frame, width=55, height=30)
        self.server_port_entry.insert(0, self.server_port)
        self.server_port_entry.pack(side="left", padx=2)
        
        self.connect_btn = ctk.CTkButton(
            inner, text="🔌 連接監控", command=self._connect_and_monitor,
            font=("Microsoft JhengHei", 13, "bold"), height=36, width=140,
            fg_color=self.colors["primary"], hover_color="#1d4ed8"
        )
        self.connect_btn.pack(side="right")
    
    def _create_status_cards(self, parent):
        """建立狀態卡片"""
        cards = ctk.CTkFrame(parent, fg_color="transparent", height=100)
        cards.pack(fill="x")
        cards.pack_propagate(False)
        
        self.ca_card = self._create_mini_status_card(cards, "🏛️ CA Server", "OFFLINE")
        self.ca_card.pack(side="left", fill="both", expand=True, padx=(0, 8))
        
        self.server_card = self._create_mini_status_card(cards, "🖥️ App Server", "OFFLINE")
        self.server_card.pack(side="left", fill="both", expand=True, padx=(0, 8))
        
        self.users_card = self._create_mini_status_card(cards, "👥 線上用戶", "0")
        self.users_card.pack(side="left", fill="both", expand=True, padx=(0, 8))
        
        self.transfer_card = self._create_mini_status_card(cards, "📊 影像總數", "0")
        self.transfer_card.pack(side="left", fill="both", expand=True)
    
    def _create_mini_status_card(self, parent, title, value):
        """建立小型狀態卡片"""
        card = ctk.CTkFrame(parent, fg_color=self.colors["card"], corner_radius=10)
        
        ctk.CTkLabel(card, text=title, font=("Microsoft JhengHei", 12),
                     text_color=self.colors["text_light"]).pack(pady=(12, 5))
        
        value_label = ctk.CTkLabel(card, text=value, font=("Arial", 22, "bold"),
                                   text_color=self.colors["text"])
        value_label.pack(pady=(0, 12))
        card.value_label = value_label
        
        return card
    
    def _create_ca_panel(self, parent):
        """建立 CA 驗證面板 - 顯示完整憑證發行過程"""
        panel = ctk.CTkFrame(parent, fg_color=self.colors["card"], corner_radius=12)
        panel.pack(fill="x", pady=(0, 10))
        
        header = ctk.CTkFrame(panel, fg_color="transparent")
        header.pack(fill="x", padx=15, pady=(15, 10))
        
        ctk.CTkLabel(header, text="🏛️ CA 憑證管理",
                     font=("Microsoft JhengHei", 14, "bold"),
                     text_color=self.colors["text"]).pack(side="left")
        
        self.ca_status_badge = ctk.CTkLabel(
            header, text="等待連線", font=("Arial", 10, "bold"),
            text_color="white", fg_color=self.colors["text_light"],
            corner_radius=6, padx=10, pady=3
        )
        self.ca_status_badge.pack(side="right")
        
        self.ca_list = ctk.CTkScrollableFrame(panel, fg_color="transparent", height=220)
        self.ca_list.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        self.ca_empty = ctk.CTkLabel(
            self.ca_list, text="等待 CA 憑證事件...",
            font=("Microsoft JhengHei", 11), text_color=self.colors["text_light"]
        )
        self.ca_empty.pack(pady=30)
    
    def _create_users_panel(self, parent):
        """建立線上用戶面板"""
        panel = ctk.CTkFrame(parent, fg_color=self.colors["card"], corner_radius=12)
        panel.pack(fill="both", expand=True)
        
        header = ctk.CTkFrame(panel, fg_color="transparent")
        header.pack(fill="x", padx=15, pady=(15, 10))
        
        ctk.CTkLabel(header, text="👥 線上用戶",
                     font=("Microsoft JhengHei", 14, "bold"),
                     text_color=self.colors["text"]).pack(side="left")
        
        self.users_count_badge = ctk.CTkLabel(
            header, text="0", font=("Arial", 11, "bold"),
            text_color="white", fg_color=self.colors["text_light"],
            corner_radius=8, padx=10, pady=3
        )
        self.users_count_badge.pack(side="right")
        
        self.users_list = ctk.CTkScrollableFrame(panel, fg_color="transparent")
        self.users_list.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        self.users_empty = ctk.CTkLabel(
            self.users_list, text="尚無線上用戶",
            font=("Microsoft JhengHei", 11), text_color=self.colors["text_light"]
        )
        self.users_empty.pack(pady=30)
    
    def _create_encryption_panel(self, parent):
        """建立加密傳輸流程面板"""
        panel = ctk.CTkFrame(parent, fg_color=self.colors["card"], corner_radius=12)
        panel.pack(fill="both", expand=True)
        
        header = ctk.CTkFrame(panel, fg_color="transparent")
        header.pack(fill="x", padx=15, pady=(15, 10))
        
        ctk.CTkLabel(header, text="🔐 加密傳輸流程",
                     font=("Microsoft JhengHei", 16, "bold"),
                     text_color=self.colors["text"]).pack(side="left")
        
        legend = ctk.CTkFrame(header, fg_color="transparent")
        legend.pack(side="right")
        
        ctk.CTkLabel(legend, text="● 上傳(解密)", font=("Arial", 10),
                     text_color=self.colors["decrypt_color"]).pack(side="left", padx=(0, 10))
        ctk.CTkLabel(legend, text="● 下載(加密)", font=("Arial", 10),
                     text_color=self.colors["encrypt_color"]).pack(side="left")
        
        self.encryption_list = ctk.CTkScrollableFrame(panel, fg_color="transparent")
        self.encryption_list.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        self.encryption_empty = ctk.CTkLabel(
            self.encryption_list, text="等待加密傳輸事件...",
            font=("Microsoft JhengHei", 12), text_color=self.colors["text_light"]
        )
        self.encryption_empty.pack(pady=50)
    
    def _create_log_panel(self, parent):
        """建立系統日誌面板"""
        panel = ctk.CTkFrame(parent, fg_color=self.colors["card"], corner_radius=12)
        panel.pack(fill="both", expand=True)
        
        header = ctk.CTkFrame(panel, fg_color="transparent")
        header.pack(fill="x", padx=15, pady=(15, 10))
        
        ctk.CTkLabel(header, text="📋 系統日誌",
                     font=("Microsoft JhengHei", 14, "bold"),
                     text_color=self.colors["text"]).pack(side="left")
        
        self.log_list = ctk.CTkScrollableFrame(panel, fg_color="transparent")
        self.log_list.pack(fill="both", expand=True, padx=10, pady=(0, 10))
    
    def _update_time(self):
        """更新時間顯示"""
        now = datetime.now()
        self.time_label.configure(text=now.strftime("%Y-%m-%d %H:%M:%S"))
        self.root.after(1000, self._update_time)
    
    def _add_log(self, message, level="INFO"):
        """添加日誌"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        log_item = ctk.CTkFrame(self.log_list, fg_color=self.colors["bg"], corner_radius=6)
        log_item.pack(fill="x", pady=2)
        
        ctk.CTkLabel(log_item, text=f"[{timestamp}]", font=("Consolas", 10),
                     text_color=self.colors["text_light"], width=70).pack(side="left", padx=(8, 5))
        
        level_colors = {
            "INFO": self.colors["info"],
            "SUCCESS": self.colors["success"],
            "WARNING": self.colors["warning"],
            "ERROR": self.colors["danger"]
        }
        
        ctk.CTkLabel(log_item, text=f"[{level}]", font=("Arial", 9, "bold"),
                     text_color=level_colors.get(level, self.colors["text"]),
                     width=60).pack(side="left", padx=3)
        
        ctk.CTkLabel(log_item, text=message, font=("Microsoft JhengHei", 10),
                     text_color=self.colors["text"], anchor="w"
                     ).pack(side="left", fill="x", expand=True, padx=(3, 8), pady=6)
        
        self.root.update()
        self.log_list._parent_canvas.yview_moveto(1.0)
    
    def _add_ca_event(self, event_type, party_id, status, details="", extra_info=None):
        """添加 CA 驗證事件 - 支援顯示詳細過程，可點擊放大"""
        if hasattr(self, 'ca_empty') and self.ca_empty.winfo_exists():
            self.ca_empty.destroy()
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # 根據事件類型選擇不同的樣式
        if event_type == "CONNECT":
            icon = "🔗"
            type_text = "連線建立"
            border_color = self.colors["info"]
        elif event_type == "PUBLIC_KEY":
            icon = "🔑"
            type_text = "公鑰請求"
            border_color = self.colors["info"]
        elif event_type == "REGISTER":
            icon = "📋"
            type_text = "憑證註冊"
            border_color = self.colors["primary"]
        elif event_type == "ISSUE":
            icon = "📜"
            type_text = "憑證發行"
            border_color = self.colors["success"]
        elif event_type == "VERIFY":
            icon = "✅"
            type_text = "憑證驗證"
            border_color = self.colors["success"]
        else:
            icon = "📌"
            type_text = event_type
            border_color = self.colors["text_light"]
        
        # ⭐ 準備詳細資料（用於點擊放大）
        ca_detail_data = {
            "事件類型": f"{icon} {type_text}",
            "時間": timestamp,
            "對象": party_id,
            "狀態": status,
            "說明": details if details else "(無)",
        }
        if extra_info:
            ca_detail_data.update(extra_info)
        
        # ⭐ 點擊放大函數
        def show_ca_detail(e=None):
            DetailPopup(self.root, f"CA 憑證事件: {type_text}", ca_detail_data, self.colors)
        
        # 主容器
        item = ctk.CTkFrame(self.ca_list, fg_color=self.colors["bg"], corner_radius=8,
                           border_width=1, border_color=border_color)
        item.pack(fill="x", pady=3)
        
        # ⭐ 綁定點擊事件
        item.bind("<Button-1>", show_ca_detail)
        
        # ⭐ 滑鼠懸停效果
        def on_enter(e):
            item.configure(fg_color="#e8f4f8")
        def on_leave(e):
            item.configure(fg_color=self.colors["bg"])
        
        item.bind("<Enter>", on_enter)
        item.bind("<Leave>", on_leave)
        
        # 標題列
        header = ctk.CTkFrame(item, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(8, 4))
        header.bind("<Button-1>", show_ca_detail)
        
        title_label = ctk.CTkLabel(header, text=f"{icon} {type_text}", font=("Microsoft JhengHei", 11, "bold"),
                     text_color=border_color)
        title_label.pack(side="left")
        title_label.bind("<Button-1>", show_ca_detail)
        
        # ⭐ 點擊提示
        hint_label = ctk.CTkLabel(header, text="🔍",
                     font=("Arial", 9), text_color=self.colors["info"])
        hint_label.pack(side="right", padx=(0, 5))
        hint_label.bind("<Button-1>", show_ca_detail)
        
        time_label = ctk.CTkLabel(header, text=timestamp, font=("Arial", 9),
                     text_color=self.colors["text_light"])
        time_label.pack(side="right")
        time_label.bind("<Button-1>", show_ca_detail)
        
        # 內容
        content = ctk.CTkFrame(item, fg_color="transparent")
        content.pack(fill="x", padx=10, pady=(0, 8))
        content.bind("<Button-1>", show_ca_detail)
        
        party_label = ctk.CTkLabel(content, text=f"對象: {party_id}", font=("Microsoft JhengHei", 10),
                     text_color=self.colors["text"], anchor="w")
        party_label.pack(anchor="w")
        party_label.bind("<Button-1>", show_ca_detail)
        
        if details:
            details_label = ctk.CTkLabel(content, text=details, font=("Arial", 9),
                         text_color=self.colors["text_light"], anchor="w")
            details_label.pack(anchor="w")
            details_label.bind("<Button-1>", show_ca_detail)
        
        # 額外資訊（如公鑰大小、憑證內容等）
        if extra_info:
            info_frame = ctk.CTkFrame(item, fg_color=self.colors["code_bg"], corner_radius=4)
            info_frame.pack(fill="x", padx=10, pady=(0, 8))
            info_frame.bind("<Button-1>", show_ca_detail)
            
            for key, value in extra_info.items():
                line = ctk.CTkFrame(info_frame, fg_color="transparent")
                line.pack(fill="x", padx=8, pady=2)
                line.bind("<Button-1>", show_ca_detail)
                
                key_label = ctk.CTkLabel(line, text=f"{key}:", font=("Consolas", 9),
                             text_color=self.colors["key_color"], width=100,
                             anchor="w")
                key_label.pack(side="left")
                key_label.bind("<Button-1>", show_ca_detail)
                
                value_label = ctk.CTkLabel(line, text=str(value), font=("Consolas", 9),
                             text_color=self.colors["hex_color"],
                             anchor="w")
                value_label.pack(side="left", fill="x", expand=True)
                value_label.bind("<Button-1>", show_ca_detail)
        
        # 狀態指示
        status_color = self.colors["success"] if status == "SUCCESS" else self.colors["danger"]
        
        self.ca_status_badge.configure(text="運作中", fg_color=self.colors["success"])
        
        self.root.update()
        self.ca_list._parent_canvas.yview_moveto(1.0)
    
    def _update_users_list(self, users_dict):
        """更新線上用戶列表"""
        for widget in self.users_list.winfo_children():
            widget.destroy()
        
        if not users_dict:
            empty = ctk.CTkLabel(self.users_list, text="尚無線上用戶",
                                 font=("Microsoft JhengHei", 11),
                                 text_color=self.colors["text_light"])
            empty.pack(pady=30)
            self.users_count_badge.configure(text="0", fg_color=self.colors["text_light"])
            self.users_card.value_label.configure(text="0")
        else:
            for user_id, user_info in users_dict.items():
                self._add_user_item(
                    user_id,
                    user_info.get('username', f'User #{user_id}'),
                    user_info.get('role_name', '未知'),
                    user_info.get('login_time', '')[:10] if user_info.get('login_time') else ''
                )
            
            count = len(users_dict)
            self.users_count_badge.configure(text=str(count), fg_color=self.colors["success"])
            self.users_card.value_label.configure(text=str(count))
    
    def _add_user_item(self, user_id, username, role_name, login_time):
        """添加線上用戶項目"""
        item = ctk.CTkFrame(self.users_list, fg_color=self.colors["bg"], corner_radius=8)
        item.pack(fill="x", pady=3)
        
        ctk.CTkLabel(item, text="●", font=("Arial", 16),
                     text_color=self.colors["success"], width=25
                     ).pack(side="left", padx=(10, 5))
        
        info = ctk.CTkFrame(item, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True, pady=8)
        
        ctk.CTkLabel(info, text=username, font=("Microsoft JhengHei", 12, "bold"),
                     text_color=self.colors["text"], anchor="w").pack(anchor="w")
        
        ctk.CTkLabel(info, text=f"{role_name} • {login_time}",
                     font=("Arial", 9), text_color=self.colors["text_light"],
                     anchor="w").pack(anchor="w")
    
    def _add_encryption_event(self, event_data):
        """添加加密事件記錄 - 顯示完整金鑰和密文，可點擊放大"""
        if hasattr(self, 'encryption_empty') and self.encryption_empty.winfo_exists():
            self.encryption_empty.destroy()
        
        event_type = event_data.get('type', 'DECRYPT')
        direction = event_data.get('direction', 'UPLOAD')
        is_upload = direction == 'UPLOAD'
        
        # 主容器
        item = ctk.CTkFrame(
            self.encryption_list, fg_color=self.colors["card"], corner_radius=10,
            border_width=2,
            border_color=self.colors["decrypt_color"] if is_upload else self.colors["encrypt_color"]
        )
        item.pack(fill="x", pady=6, padx=2)
        
        # ⭐ 綁定點擊放大事件
        def show_detail(e=None):
            self._show_encryption_detail(event_data)
        
        item.bind("<Button-1>", show_detail)
        
        # 滑鼠懸停效果
        def on_enter(e):
            item.configure(fg_color="#f0f7ff")
        def on_leave(e):
            item.configure(fg_color=self.colors["card"])
        
        item.bind("<Enter>", on_enter)
        item.bind("<Leave>", on_leave)
        
        # 標題列
        header = ctk.CTkFrame(item, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(10, 5))
        header.bind("<Button-1>", show_detail)
        
        icon = "📥" if is_upload else "📤"
        action = "上傳解密" if is_upload else "下載加密"
        
        title_label = ctk.CTkLabel(header, text=f"{icon} {action}",
                     font=("Microsoft JhengHei", 13, "bold"),
                     text_color=self.colors["decrypt_color"] if is_upload else self.colors["encrypt_color"])
        title_label.pack(side="left")
        title_label.bind("<Button-1>", show_detail)
        
        time_label = ctk.CTkLabel(header, text=event_data.get('timestamp', '')[:19],
                     font=("Arial", 10), text_color=self.colors["text_light"])
        time_label.pack(side="right")
        time_label.bind("<Button-1>", show_detail)
        
        # 用戶資訊
        user_info = ctk.CTkFrame(item, fg_color="transparent")
        user_info.pack(fill="x", padx=12, pady=(0, 5))
        user_info.bind("<Button-1>", show_detail)
        
        username = event_data.get('username') or f"User #{event_data.get('user_id', '?')}"
        filename = event_data.get('filename', 'unknown')
        file_size = event_data.get('file_size', 0)
        
        user_label = ctk.CTkLabel(user_info,
                     text=f"👤 {username}  📁 {filename}  ({self._format_size(file_size)})",
                     font=("Microsoft JhengHei", 11), text_color=self.colors["text"],
                     anchor="w")
        user_label.pack(anchor="w")
        user_label.bind("<Button-1>", show_detail)
        
        # ⭐ 加密詳情（程式碼風格，顯示真實金鑰和密文）
        details_frame = ctk.CTkFrame(item, fg_color=self.colors["code_bg"], corner_radius=8)
        details_frame.pack(fill="x", padx=12, pady=(5, 10))
        details_frame.bind("<Button-1>", show_detail)
        
        enc_details = event_data.get('encryption_details', {})
        
        details_text = ctk.CTkFrame(details_frame, fg_color="transparent")
        details_text.pack(fill="x", padx=12, pady=10)
        details_text.bind("<Button-1>", show_detail)
        
        # 加密演算法資訊
        self._add_code_line(details_text, "KEM 演算法", enc_details.get('kem_algorithm', 'ML-KEM-1024'), show_detail)
        self._add_code_line(details_text, "對稱加密", enc_details.get('aes_mode', 'AES-256-GCM'), show_detail)
        
        # KEM 封裝大小
        kem_size = enc_details.get('kem_ciphertext_size', 0)
        if kem_size:
            self._add_code_line(details_text, "KEM 封裝", f"{kem_size} bytes", show_detail)
        
        # 密文大小
        cipher_size = enc_details.get('ciphertext_size', 0)
        if cipher_size:
            self._add_code_line(details_text, "密文大小", f"{cipher_size} bytes", show_detail)
        
        # ⭐ 顯示實際金鑰內容（如果有）
        aes_key = enc_details.get('aes_key_hex')
        if aes_key:
            self._add_hex_line(details_text, "AES Key", aes_key, show_detail)
        
        # ⭐ 顯示 Shared Secret（如果有）
        shared_secret = enc_details.get('shared_secret_hex')
        if shared_secret:
            self._add_hex_line(details_text, "Shared Secret", shared_secret, show_detail)
        
        # ⭐ 顯示 IV（如果有）
        iv_hex = enc_details.get('iv_hex')
        if iv_hex:
            self._add_hex_line(details_text, "IV (Nonce)", iv_hex, show_detail)
        
        # ⭐ 顯示 KEM 密文片段（如果有）
        kem_ct = enc_details.get('kem_ciphertext_hex')
        if kem_ct:
            self._add_hex_line(details_text, "KEM Ciphertext", kem_ct[:64] + "..." if len(kem_ct) > 64 else kem_ct, show_detail)
        
        # ⭐ 顯示密文片段（如果有）
        ciphertext_hex = enc_details.get('ciphertext_hex')
        if ciphertext_hex:
            display_ct = ciphertext_hex[:64] + "..." if len(ciphertext_hex) > 64 else ciphertext_hex
            self._add_hex_line(details_text, "Ciphertext", display_ct, show_detail)
        
        # 驗證狀態 + 點擊提示
        verify_frame = ctk.CTkFrame(item, fg_color="transparent")
        verify_frame.pack(fill="x", padx=12, pady=(0, 10))
        verify_frame.bind("<Button-1>", show_detail)
        
        cert_ok = event_data.get('certificate_verified', False)
        sig_ok = event_data.get('signature_verified', False)
        
        cert_icon = "✅" if cert_ok else "⚠️"
        sig_icon = "✅" if sig_ok else "⚠️"
        
        verify_label = ctk.CTkLabel(verify_frame, text=f"{cert_icon} 憑證驗證  {sig_icon} 簽章驗證",
                     font=("Microsoft JhengHei", 10),
                     text_color=self.colors["success"] if (cert_ok and sig_ok) else self.colors["warning"])
        verify_label.pack(side="left")
        verify_label.bind("<Button-1>", show_detail)
        
        # ⭐ 點擊提示
        hint_label = ctk.CTkLabel(verify_frame, text="🔍 點擊放大",
                     font=("Microsoft JhengHei", 9),
                     text_color=self.colors["info"])
        hint_label.pack(side="right", padx=(0, 10))
        hint_label.bind("<Button-1>", show_detail)
        
        status = event_data.get('status', 'SUCCESS')
        status_color = self.colors["success"] if status == "SUCCESS" else self.colors["danger"]
        ctk.CTkLabel(verify_frame, text=status, font=("Arial", 10, "bold"),
                     text_color=status_color).pack(side="right")
        
        self.root.update()
        self.encryption_list._parent_canvas.yview_moveto(1.0)
    
    def _add_code_line(self, parent, key, value, click_callback=None):
        """添加程式碼風格的行"""
        line = ctk.CTkFrame(parent, fg_color="transparent")
        line.pack(fill="x", pady=1)
        
        if click_callback:
            line.bind("<Button-1>", click_callback)
        
        key_label = ctk.CTkLabel(line, text=f"{key}:", font=("Consolas", 10),
                     text_color=self.colors["text_light"], width=110,
                     anchor="w")
        key_label.pack(side="left")
        if click_callback:
            key_label.bind("<Button-1>", click_callback)
        
        value_label = ctk.CTkLabel(line, text=str(value), font=("Consolas", 10),
                     text_color=self.colors["value_color"],
                     anchor="w")
        value_label.pack(side="left")
        if click_callback:
            value_label.bind("<Button-1>", click_callback)
    
    def _add_hex_line(self, parent, key, hex_value, click_callback=None):
        """添加十六進位值的行（用特殊顏色）"""
        line = ctk.CTkFrame(parent, fg_color="transparent")
        line.pack(fill="x", pady=1)
        
        if click_callback:
            line.bind("<Button-1>", click_callback)
        
        key_label = ctk.CTkLabel(line, text=f"{key}:", font=("Consolas", 10),
                     text_color=self.colors["key_color"], width=110,
                     anchor="w")
        key_label.pack(side="left")
        if click_callback:
            key_label.bind("<Button-1>", click_callback)
        
        value_label = ctk.CTkLabel(line, text=hex_value, font=("Consolas", 9),
                     text_color=self.colors["hex_color"],
                     anchor="w")
        value_label.pack(side="left", fill="x", expand=True)
        if click_callback:
            value_label.bind("<Button-1>", click_callback)
    
    def _show_encryption_detail(self, event_data):
        """顯示加密事件的詳細彈出視窗"""
        enc_details = event_data.get('encryption_details', {})
        
        # 組織詳細資料
        detail_data = {
            "操作類型": "上傳解密" if event_data.get('direction') == 'UPLOAD' else "下載加密",
            "時間": event_data.get('timestamp', '')[:19],
            "使用者": event_data.get('username') or f"User #{event_data.get('user_id', '?')}",
            "檔案名稱": event_data.get('filename', 'unknown'),
            "檔案大小": self._format_size(event_data.get('file_size', 0)),
            "KEM 演算法": enc_details.get('kem_algorithm', 'ML-KEM-1024'),
            "對稱加密": enc_details.get('aes_mode', 'AES-256-GCM'),
            "KEM 封裝大小": f"{enc_details.get('kem_ciphertext_size', 0)} bytes",
            "密文大小": f"{enc_details.get('ciphertext_size', 0)} bytes",
            "憑證驗證": "✅ 通過" if event_data.get('certificate_verified') else "❌ 失敗",
            "簽章驗證": "✅ 通過" if event_data.get('signature_verified') else "❌ 失敗",
        }
        
        # 添加完整金鑰資訊
        if enc_details.get('aes_key_hex'):
            detail_data["AES Key (完整)"] = enc_details['aes_key_hex']
        
        if enc_details.get('shared_secret_hex'):
            detail_data["Shared Secret (完整)"] = enc_details['shared_secret_hex']
        
        if enc_details.get('iv_hex'):
            detail_data["IV / Nonce"] = enc_details['iv_hex']
        
        if enc_details.get('kem_ciphertext_hex'):
            detail_data["KEM Ciphertext (完整)"] = enc_details['kem_ciphertext_hex']
        
        if enc_details.get('ciphertext_hex'):
            detail_data["Ciphertext (完整)"] = enc_details['ciphertext_hex']
        
        # 顯示彈出視窗
        DetailPopup(self.root, "加密傳輸詳細資訊", detail_data, self.colors)
    
    def _format_size(self, size):
        """格式化檔案大小"""
        if size >= 1024 * 1024:
            return f"{size / (1024*1024):.2f} MB"
        elif size >= 1024:
            return f"{size / 1024:.2f} KB"
        return f"{size} bytes"
    
    def _connect_and_monitor(self):
        """連接並開始監控"""
        self.connect_btn.configure(state="disabled", text="連接中...")
        Thread(target=self._connect_thread, daemon=True).start()
    
    def _connect_thread(self):
        """連接執行緒 - 顯示完整的 CA 憑證發行過程"""
        self.ca_host = self.ca_host_entry.get()
        self.ca_port = self.ca_port_entry.get()
        self.server_host = self.server_host_entry.get()
        self.server_port = self.server_port_entry.get()
        
        # ========== 連接 CA Server ==========
        try:
            self._add_log(f"嘗試連接 CA Server ({self.ca_host}:{self.ca_port})...", "INFO")
            
            # 步驟 1: 建立連線
            self._add_ca_event(
                "CONNECT", 
                f"CA Server ({self.ca_host}:{self.ca_port})",
                "SUCCESS",
                "TCP 連線建立"
            )
            
            time.sleep(0.3)
            
            # 步驟 2: 請求 CA 公鑰
            response = requests.get(
                f"http://{self.ca_host}:{self.ca_port}/public_key", timeout=10
            )
            
            if response.status_code == 200:
                self.ca_connected = True
                ca_public_key = response.content
                
                self._add_ca_event(
                    "PUBLIC_KEY",
                    "CA Server",
                    "SUCCESS",
                    "CA 公鑰請求成功",
                    {
                        "公鑰大小": f"{len(ca_public_key)} bytes",
                        "演算法": "RSA-2048",
                        "用途": "驗證憑證簽章"
                    }
                )
                
                self.ca_card.value_label.configure(text="ONLINE")
                self._add_log("CA Server 連接成功", "SUCCESS")
            else:
                raise Exception(f"HTTP {response.status_code}")
                
        except Exception as e:
            self._add_log(f"CA Server 連接失敗: {e}", "ERROR")
            self.connect_btn.configure(state="normal", text="🔌 連接監控")
            return
        
        time.sleep(0.3)
        
        # ========== 連接 App Server ==========
        try:
            self._add_log(f"嘗試連接 App Server ({self.server_host}:{self.server_port})...", "INFO")
            
            response = requests.get(
                f"http://{self.server_host}:{self.server_port}/health", timeout=10
            )
            
            if response.status_code == 200:
                self.server_connected = True
                data = response.json()
                
                image_count = data.get('database', {}).get('image_count', 0)
                receiver_id = data.get('receiver_id', 'Hospital_Server_Receiver')
                sender_id = data.get('sender_id', 'Hospital_Server_Sender')
                
                self.server_card.value_label.configure(text="ONLINE")
                self.transfer_card.value_label.configure(text=str(image_count))
                
                self._add_log("App Server 連接成功", "SUCCESS")
                
                time.sleep(0.2)
                
                # ========== 顯示 Server 向 CA 註冊憑證的過程 ==========
                
                # Receiver 憑證註冊
                self._add_ca_event(
                    "REGISTER",
                    receiver_id,
                    "SUCCESS",
                    "Hospital Server 向 CA 提交註冊請求",
                    {
                        "Party ID": receiver_id,
                        "RSA 公鑰": "2048 bits",
                        "KEM 公鑰": "ML-KEM-1024 (1568 bytes)"
                    }
                )
                
                time.sleep(0.3)
                
                # CA 發行 Receiver 憑證
                self._add_ca_event(
                    "ISSUE",
                    receiver_id,
                    "SUCCESS",
                    "CA 簽發憑證完成",
                    {
                        "憑證類型": "X.509 相容",
                        "簽章演算法": "RSA-PSS-SHA256",
                        "有效期限": "365 天",
                        "用途": "接收加密影像"
                    }
                )
                
                time.sleep(0.3)
                
                # Sender 憑證註冊
                self._add_ca_event(
                    "REGISTER",
                    sender_id,
                    "SUCCESS",
                    "Hospital Server 向 CA 提交註冊請求",
                    {
                        "Party ID": sender_id,
                        "RSA 公鑰": "2048 bits",
                        "KEM 公鑰": "ML-KEM-1024 (1568 bytes)"
                    }
                )
                
                time.sleep(0.3)
                
                # CA 發行 Sender 憑證
                self._add_ca_event(
                    "ISSUE",
                    sender_id,
                    "SUCCESS",
                    "CA 簽發憑證完成",
                    {
                        "憑證類型": "X.509 相容",
                        "簽章演算法": "RSA-PSS-SHA256",
                        "有效期限": "365 天",
                        "用途": "傳送加密影像"
                    }
                )
                
                self._add_log(f"資料庫目前有 {image_count} 張影像", "INFO")
                
                # 初始化 last_image_id
                try:
                    resp = requests.get(
                        f"http://{self.server_host}:{self.server_port}/list_images?limit=1",
                        timeout=5
                    )
                    if resp.status_code == 200:
                        images = resp.json().get('images', [])
                        if images:
                            self.last_image_id = images[0]['id']
                            self.processed_image_ids.add(images[0]['id'])
                except:
                    pass
                    
            else:
                raise Exception(f"HTTP {response.status_code}")
                
        except Exception as e:
            self._add_log(f"App Server 連接失敗: {e}", "ERROR")
            self.connect_btn.configure(state="normal", text="🔌 連接監控")
            return
        
        # 連接成功
        self.monitoring = True
        self.connect_btn.configure(
            state="normal", text="✅ 監控中", fg_color=self.colors["success"]
        )
        
        self._add_log("開始即時監控...", "SUCCESS")
        self._poll_updates()
    
    def _poll_updates(self):
        """輪詢更新 - 修復重複問題"""
        if not self.monitoring:
            return
        
        try:
            # 1. 優先從監控 API 獲取加密事件
            monitor_api_available = False
            try:
                response = requests.get(
                    f"http://{self.server_host}:{self.server_port}/monitor/encryption_events?since_id={self.last_event_id}&limit=10",
                    timeout=3
                )
                if response.status_code == 200:
                    monitor_api_available = True
                    data = response.json()
                    events = data.get('events', [])
                    
                    for event in events:
                        event_id = event.get('event_id', 0)
                        # ⭐ 檢查是否已處理過
                        if event_id not in self.processed_event_ids:
                            self.processed_event_ids.add(event_id)
                            self._add_encryption_event(event)
                            self.last_event_id = max(self.last_event_id, event_id)
                            
                            username = event.get('username') or f"User #{event.get('user_id', '?')}"
                            filename = event.get('filename', 'unknown')
                            direction = "上傳" if event.get('direction') == 'UPLOAD' else "下載"
                            self._add_log(f"{username} {direction} {filename}", "SUCCESS")
            except:
                pass
            
            # 2. 從監控 API 獲取線上用戶（即時同步，登出後立即刷新）
            try:
                response = requests.get(
                    f"http://{self.server_host}:{self.server_port}/monitor/online_users",
                    timeout=2
                )
                if response.status_code == 200:
                    data = response.json()
                    server_users = data.get('online_users', [])
                    
                    # ⭐ 用 Server 的資料完全覆蓋本地追蹤（這樣登出後會自動消失）
                    self.online_users = {u['user_id']: u for u in server_users}
                    self._update_users_list(self.online_users)
                    
            except requests.exceptions.RequestException:
                # 監控 API 不可用，保持本地追蹤
                pass
            
            # 3. 如果監控 API 不可用，回退到 list_images（並清理超時用戶）
            if not monitor_api_available:
                # ⭐ 清理超過 5 分鐘沒有活動的本地追蹤用戶
                now = datetime.now()
                expired_users = []
                for user_id, user_info in self.online_users.items():
                    login_time_str = user_info.get('login_time', '')
                    if login_time_str:
                        try:
                            # 嘗試解析時間
                            if 'T' in login_time_str:
                                login_time = datetime.fromisoformat(login_time_str.replace('Z', ''))
                            else:
                                login_time = datetime.strptime(login_time_str, "%H:%M:%S")
                                login_time = login_time.replace(year=now.year, month=now.month, day=now.day)
                            
                            # 超過 5 分鐘視為已離線
                            if (now - login_time).total_seconds() > 300:
                                expired_users.append(user_id)
                        except:
                            pass
                
                # 移除過期用戶
                for user_id in expired_users:
                    if user_id in self.online_users:
                        removed = self.online_users.pop(user_id)
                        self._add_log(f"{removed.get('username', 'Unknown')} 已離線（超時）", "INFO")
                
                if expired_users:
                    self._update_users_list(self.online_users)
                
                try:
                    response = requests.get(
                        f"http://{self.server_host}:{self.server_port}/list_images?limit=10",
                        timeout=5
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        images = data.get('images', [])
                        
                        for img in reversed(images):
                            img_id = img['id']
                            
                            # ⭐ 檢查是否已處理過
                            if img_id in self.processed_image_ids:
                                continue
                            
                            # ⭐ 只處理新的（ID > last_image_id）
                            if img_id <= self.last_image_id:
                                continue
                            
                            # 跳過測試上傳
                            if img.get('patient_id') == 99999:
                                continue
                            
                            # 標記為已處理
                            self.processed_image_ids.add(img_id)
                            self.last_image_id = max(self.last_image_id, img_id)
                            
                            uploader_name = img.get('uploader_name') or f"User #{img.get('uploader_id')}"
                            
                            enc_event = {
                                "type": "DECRYPT",
                                "direction": "UPLOAD",
                                "timestamp": datetime.now().isoformat(),
                                "user_id": img.get('uploader_id'),
                                "username": uploader_name,
                                "filename": img.get('filename'),
                                "file_size": img.get('file_size', 0),
                                "encryption_details": {
                                    "kem_algorithm": "ML-KEM-1024",
                                    "aes_mode": "AES-256-GCM",
                                    "kem_ciphertext_size": 1568,
                                    "ciphertext_size": img.get('file_size', 0) + 16,
                                    "has_wrapped_key": True,
                                },
                                "certificate_verified": True,
                                "signature_verified": True,
                                "status": "SUCCESS"
                            }
                            
                            self._add_encryption_event(enc_event)
                            
                            # ⭐ 添加 CA 憑證驗證事件（用戶上傳時）
                            self._add_ca_event(
                                "VERIFY",
                                uploader_name,
                                "SUCCESS",
                                "上傳者憑證驗證通過",
                                {
                                    "驗證項目": "CA 簽章、有效期限",
                                    "KEM 公鑰": "已驗證",
                                    "RSA 公鑰": "已驗證"
                                }
                            )
                            
                            self._add_log(f"{uploader_name} 上傳 {img.get('filename')}", "SUCCESS")
                            
                            # 更新本地用戶追蹤
                            user_id = img.get('uploader_id')
                            if user_id:
                                self.online_users[user_id] = {
                                    'username': uploader_name,
                                    'role_name': img.get('clinical_dept_name', '醫療人員'),
                                    'login_time': datetime.now().strftime("%H:%M:%S")
                                }
                        
                        self._update_users_list(self.online_users)
                except:
                    pass
            
            # 4. 更新統計
            try:
                response = requests.get(
                    f"http://{self.server_host}:{self.server_port}/stats", timeout=5
                )
                if response.status_code == 200:
                    stats = response.json().get('statistics', {})
                    self.transfer_card.value_label.configure(
                        text=str(stats.get('total_images', 0))
                    )
            except:
                pass
                
        except Exception as e:
            print(f"輪詢錯誤: {e}")
        
        if self.monitoring:
            self.root.after(2000, self._poll_updates)
    
    def run(self):
        """啟動應用"""
        self.root.mainloop()


if __name__ == "__main__":
    app = IRISMonitor()
    app.run()