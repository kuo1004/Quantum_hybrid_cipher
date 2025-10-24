# -*- coding: utf-8 -*-
"""
images_tab.py - 影像清單查看模組（安全通道整合版）
支援顯示透過加密通道傳輸的影像
"""

import io
from logging import info
import os
import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox, filedialog
from PIL import Image, ImageTk
from .database import connect_db
from .config import COLOR, FONT, Card, Subtle, SolidBtn, OutlineBtn, PAD, GAP
from .video_player import VideoPlayer

class ImagesTab:
    """影像清單標籤頁 - 整合安全通道"""
    
    def __init__(self, root, user, parent_root):
        self.root = root
        self.user = user
        self.parent_root = parent_root
        self.kw = None
        self.imageslistframe = None
        self.auto_refresh_id = None  # 用於自動刷新
        self.setup_ui()
    
    def setup_ui(self):
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
            placeholder_text="輸入病人姓名",
            height=44, 
            corner_radius=12, 
            font=FONT.get("body")
        ).pack(side="left", fill="x", expand=True, padx=(12, 0))
        
        OutlineBtn(row, "🔍 搜尋", self.reload_images, w=88).pack(side="left", padx=8)
        OutlineBtn(row, "🔄 刷新", self.reload_images, w=88).pack(side="left")
        
        # 功能說明
        desc = ctk.CTkFrame(bar, fg_color=COLOR["surfacealt"])
        desc.pack(fill="x", padx=PAD, pady=(0, PAD))
        
        ctk.CTkLabel(
            desc, 
            text="📌 功能說明: 顯示所有影像，包括透過「🔐 加密通道」安全傳輸的檔案 | 自動每5秒刷新",
            font=FONT.get("meta"), 
            text_color=COLOR["inksubtle"]
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
            # 繼續下一次刷新
            self.auto_refresh_id = self.root.after(5000, self.auto_refresh_loop)
    
    def stop_auto_refresh(self):
        """停止自動刷新（在視窗關閉時呼叫）"""
        if self.auto_refresh_id:
            self.root.after_cancel(self.auto_refresh_id)
            self.auto_refresh_id = None
    
    def reload_images(self):
        """重新載入影像清單"""
        # 清空現有影像
        for widget in self.imageslistframe.winfo_children():
            widget.destroy()

        # 從資料庫查詢
        conn = connect_db()
        c = conn.cursor()
        
        # 使用者角色判斷
        if self.user['role'] in ('doctor', 'radiologist'):
            query = """
            SELECT i.id, i.uploaded_at, i.thumbdata, i.imagedata, i.filename, i.mime, 
                p.name, i.transmission_status
            FROM imageuploads i
            JOIN patients p ON i.patient_id = p.id
            WHERE p.name LIKE ?
            ORDER BY i.uploaded_at DESC
            """
        else:
            query = """
            SELECT i.id, i.uploaded_at, i.thumbdata, i.imagedata, i.filename, i.mime, 
                p.name, i.transmission_status
            FROM imageuploads i
            JOIN patients p ON i.patient_id = p.id
            WHERE i.uploader_id = ? AND p.name LIKE ?
            ORDER BY i.uploaded_at DESC
            """

        kw = f"%{self.kw.get()}%"
        
        if self.user['role'] in ('doctor', 'radiologist'):
            c.execute(query, (kw,))
        else:
            c.execute(query, (self.user['id'], kw))

        rows = c.fetchall()
        conn.close()

        if not rows:
            ctk.CTkLabel(
                self.imageslistframe,
                text="🔍 查無資料",
                font=FONT.get("body"),
                text_color=COLOR["inksubtle"]
            ).pack(pady=20)
            return

        # 顯示影像卡片
        for iid, ts, th, full, fname, mime, pname, status in rows:
            # 新增：檢查資料完整性
            th_size = len(th) if th else 0
            full_size = len(full) if full else 0
            
            if th_size == 0 and full_size == 0:
                print(f"⚠️  影像 {fname} (ID: {iid}) 沒有任何影像資料")
            else:
                print(f"✓ 影像 {fname} - 縮圖: {th_size} bytes, 完整: {full_size} bytes")
            
            self.create_image_card(iid, ts, th, full, fname, mime, pname, status)
        
        print("=== 查詢完成 ===\n")

    
    def create_image_card(self, iid, ts, th, full, fname, mime, pname, status):
        """建立單一影像卡片"""
        cell = Card(self.imageslistframe)
        cell.pack(fill="x", pady=6)
        
        line = ctk.CTkFrame(cell, fg_color=COLOR["surface"])
        line.pack(fill="x", padx=PAD, pady=PAD)
        
        # 縮圖
        box = ctk.CTkFrame(
            line, 
            fg_color="#FFFFFF", 
            corner_radius=12,
            width=120, 
            height=90
        )
        box.pack_propagate(False)
        box.pack(side="left", padx=(0, 12))
        
        try:
            image_data = th or full
            
            if image_data:
                # 確保資料是 bytes 類型
                if not isinstance(image_data, bytes):
                    image_data = bytes(image_data)
                
                print(f"[DEBUG] 處理影像 {fname}, 資料大小: {len(image_data)} bytes")
                
                # 建立 BytesIO 並載入影像
                bio = io.BytesIO(image_data)
                bio.seek(0)
                
                im = Image.open(bio)
                print(f"[DEBUG] PIL 成功開啟影像: {im.format} {im.size} {im.mode}")
                
                im.thumbnail((120, 90), Image.Resampling.LANCZOS)
                imtk = ImageTk.PhotoImage(im)
                
                lbl = tk.Label(box, image=imtk, bg="#FFFFFF")
                lbl.image = imtk  # 保存參考
                lbl.pack(expand=True)
                
                # 額外保存到 box
                box._image_ref = imtk
                
            else:
                raise Exception("無影像資料")
                
        except Exception as e:
            print(f"✗ 縮圖載入錯誤 ({fname}): {e}")
            import traceback
            traceback.print_exc()
            
            icon = "🎬" if mime and mime.startswith("video/") else "📄"
            ctk.CTkLabel(
                box, 
                text=icon, 
                font=ctk.CTkFont(size=40),
                text_color="#999999"
            ).pack(expand=True)
        
        info = ctk.CTkFrame(line, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True)

        # 確保變數有預設值
        file_type = "🎬 影片" if (mime and mime.startswith("video/")) else "🖼️ 影像"

        # 傳輸狀態標籤（加入預設值處理）
        status_emoji = {
            'pending': '⏳ 待傳輸',
            'encrypting': '🔐 加密中',
            'transmitted': '📡 已傳輸',
            'verified': '✅ 已驗證',
            None: '✅ 完成'
        }.get(status, '📋 處理中')

        # 確保所有變數都有值
        pname_safe = pname if pname else "未知病人"
        fname_safe = fname if fname else "未知檔案"
        ts_safe = ts if ts else "未知時間"

        # 第一行：病人名稱 | 檔案類型 | 狀態
        label1 = ctk.CTkLabel(
            info, 
            text=f"{pname_safe} | {file_type} | {status_emoji}",
            font=FONT.get("h3"),
            text_color=COLOR["ink"],
            anchor="w"  # 文字靠左對齊
        )
        label1.pack(anchor="w", fill="x")

        # 第二行：時間 | 檔案名稱（限制檔名長度）
        # 如果檔名太長，截斷並加上省略號
        max_filename_length = 40
        if len(fname_safe) > max_filename_length:
            fname_display = fname_safe[:max_filename_length] + "..."
        else:
            fname_display = fname_safe

        label2 = ctk.CTkLabel(
            info, 
            text=f"⏰ {ts_safe} | 📁 {fname_display}",
            font=FONT.get("meta"),
            text_color=COLOR["inksubtle"],
            anchor="w"  # 文字靠左對齊
        )
        label2.pack(anchor="w", pady=(4, 0), fill="x")
    
    def preview(self, blob, pname, ts, mime, filename):
        """預覽影像或影片"""
        win = ctk.CTkToplevel(self.parent_root)
        win.title(f"{pname} - 檢視")
        win.geometry("1000x750")
        win.update_idletasks()
        
        x = (win.winfo_screenwidth() // 2) - (1000 // 2)
        y = (win.winfo_screenheight() // 2) - (750 // 2)
        win.geometry(f"1000x750+{x}+{y}")
        
        # 標題區域
        head = Card(win)
        head.pack(fill="x", padx=PAD, pady=(PAD, 8))
        
        head_inner = ctk.CTkFrame(head, fg_color=COLOR["surface"])
        head_inner.pack(fill="x", padx=PAD, pady=PAD)
        
        file_type = "🎬 影片檔案" if mime.startswith("video/") else "🖼️ 影像檔案"
        
        ctk.CTkLabel(
            head_inner, 
            text=f"{pname} | {file_type} | 🔐 經過安全通道傳輸",
            font=FONT.get("h2"),
            text_color=COLOR["ink"]
        ).pack(anchor="w")
        
        ctk.CTkLabel(
            head_inner, 
            text=f"⏰ {ts} | 📁 {filename}",
            font=FONT.get("meta"),
            text_color=COLOR["inksubtle"]
        ).pack(anchor="w", pady=(4, 0))
        
        # 內容區域
        viewport = Card(win)
        viewport.pack(fill="both", expand=True, padx=PAD, pady=(0, 8))
        
        if mime.startswith("video/"):
            # 影片播放
            player = VideoPlayer(viewport, blob, filename)
            
            def on_close():
                try:
                    player.cleanup()
                except Exception as e:
                    print(f"清理播放器錯誤: {e}")
                finally:
                    try:
                        win.destroy()
                    except:
                        pass
            
            win.protocol("WM_DELETE_WINDOW", on_close)
        else:
            # 影像顯示
            area = ctk.CTkScrollableFrame(viewport, fg_color="#FFFFFF")
            area.pack(fill="both", expand=True, padx=PAD, pady=PAD)
            
            try:
                img = Image.open(io.BytesIO(blob))
                orig_w, orig_h = img.width, img.height
                
                # 資訊列
                info_bar = ctk.CTkFrame(area, fg_color=COLOR["chip"], corner_radius=8)
                info_bar.pack(fill="x", padx=20, pady=(10, 10))
                
                info_text = f"📐 原始尺寸: {orig_w} × {orig_h} px | 💾 大小: {len(blob)/(1024*1024):.2f} MB | 🔐 已解密驗證"
                ctk.CTkLabel(
                    info_bar, 
                    text=info_text,
                    font=FONT.get("meta"),
                    text_color=COLOR["primary"]
                ).pack(padx=12, pady=8)
                
                # 縮放顯示
                max_w, max_h = 900, 550
                scale = min(max_w / orig_w, max_h / orig_h, 1.0)
                new_w, new_h = int(orig_w * scale), int(orig_h * scale)
                
                display_img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(display_img)
                
                img_frame = ctk.CTkFrame(area, fg_color="#F5F5F5", corner_radius=12)
                img_frame.pack(padx=20, pady=10)
                
                img_label = tk.Label(img_frame, image=photo, bg="#F5F5F5")
                img_label.image = photo
                img_label.pack(padx=20, pady=20)
                
                # 匯出按鈕
                def export_image():
                    save_path = filedialog.asksaveasfilename(
                        defaultextension=".jpg",
                        initialfile=filename,
                        filetypes=[
                            ("JPEG 圖片", "*.jpg *.jpeg"),
                            ("PNG 圖片", "*.png"),
                            ("所有檔案", "*.*")
                        ]
                    )
                    
                    if save_path:
                        try:
                            img.save(save_path)
                            messagebox.showinfo("成功", f"✅ 影像已匯出至:\n{save_path}")
                        except Exception as e:
                            messagebox.showerror("錯誤", f"匯出失敗: {e}")
                
                export_btn_frame = ctk.CTkFrame(area, fg_color="transparent")
                export_btn_frame.pack(pady=10)
                OutlineBtn(export_btn_frame, "💾 匯出影像", export_image, w=150).pack()
                
            except Exception as e:
                error_frame = ctk.CTkFrame(area, fg_color="#FFF5F5", corner_radius=12)
                error_frame.pack(fill="x", padx=20, pady=20)
                
                ctk.CTkLabel(
                    error_frame,
                    text=f"❌ 無法顯示影像\n錯誤: {str(e)}",
                    font=FONT.get("body"),
                    text_color=COLOR["danger"],
                    justify="center"
                ).pack(padx=40, pady=40)
        
        # 底部關閉按鈕
        btn_bottom = ctk.CTkFrame(win, fg_color="transparent")
        btn_bottom.pack(fill="x", padx=PAD, pady=(0, PAD))
        
        close_func = on_close if mime.startswith("video/") else win.destroy
        OutlineBtn(btn_bottom, "✖️ 關閉", close_func, w=120, h=40).pack()
