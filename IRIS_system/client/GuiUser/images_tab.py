# -*- coding: utf-8 -*-
"""
images_tab.py - 影像清單查看模組（精簡修正版）

修正內容：
1. 只顯示當前登入後的上傳記錄（使用 session 開始時間過濾）
2. 檢視按鈕直接開啟系統媒體播放器，不再彈出額外視窗
3. 移除對 video_player.py 的依賴
"""

import os
import tempfile
import platform
import subprocess
import customtkinter as ctk
from datetime import datetime
from tkinter import messagebox
from PIL import Image, ImageTk
from io import BytesIO
from .config import COLOR, FONT, Card, Subtle, OutlineBtn, PAD, GAP
from .api_client import get_api_client
from .thumbnail_utils import create_thumbnail, is_video_file, is_image_file


class ImagesTab:
    """影像清單標籤頁（精簡修正版 - 只顯示當前 Session 的上傳）"""
    
    def __init__(self, root, user, parent_root, local_manager=None):
        self.root = root
        self.user = user
        self.parent_root = parent_root
        self.local_manager = local_manager
        self.api_client = get_api_client()
        self.kw = None
        self.imageslistframe = None
        self.auto_refresh_id = None
        self.thumbnail_cache = {}
        
        # ⭐ 記錄 Session 開始時間（用於過濾舊資料）
        self.session_start_time = datetime.now()
        print(f"📅 Session 開始時間: {self.session_start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        self.setup_ui()
    
    def setup_ui(self):
        """設置使用者介面"""
        # 頂部搜尋欄
        bar = Subtle(self.root)
        bar.pack(fill="x", pady=(0, GAP))
        
        row = ctk.CTkFrame(bar, fg_color=COLOR["surfacealt"])
        row.pack(fill="x", padx=PAD, pady=PAD)
        
        ctk.CTkLabel(
            row, 
            text="🔍 搜尋病人:", 
            font=FONT.get("body"),
            text_color=COLOR["inksubtle"]
        ).pack(side="left")
        
        self.kw = ctk.StringVar()
        ctk.CTkEntry(
            row, 
            textvariable=self.kw, 
            placeholder_text="輸入病人ID或姓名",
            height=44, 
            corner_radius=12, 
            font=FONT.get("body")
        ).pack(side="left", fill="x", expand=True, padx=(12, 0))
        
        OutlineBtn(row, "🔍 搜尋", self.reload_images, w=88).pack(side="left", padx=8)
        OutlineBtn(row, "🔄 刷新", self.reload_images, w=88).pack(side="left")
        
        # 連接狀態
        desc = ctk.CTkFrame(bar, fg_color=COLOR["surfacealt"])
        desc.pack(fill="x", padx=PAD, pady=(0, PAD))
        
        # 檢查 Server 連接
        health = self.api_client.health_check()
        if health:
            status_text = f"✅ 已連接到 Hospital Server"
            status_color = COLOR["success"]
        else:
            status_text = "❌ 無法連接到 Hospital Server"
            status_color = COLOR["danger"]
        
        # 顯示本地暫存統計
        if self.local_manager:
            stats = self.local_manager.get_stats()
            status_text += f" | 💾 本地暫存: {stats['total_images']} 張"
        
        # 顯示 Session 資訊
        status_text += f" | 📅 顯示 {self.session_start_time.strftime('%H:%M')} 後的上傳"
        
        ctk.CTkLabel(
            desc, 
            text=status_text,
            font=FONT.get("meta"), 
            text_color=status_color
        ).pack(anchor="w")
        
        # 影像列表區域
        lstcard = Card(self.root)
        lstcard.pack(fill="both", expand=True, pady=(0, 0))
        
        self.imageslistframe = ctk.CTkScrollableFrame(
            lstcard, 
            fg_color=COLOR["surface"]
        )
        self.imageslistframe.pack(fill="both", expand=True, padx=PAD, pady=PAD)
        
        # 首次載入
        self.reload_images()
        
        # 啟動自動刷新
        self.start_auto_refresh()
    
    def start_auto_refresh(self):
        """啟動自動刷新（每5秒）"""
        self.auto_refresh_id = self.root.after(5000, self.auto_refresh_loop)
    
    def auto_refresh_loop(self):
        """自動刷新循環"""
        try:
            self.reload_images()
        except Exception as e:
            print(f"自動刷新錯誤: {e}")
        finally:
            self.auto_refresh_id = self.root.after(5000, self.auto_refresh_loop)
    
    def stop_auto_refresh(self):
        """停止自動刷新"""
        if self.auto_refresh_id:
            self.root.after_cancel(self.auto_refresh_id)
            self.auto_refresh_id = None
    
    def reload_images(self):
        """重新載入影像列表（只顯示當前 Session 的上傳）"""
        # 清空舊內容
        for widget in self.imageslistframe.winfo_children():
            widget.destroy()
        
        # 解析搜尋條件
        keyword = self.kw.get().strip() if self.kw else ""
        patient_id = None
        
        if keyword.isdigit():
            patient_id = int(keyword)
        
        all_images = []
        
        # ⭐ 只從本地載入當前 Session 的影像
        if self.local_manager:
            try:
                if keyword:
                    local_images = self.local_manager.search_images(keyword)
                else:
                    local_images = self.local_manager.get_all_images()
                
                # ⭐ 過濾：只保留當前 Session 開始後的影像
                filtered_local = []
                for img in local_images:
                    upload_time_str = img.get('upload_time', '')
                    if upload_time_str:
                        try:
                            # 嘗試解析時間
                            upload_time = datetime.strptime(upload_time_str, '%Y-%m-%d %H:%M:%S')
                            if upload_time >= self.session_start_time:
                                img['source'] = 'local'
                                filtered_local.append(img)
                        except ValueError:
                            # 如果無法解析時間，仍然顯示（保險起見）
                            img['source'] = 'local'
                            filtered_local.append(img)
                    else:
                        # 沒有時間戳記的一律顯示
                        img['source'] = 'local'
                        filtered_local.append(img)
                
                all_images.extend(filtered_local)
                
            except Exception as e:
                print(f"⚠️ 載入本地影像失敗: {e}")
        
        # ⭐ 不再從 Server 載入舊資料，只顯示本地暫存
        # 如果你仍然需要顯示 Server 資料，可以取消下面的註解
        # 但會顯示所有歷史資料
        
        # try:
        #     result = self.api_client.list_images(patient_id=patient_id)
        #     if result and result.get('images'):
        #         for img in result['images']:
        #             img['source'] = 'server'
        #         all_images.extend(result['images'])
        # except Exception as e:
        #     print(f"⚠️ 無法從 Server 獲取影像列表: {e}")
        
        if not all_images:
            self.show_empty("本次登入尚無上傳影像")
            return
        
        # 顯示統計
        stats_frame = ctk.CTkFrame(
            self.imageslistframe,
            fg_color=COLOR["chip"],
            corner_radius=12
        )
        stats_frame.pack(fill="x", pady=(0, GAP))
        
        ctk.CTkLabel(
            stats_frame,
            text=f"📊 本次登入已上傳 {len(all_images)} 張影像",
            font=FONT["h3"],
            text_color=COLOR["primary"]
        ).pack(padx=PAD, pady=PAD)
        
        # 顯示影像卡片（按時間排序，最新的在前）
        sorted_images = sorted(
            all_images, 
            key=lambda x: x.get('uploaded_at', x.get('upload_time', '')), 
            reverse=True
        )
        for img in sorted_images:
            self.create_image_card(img)
    
    def create_image_card(self, img_data):
        """創建影像卡片"""
        source = img_data.get('source', 'unknown')
        filename = img_data.get('filename', 'unknown')
        
        card = ctk.CTkFrame(
            self.imageslistframe,
            fg_color=COLOR["surfacealt"],
            corner_radius=12
        )
        card.pack(fill="x", pady=(0, GAP))
        
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=PAD, pady=PAD)
        
        # 左側：縮圖
        left = ctk.CTkFrame(inner, fg_color="transparent")
        left.pack(side="left", padx=(0, PAD))
        
        # 載入縮圖
        thumbnail = self.load_thumbnail(img_data)
        if thumbnail:
            thumbnail_label = ctk.CTkLabel(left, image=thumbnail, text="")
            thumbnail_label.image = thumbnail
            thumbnail_label.pack()
        else:
            icon = "🎬" if is_video_file(filename) else "🖼️"
            ctk.CTkLabel(
                left,
                text=icon,
                font=("Arial", 48),
                width=200,
                height=150,
                fg_color=COLOR["surface"],
                corner_radius=8
            ).pack()
        
        # 中間：檔案資訊
        middle = ctk.CTkFrame(inner, fg_color="transparent")
        middle.pack(side="left", fill="x", expand=True)
        
        # 檔名
        ctk.CTkLabel(
            middle,
            text=filename,
            font=FONT["h3"],
            text_color=COLOR["ink"]
        ).pack(anchor="w")
        
        # 病人資訊
        patient_name = img_data.get('patient_name', '未知')
        mrn = img_data.get('mrn', '-')
        ctk.CTkLabel(
            middle,
            text=f"👤 {patient_name} | 🏥 MRN: {mrn}",
            font=FONT["body"],
            text_color=COLOR["inksubtle"]
        ).pack(anchor="w", pady=(4, 0))
        
        # 上傳時間
        upload_time = img_data.get('upload_time', img_data.get('uploaded_at', '未知'))
        ctk.CTkLabel(
            middle,
            text=f"📅 {upload_time}",
            font=FONT["meta"],
            text_color=COLOR["muted"]
        ).pack(anchor="w", pady=(4, 0))
        
        # 檔案類型標籤
        if is_video_file(filename):
            type_text = "🎬 影片"
            type_color = COLOR["warning"]
        else:
            type_text = "🖼️ 影像"
            type_color = COLOR["primary"]
        
        ctk.CTkLabel(
            middle,
            text=type_text,
            font=FONT["meta"],
            text_color=type_color
        ).pack(anchor="w", pady=(4, 0))
        
        # 右側：操作按鈕
        right = ctk.CTkFrame(inner, fg_color="transparent")
        right.pack(side="right")
        
        # 根據檔案類型顯示不同按鈕
        if is_video_file(filename):
            button_text = "▶️ 播放"
        else:
            button_text = "👁️ 檢視"
        
        OutlineBtn(
            right,
            button_text,
            lambda d=img_data: self.view_media(d),
            w=100,
            h=36
        ).pack(side="right", padx=(8, 0))
    
    def load_thumbnail(self, img_data):
        """載入縮圖"""
        try:
            source = img_data.get('source', 'unknown')
            filename = img_data.get('filename', 'unknown')
            img_id = img_data.get('id', 0)
            
            cache_key = f"{source}_{img_id}"
            if cache_key in self.thumbnail_cache:
                return self.thumbnail_cache[cache_key]
            
            if source == 'local':
                image_path = img_data.get('local_path')
                if not image_path or not os.path.exists(image_path):
                    return None
                
                with open(image_path, 'rb') as f:
                    image_data = f.read()
            else:
                return None
            
            thumbnail = create_thumbnail(image_data, filename, width=200, height=150)
            photo = ImageTk.PhotoImage(thumbnail)
            
            self.thumbnail_cache[cache_key] = photo
            return photo
            
        except Exception as e:
            print(f"⚠️ 載入縮圖失敗 ({img_data.get('filename', 'unknown')}): {e}")
            return None
    
    def view_media(self, img_data):
        """查看媒體 - 直接使用系統播放器開啟"""
        filename = img_data.get('filename', 'unknown')
        source = img_data.get('source', 'unknown')
        
        if source == 'local':
            # 本地檔案：直接開啟
            file_path = img_data.get('local_path')
            if file_path and os.path.exists(file_path):
                self._open_with_system(file_path, filename)
            else:
                messagebox.showerror("錯誤", "檔案不存在")
        else:
            # Server 檔案：需要先下載
            self._download_and_open(img_data)
    
    def _open_with_system(self, file_path, filename):
        """使用系統預設程式開啟檔案"""
        try:
            system = platform.system()
            
            if system == "Windows":
                os.startfile(file_path)
                print(f"✅ 已使用 Windows 預設程式開啟: {filename}")
                
            elif system == "Darwin":  # macOS
                subprocess.Popen(['open', file_path])
                print(f"✅ 已使用 macOS 預設程式開啟: {filename}")
                
            else:  # Linux
                subprocess.Popen(['xdg-open', file_path])
                print(f"✅ 已使用 Linux 預設程式開啟: {filename}")
                
        except Exception as e:
            messagebox.showerror("錯誤", f"無法開啟檔案: {e}")
            import traceback
            traceback.print_exc()
    
    def _download_and_open(self, img_data):
        """下載 Server 檔案並開啟"""
        try:
            image_id = img_data.get('id')
            filename = img_data.get('filename', 'unknown')
            
            print(f"📥 正在下載: {filename} (ID: {image_id})")
            
            # 從 Server 下載
            image_data = self.api_client.get_image_full(image_id)
            
            if not image_data:
                messagebox.showerror("錯誤", "無法下載檔案")
                return
            
            # 取得副檔名
            _, ext = os.path.splitext(filename)
            if not ext:
                ext = '.dat'
            
            # 建立臨時檔案
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext, prefix='iris_') as tmp:
                tmp.write(image_data)
                tmp_path = tmp.name
            
            print(f"💾 臨時檔案: {tmp_path}")
            
            # 用系統預設程式開啟
            self._open_with_system(tmp_path, filename)
            
        except Exception as e:
            messagebox.showerror("錯誤", f"下載失敗: {e}")
            import traceback
            traceback.print_exc()
    
    def show_error(self, message):
        """顯示錯誤訊息"""
        error_frame = ctk.CTkFrame(
            self.imageslistframe,
            fg_color=COLOR["danger"],
            corner_radius=12
        )
        error_frame.pack(fill="x", pady=GAP)
        
        ctk.CTkLabel(
            error_frame,
            text=f"❌ {message}",
            font=FONT["body"],
            text_color="white"
        ).pack(padx=PAD, pady=PAD)
    
    def show_empty(self, message):
        """顯示空狀態"""
        empty_frame = ctk.CTkFrame(
            self.imageslistframe,
            fg_color=COLOR["surfacealt"],
            corner_radius=12
        )
        empty_frame.pack(fill="both", expand=True, pady=GAP)
        
        ctk.CTkLabel(
            empty_frame,
            text=f"📭 {message}",
            font=FONT["h2"],
            text_color=COLOR["muted"]
        ).pack(expand=True, padx=PAD, pady=PAD*3)
        
        # 提示訊息
        ctk.CTkLabel(
            empty_frame,
            text="請到「上傳影像」頁面上傳新的醫療影像",
            font=FONT["body"],
            text_color=COLOR["inksubtle"]
        ).pack(pady=(0, PAD*2))