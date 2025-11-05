# -*- coding: utf-8 -*-
"""
images_tab.py - 影像清單查看模組（完整版）
支援：
1. 影像和影片的縮圖顯示
2. 本地暫存和 Server 端資料
3. 影片播放器整合
4. 搜尋和篩選功能
"""

import os
import customtkinter as ctk
from tkinter import messagebox
from PIL import Image, ImageTk
from io import BytesIO
from .config import COLOR, FONT, Card, Subtle, OutlineBtn, PAD, GAP
from .api_client import get_api_client
from .thumbnail_utils import create_thumbnail, is_video_file, is_image_file


class ImagesTab:
    """影像清單標籤頁（完整版 - 支援影片）"""
    
    def __init__(self, root, user, parent_root, local_manager=None):
        self.root = root
        self.user = user
        self.parent_root = parent_root
        self.local_manager = local_manager
        self.api_client = get_api_client()
        self.kw = None
        self.imageslistframe = None
        self.auto_refresh_id = None
        self.thumbnail_cache = {}  # 縮圖快取
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
            status_text = f"✅ 已連接到 Hospital Server | 資料庫: {health.get('database', {}).get('image_count', 0)} 張影像"
            status_color = COLOR["success"]
        else:
            status_text = "❌ 無法連接到 Hospital Server"
            status_color = COLOR["danger"]
        
        # 顯示本地暫存統計
        if self.local_manager:
            stats = self.local_manager.get_stats()
            status_text += f" | 💾 本地暫存: {stats['total_images']} 張 ({stats['total_size_mb']} MB)"
        
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
        """重新載入影像列表（支援本地和 Server）"""
        # 清空舊內容
        for widget in self.imageslistframe.winfo_children():
            widget.destroy()
        
        # 解析搜尋條件
        keyword = self.kw.get().strip() if self.kw else ""
        patient_id = None
        
        if keyword.isdigit():
            patient_id = int(keyword)
        
        all_images = []
        
        # 從本地載入影像
        if self.local_manager:
            try:
                if keyword:
                    local_images = self.local_manager.search_images(keyword)
                else:
                    local_images = self.local_manager.get_all_images()
                
                # 標記為本地來源
                for img in local_images:
                    img['source'] = 'local'
                
                all_images.extend(local_images)
             #   print(f"💾 載入本地影像: {len(local_images)} 張")
                
            except Exception as e:
                print(f"⚠️ 載入本地影像失敗: {e}")
        
        # 從後端獲取影像列表
        try:
            result = self.api_client.list_images(patient_id=patient_id)
            
            if result and result.get('images'):
                server_images = result['images']
                
                # 標記為 Server 來源
                for img in server_images:
                    img['source'] = 'server'
                
                all_images.extend(server_images)
                print(f"🌐 載入 Server 影像: {len(server_images)} 張")
                
        except Exception as e:
            print(f"⚠️ 無法從 Server 獲取影像列表: {e}")
        
        if not all_images:
            self.show_empty("目前沒有影像")
            return
        
        # 顯示統計
        local_count = sum(1 for img in all_images if img.get('source') == 'local')
        server_count = sum(1 for img in all_images if img.get('source') == 'server')
        
        stats_frame = ctk.CTkFrame(
            self.imageslistframe,
            fg_color=COLOR["chip"],
            corner_radius=12
        )
        stats_frame.pack(fill="x", pady=(0, GAP))
        
        ctk.CTkLabel(
            stats_frame,
            text=f"📊 共找到 {len(all_images)} 張影像（💾 本地: {local_count} 張 | 🌐 Server: {server_count} 張）",
            font=FONT["h3"],
            text_color=COLOR["primary"]
        ).pack(padx=PAD, pady=PAD)
        
        # 顯示影像卡片（按時間排序，最新的在前）
        sorted_images = sorted(all_images, key=lambda x: x.get('uploaded_at', x.get('upload_time', '')), reverse=True)
        for img in sorted_images:
            self.create_image_card(img)
    
    def create_image_card(self, img_data):
        """創建影像卡片（支援影像和影片）"""
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
            thumbnail_label.image = thumbnail  # 保持引用
            thumbnail_label.pack()
        else:
            # 沒有縮圖時顯示預設圖示
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
        
        # 中間：影像資訊
        middle = ctk.CTkFrame(inner, fg_color="transparent")
        middle.pack(side="left", fill="both", expand=True)
        
        # 檔名 + 類型標籤
        name_frame = ctk.CTkFrame(middle, fg_color="transparent")
        name_frame.pack(anchor="w", fill="x")
        
        ctk.CTkLabel(
            name_frame,
            text=f"📁 {filename}",
            font=FONT["h3"],
            text_color=COLOR["ink"],
            anchor="w"
        ).pack(side="left")
        
        # 類型標籤
        if is_video_file(filename):
            type_label = ctk.CTkLabel(
                name_frame,
                text="🎬 影片",
                font=FONT["meta"],
                text_color="white",
                fg_color=COLOR["primary"],
                corner_radius=4
            )
            type_label.pack(side="left", padx=(8, 0), pady=2)
        elif is_image_file(filename):
            type_label = ctk.CTkLabel(
                name_frame,
                text="🖼️ 影像",
                font=FONT["meta"],
                text_color="white",
                fg_color=COLOR["success"],
                corner_radius=4
            )
            type_label.pack(side="left", padx=(8, 0), pady=2)
        
        # 根據來源顯示不同資訊
        if source == 'local':
            # 本地影像資訊
            info_items = []
            
            if 'patient_name' in img_data and img_data['patient_name']:
                info_items.append(f"👤 病患: {img_data['patient_name']}")
            
            if 'mrn' in img_data and img_data['mrn']:
                info_items.append(f"🏥 MRN: {img_data['mrn']}")
            
            if 'upload_time' in img_data and img_data['upload_time']:
                info_items.append(f"📅 {img_data['upload_time']}")
            
            if 'file_size' in img_data:
                size_mb = round(img_data['file_size'] / (1024 * 1024), 2)
                info_items.append(f"💾 {size_mb} MB")
            
            for item in info_items:
                ctk.CTkLabel(
                    middle,
                    text=item,
                    font=FONT["body"],
                    text_color=COLOR["ink"],
                    anchor="w"
                ).pack(anchor="w", pady=(4, 0))
        else:
            # Server 影像資訊
            info_text = (
                f"ID: {img_data.get('id', '?')} | "
                f"病患ID: {img_data.get('patient_id', '?')} | "
                f"上傳時間: {img_data.get('uploaded_at', '未知')}"
            )
            
            ctk.CTkLabel(
                middle,
                text=info_text,
                font=FONT["meta"],
                text_color=COLOR["inksubtle"],
                anchor="w"
            ).pack(anchor="w", pady=(4, 0))
        
        # 狀態標籤
        status = img_data.get('status', 'unknown')
        if source == 'local':
            status_map = {
                'local': ('📥 本地暫存', COLOR["primary"]),
                'uploaded': ('✅ 已上傳', COLOR["success"]),
                'error': ('❌ 上傳失敗', COLOR["danger"])
            }
            status_text, status_color = status_map.get(status, ('❓ 未知', COLOR["muted"]))
        else:
            status_text = f"📌 狀態: {status}"
            status_color = COLOR["success"] if status == 'completed' else COLOR["muted"]
        
        status_label = ctk.CTkLabel(
            middle,
            text=status_text,
            font=FONT["meta"],
            text_color=status_color
        )
        status_label.pack(anchor="w", pady=(4, 0))
        
        # 右側：操作按鈕
        right = ctk.CTkFrame(inner, fg_color="transparent")
        right.pack(side="right")
        
        # 根據檔案類型顯示不同按鈕
        if is_video_file(filename):
            button_text = "▶️ 播放"
        else:
            button_text = "👁️ 查看"
        
        OutlineBtn(
            right,
            button_text,
            lambda: self.view_media(img_data),
            w=100,
            h=36
        ).pack(side="right", padx=(8, 0))
    
    def load_thumbnail(self, img_data):
        """載入縮圖（支援影像和影片）"""
        try:
            source = img_data.get('source', 'unknown')
            filename = img_data.get('filename', 'unknown')
            img_id = img_data.get('id', 0)
            
            # 檢查快取
            cache_key = f"{source}_{img_id}"
            if cache_key in self.thumbnail_cache:
                return self.thumbnail_cache[cache_key]
            
            # 獲取資料
            if source == 'local':
                # 從本地檔案載入
                image_path = img_data.get('local_path')
                if not image_path or not os.path.exists(image_path):
                    return None
                
                with open(image_path, 'rb') as f:
                    image_data = f.read()
            else:
                # 從 Server 獲取（可選實作）
                return None
            
            # 生成縮圖
            thumbnail = create_thumbnail(image_data, filename, width=200, height=150)
            photo = ImageTk.PhotoImage(thumbnail)
            
            # 快取
            self.thumbnail_cache[cache_key] = photo
            
            return photo
            
        except Exception as e:
            print(f"⚠️ 載入縮圖失敗 ({img_data.get('filename', 'unknown')}): {e}")
            return None
    
    def view_media(self, img_data):
        """查看媒體（影像或影片）"""
        filename = img_data.get('filename', 'unknown')
        source = img_data.get('source', 'unknown')
        
        if is_video_file(filename):
            # 播放影片
            self.play_video(img_data)
        else:
            # 查看影像
            if source == 'local':
                self.view_local_image(img_data)
            else:
                self.view_server_image(img_data)
    
    def play_video(self, img_data):
        """播放影片"""
        try:
            source = img_data.get('source', 'unknown')
            filename = img_data.get('filename', 'unknown')
            
            # 獲取影片資料
            if source == 'local':
                video_path = img_data.get('local_path')
                if not video_path or not os.path.exists(video_path):
                    messagebox.showerror("錯誤", "影片檔案不存在")
                    return
                
                with open(video_path, 'rb') as f:
                    video_data = f.read()
            else:
                messagebox.showinfo("提示", "Server 端影片下載功能開發中")
                return
            
            # 創建播放器視窗
            player_window = ctk.CTkToplevel(self.parent_root)
            player_window.title(f"影片播放 - {filename}")
            player_window.geometry("1000x700")
            
            # 匯入並創建播放器
            from .video_player import VideoPlayer
            player = VideoPlayer(player_window, video_data, filename)
            
            # 視窗關閉時清理資源
            def on_close():
                player.cleanup()
                player_window.destroy()
            
            player_window.protocol("WM_DELETE_WINDOW", on_close)
            
        except Exception as e:
            messagebox.showerror("錯誤", f"無法播放影片: {e}")
            import traceback
            traceback.print_exc()
    
    def view_local_image(self, img_data):
        """查看本地影像"""
        try:
            # 創建新視窗
            view_window = ctk.CTkToplevel(self.parent_root)
            view_window.title(f"影像檢視 - {img_data.get('filename', '未知')}")
            view_window.geometry("800x900")
            
            # 頂部資訊
            info_frame = ctk.CTkFrame(view_window, fg_color=COLOR["surface"])
            info_frame.pack(fill="x", padx=20, pady=20)
            
            info_lines = [
                f"📁 檔名: {img_data.get('filename', '未知')}",
                f"👤 病患姓名: {img_data.get('patient_name', '未知')}",
                f"🏥 MRN: {img_data.get('mrn', '-')}",
                f"📅 上傳時間: {img_data.get('upload_time', '未知')}",
            ]
            
            if 'file_size' in img_data:
                size_mb = round(img_data['file_size'] / (1024 * 1024), 2)
                info_lines.append(f"💾 檔案大小: {size_mb} MB")
            
            info_text = "\n".join(info_lines)
            
            ctk.CTkLabel(
                info_frame,
                text=info_text,
                font=FONT["body"],
                justify="left"
            ).pack(padx=20, pady=20)
            
            # 影像顯示區域
            image_frame = ctk.CTkScrollableFrame(view_window, fg_color=COLOR["bg"])
            image_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
            
            # 載入並顯示完整影像
            image_path = img_data.get('local_path')
            if image_path and os.path.exists(image_path):
                img = Image.open(image_path)
                
                # 調整大小以適應視窗（最大 750x750）
                img.thumbnail((750, 750), Image.Resampling.LANCZOS)
                
                photo = ImageTk.PhotoImage(img)
                
                image_label = ctk.CTkLabel(image_frame, image=photo, text="")
                image_label.image = photo  # 保持引用
                image_label.pack(pady=20)
            else:
                ctk.CTkLabel(
                    image_frame,
                    text="⚠️ 影像檔案不存在",
                    font=FONT["h2"],
                    text_color=COLOR["danger"]
                ).pack(pady=50)
            
        except Exception as e:
            messagebox.showerror("錯誤", f"無法開啟影像: {e}")
    
    def view_server_image(self, img_data):
        """查看 Server 影像資訊"""
        messagebox.showinfo(
            "影像資訊",
            f"檔名: {img_data.get('filename', '未知')}\n"
            f"ID: {img_data.get('id', '?')}\n"
            f"病患ID: {img_data.get('patient_id', '?')}\n"
            f"MIME: {img_data.get('mime', '未知')}\n"
            f"上傳時間: {img_data.get('uploaded_at', '未知')}\n"
            f"狀態: {img_data.get('status', '未知')}"
        )
    
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