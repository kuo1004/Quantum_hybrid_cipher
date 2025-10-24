# -*- coding: utf-8 -*-
"""
transmission_status_tab.py - 加密傳輸狀態監控
即時顯示檔案透過安全通道的傳輸進度
"""

import os
import json
import customtkinter as ctk
from datetime import datetime
from .config import COLOR, FONT, Card, PAD, GAP

class TransmissionStatusTab:
    """監控加密傳輸狀態的頁籤"""
    
    def __init__(self, root, user):
        self.root = root
        self.user = user
        self.status_frame = None
        self.auto_refresh_id = None
        self.setup_ui()
        self.start_auto_refresh()
    
    def setup_ui(self):
        """設置 UI"""
        # 標題卡片
        title_card = Card(self.root)
        title_card.pack(fill="x", pady=(0, GAP))
        
        title_inner = ctk.CTkFrame(title_card, fg_color=COLOR["surface"])
        title_inner.pack(fill="x", padx=PAD, pady=PAD)
        
        ctk.CTkLabel(
            title_inner,
            text="📡 加密傳輸狀態監控",
            font=FONT["h1"],
            text_color=COLOR["ink"]
        ).pack(anchor="w")
        
        ctk.CTkLabel(
            title_inner,
            text="即時監控透過 ML-KEM + AES-GCM + RSA-PSS 安全通道傳輸的檔案狀態",
            font=FONT["meta"],
            text_color=COLOR["inksubtle"]
        ).pack(anchor="w", pady=(4, 0))
        
        # 狀態顯示區域
        status_card = Card(self.root)
        status_card.pack(fill="both", expand=True)
        
        self.status_frame = ctk.CTkScrollableFrame(
            status_card,
            fg_color=COLOR["surface"]
        )
        self.status_frame.pack(fill="both", expand=True, padx=PAD, pady=PAD)
    
    def start_auto_refresh(self):
        """啟動自動刷新（每3秒）"""
        self.check_queue_status()
        self.auto_refresh_id = self.root.after(3000, self.start_auto_refresh)
    
    def stop_auto_refresh(self):
        """停止自動刷新"""
        if self.auto_refresh_id:
            self.root.after_cancel(self.auto_refresh_id)
            self.auto_refresh_id = None
    
    def check_queue_status(self):
        """檢查傳輸佇列狀態"""
        # 清空舊內容
        for widget in self.status_frame.winfo_children():
            widget.destroy()
        
        input_dir = ".medicalimages/input"
        output_dir = ".medicalimages/output"
        
        # 統計資訊
        pending_count = 0
        encrypted_count = 0
        pending_files = []
        encrypted_files = []
        
        # 檢查待加密檔案
        if os.path.exists(input_dir):
            for f in os.listdir(input_dir):
                if not f.endswith('.meta.json'):
                    pending_count += 1
                    pending_files.append(f)
        
        # 檢查已加密檔案
        if os.path.exists(output_dir):
            for f in os.listdir(output_dir):
                if f.startswith('stego_'):
                    encrypted_count += 1
                    encrypted_files.append(f)
        
        # 顯示整體狀態
        overall_frame = ctk.CTkFrame(
            self.status_frame,
            fg_color=COLOR["chip"],
            corner_radius=12
        )
        overall_frame.pack(fill="x", padx=0, pady=(0, GAP))
        
        if pending_count == 0 and encrypted_count == 0:
            status_text = "✅ 所有檔案處理完成"
            status_color = COLOR["success"]
        elif pending_count > 0:
            status_text = f"⏳ 正在處理 {pending_count} 個檔案"
            status_color = COLOR["warning"]
        else:
            status_text = f"🔒 {encrypted_count} 個檔案等待傳輸"
            status_color = COLOR["primary"]
        
        ctk.CTkLabel(
            overall_frame,
            text=status_text,
            font=FONT["h2"],
            text_color=status_color
        ).pack(padx=PAD, pady=PAD)
        
        # 待加密檔案列表
        if pending_files:
            pending_card = ctk.CTkFrame(
                self.status_frame,
                fg_color=COLOR["surfacealt"],
                corner_radius=12
            )
            pending_card.pack(fill="x", pady=(0, GAP))
            
            ctk.CTkLabel(
                pending_card,
                text=f"⏳ 待加密檔案 ({pending_count} 個)",
                font=FONT["h3"],
                text_color=COLOR["warning"]
            ).pack(anchor="w", padx=PAD, pady=(PAD, 8))
            
            for f in pending_files[:10]:  # 只顯示前10個
                file_frame = ctk.CTkFrame(pending_card, fg_color="transparent")
                file_frame.pack(fill="x", padx=PAD*2, pady=2)
                
                # 檢查是否有 meta 檔案
                meta_path = os.path.join(input_dir, f + ".meta.json")
                meta_info = ""
                if os.path.exists(meta_path):
                    try:
                        with open(meta_path, 'r', encoding='utf-8') as mf:
                            meta = json.load(mf)
                            meta_info = f" | 🏥 病人ID: {meta.get('patient_id', '?')}"
                    except:
                        pass
                
                ctk.CTkLabel(
                    file_frame,
                    text=f"  • {f}{meta_info}",
                    font=FONT["meta"],
                    text_color=COLOR["inksubtle"]
                ).pack(anchor="w")
            
            if pending_count > 10:
                ctk.CTkLabel(
                    pending_card,
                    text=f"... 還有 {pending_count - 10} 個檔案",
                    font=FONT["meta"],
                    text_color=COLOR["muted"]
                ).pack(anchor="w", padx=PAD*2, pady=(0, PAD))
        
        # 已加密檔案列表
        if encrypted_files:
            encrypted_card = ctk.CTkFrame(
                self.status_frame,
                fg_color=COLOR["surfacealt"],
                corner_radius=12
            )
            encrypted_card.pack(fill="x", pady=(0, GAP))
            
            ctk.CTkLabel(
                encrypted_card,
                text=f"🔒 已加密待傳輸 ({encrypted_count} 個)",
                font=FONT["h3"],
                text_color=COLOR["success"]
            ).pack(anchor="w", padx=PAD, pady=(PAD, 8))
            
            for f in encrypted_files[:5]:  # 只顯示前5個
                ctk.CTkLabel(
                    encrypted_card,
                    text=f"  • {f}",
                    font=FONT["meta"],
                    text_color=COLOR["inksubtle"]
                ).pack(anchor="w", padx=PAD*2, pady=2)
        
        # 安全特性說明
        security_card = ctk.CTkFrame(
            self.status_frame,
            fg_color=COLOR["surfacealt"],
            corner_radius=12
        )
        security_card.pack(fill="x", pady=(GAP, 0))
        
        ctk.CTkLabel(
            security_card,
            text="🔐 安全保障",
            font=FONT["h3"],
            text_color=COLOR["primary"]
        ).pack(anchor="w", padx=PAD, pady=(PAD, 8))
        
        security_features = [
            "✅ ML-KEM (後量子密鑰封裝機制) - 對抗量子電腦攻擊",
            "✅ AES-256-GCM 加密 - 軍事級資料加密",
            "✅ RSA-PSS 數位簽章 - 確保資料完整性與不可否認性",
            "✅ LSB 隱寫術 - 隱藏傳輸內容",
            "✅ CA 憑證驗證 - 防止中間人攻擊"
        ]
        
        for feature in security_features:
            ctk.CTkLabel(
                security_card,
                text=feature,
                font=FONT["meta"],
                text_color=COLOR["inksubtle"]
            ).pack(anchor="w", padx=PAD*2, pady=2)
        
        ctk.CTkLabel(
            security_card,
            text="",
            font=FONT["meta"]
        ).pack(pady=(0, PAD))
