# -*- coding: utf-8 -*-
"""
images_tab.py - 影像清單查看模組（安全版）
"""
import io
import os
import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox, filedialog
from PIL import Image, ImageTk
from .database import connect_db
from .config import COLOR, FONT, Card, Subtle, SolidBtn, OutlineBtn, PAD, GAP
from .video_player import VideoPlayer

class ImagesTab:
    """影像清單標籤頁"""

    def __init__(self, root, user, parent_root):
        self.root = root
        self.user = user
        self.parent_root = parent_root
        self.kw = None
        self.imageslistframe = None
        self.setup_ui()

    def setup_ui(self):
        bar = Subtle(self.root)
        bar.pack(fill="x", pady=(0, GAP))

        row = ctk.CTkFrame(bar, fg_color=COLOR["surfacealt"])
        row.pack(fill="x", padx=PAD, pady=PAD)

        ctk.CTkLabel(row, text="🔍 搜尋病人:", font=FONT.get("body"), 
                    text_color=COLOR["inksubtle"]).pack(side="left")

        self.kw = ctk.StringVar()
        ctk.CTkEntry(row, textvariable=self.kw, placeholder_text="輸入病人姓名", 
                    height=44, corner_radius=12, font=FONT.get("body")).pack(
                        side="left", fill="x", expand=True, padx=(12, 0))

        OutlineBtn(row, "搜尋", self.reload_images, w=88).pack(side="left", padx=8)

        desc = ctk.CTkFrame(bar, fg_color=COLOR["surfacealt"])
        desc.pack(fill="x", padx=PAD, pady=(0, PAD))

        ctk.CTkLabel(desc, text="📌 功能說明: 影像清單用於「查看和管理所有已上傳的醫學影像和影片」", 
                    font=FONT.get("meta"), text_color=COLOR["inksubtle"]).pack(anchor="w")

        lstcard = Card(self.root)
        lstcard.pack(fill="both", expand=True, pady=(0, 0))

        self.imageslistframe = ctk.CTkScrollableFrame(lstcard, fg_color=COLOR["surface"])
        self.imageslistframe.pack(fill="both", expand=True, padx=PAD, pady=PAD)

        self.reload_images()

    def reload_images(self):
        if not self.imageslistframe:
            return

        for w in self.imageslistframe.winfo_children():
            w.destroy()

        kw = f"%{self.kw.get()}%"
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT i.id, i.uploaded_at, i.thumbdata, i.imagedata, 
                       i.filename, i.mime, p.name
                FROM imageuploads i
                JOIN patients p ON i.patient_id = p.id
                WHERE p.name LIKE ?
                ORDER BY i.uploaded_at DESC LIMIT 200
            """, (kw,))
            rows = cursor.fetchall()
            conn.close()

            if not rows:
                empty = Subtle(self.imageslistframe)
                empty.pack(fill="x", pady=6)
                ctk.CTkLabel(empty, text="沒有找到影像", font=FONT.get("body"), 
                            text_color=COLOR["inksubtle"]).pack(padx=PAD, pady=PAD)
                return

            for iid, ts, th, full, fname, mime, pname in rows:
                cell = Card(self.imageslistframe)
                cell.pack(fill="x", pady=6)

                line = ctk.CTkFrame(cell, fg_color=COLOR["surface"])
                line.pack(fill="x", padx=PAD, pady=PAD)

                box = ctk.CTkFrame(line, fg_color="#FFFFFF", corner_radius=12, 
                                  width=120, height=90)
                box.pack_propagate(False)
                box.pack(side="left", padx=(0, 12))

                try:
                    im = Image.open(io.BytesIO(th or full))
                    im.thumbnail((120, 90))
                    imtk = ImageTk.PhotoImage(im)
                    lbl = tk.Label(box, image=imtk, bg="#FFFFFF")
                    lbl.image = imtk
                    lbl.pack(expand=True)
                except Exception:
                    icon = "🎬" if mime.startswith("video/") else "📄"
                    ctk.CTkLabel(box, text=icon, font=ctk.CTkFont(size=40)).pack(expand=True)

                info = ctk.CTkFrame(line, fg_color="transparent")
                info.pack(side="left", fill="x", expand=True)

                file_type = "🎬 影片" if mime.startswith("video/") else "🖼️ 影像"
                ctk.CTkLabel(info, text=f"{pname} | {file_type}", font=FONT.get("h3"), 
                            text_color=COLOR["ink"]).pack(anchor="w")
                ctk.CTkLabel(info, text=f"⏰ {ts} | 📁 {fname}", 
                            font=FONT.get("meta"), 
                            text_color=COLOR["inksubtle"]).pack(anchor="w", pady=(4, 0))

                SolidBtn(line, "👁️ 檢視", 
                        lambda b=full, n=pname, t=ts, m=mime, fn=fname: 
                            self.preview(b, n, t, m, fn), 
                        w=88).pack(side="right")

        except Exception as e:
            messagebox.showerror("錯誤", f"{e}")

    def preview(self, blob, pname, ts, mime, filename):
        """預覽影像或影片（執行緒安全版）"""
        win = ctk.CTkToplevel(self.parent_root)
        win.title(f"{pname} - 檢視")
        win.geometry("1000x750")

        win.update_idletasks()
        x = (win.winfo_screenwidth() // 2) - (1000 // 2)
        y = (win.winfo_screenheight() // 2) - (750 // 2)
        win.geometry(f"1000x750+{x}+{y}")

        head = Card(win)
        head.pack(fill="x", padx=PAD, pady=(PAD, 8))

        head_inner = ctk.CTkFrame(head, fg_color=COLOR["surface"])
        head_inner.pack(fill="x", padx=PAD, pady=PAD)

        file_type = "🎬 影片檔案" if mime.startswith("video/") else "🖼️ 影像檔案"
        ctk.CTkLabel(head_inner, text=f"{pname} | {file_type}", font=FONT.get("h2"), 
                    text_color=COLOR["ink"]).pack(anchor="w")
        ctk.CTkLabel(head_inner, text=f"⏰ {ts} | 📁 {filename}", font=FONT.get("meta"), 
                    text_color=COLOR["inksubtle"]).pack(anchor="w", pady=(4, 0))

        viewport = Card(win)
        viewport.pack(fill="both", expand=True, padx=PAD, pady=(0, 8))

        if mime.startswith("video/"):
            # 使用 OpenCV 播放器
            player = VideoPlayer(viewport, blob, filename)

            def on_close():
                """安全關閉視窗"""
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

                info_bar = ctk.CTkFrame(area, fg_color=COLOR["chip"], corner_radius=8)
                info_bar.pack(fill="x", padx=20, pady=(10, 10))

                info_text = f"📐 原始尺寸: {orig_w} × {orig_h} px | 💾 大小: {len(blob)/(1024*1024):.2f} MB"
                ctk.CTkLabel(info_bar, text=info_text, font=FONT.get("meta"), 
                            text_color=COLOR["primary"]).pack(padx=12, pady=8)

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

        btn_bottom = ctk.CTkFrame(win, fg_color="transparent")
        btn_bottom.pack(fill="x", padx=PAD, pady=(0, PAD))

        OutlineBtn(btn_bottom, "✖️ 關閉", win.destroy if not mime.startswith("video/") else on_close, 
                  w=120, h=40).pack()