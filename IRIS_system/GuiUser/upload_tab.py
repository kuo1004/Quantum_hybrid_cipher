# -*- coding: utf-8 -*-
"""
upload_tab.py - 上傳影像功能模組（完整版）
"""

import os
import io
import json  # <--- 新增
import shutil # <--- 新增
from PIL import Image, ImageDraw, ImageFont
import customtkinter as ctk
from tkinter import messagebox, filedialog
from .database import connect_db
from .config import COLOR, FONT, Card, SolidBtn, OutlineBtn, PAD, GAP, can, IMAGEEXTS, VIDEOEXTS

class UploadTab:
    """上傳影像標籤頁"""
    
    def __init__(self, root, user, toast_callback, reload_images_callback, switch_tab_callback):
        self.root = root
        self.user = user
        self.toast = toast_callback
        self.reload_images = reload_images_callback
        self.switch_tab = switch_tab_callback
        self.patientvar = None
        self.fileinfo = None
        self.setup_ui()
    
    def setup_ui(self):
        """設置上傳介面"""
        if not can(self.user["role"], "upload"):
            card = Card(self.root)
            card.pack(fill="both", expand=True)
            wrap = ctk.CTkFrame(card, fg_color=COLOR["surface"])
            wrap.pack(fill="x", padx=PAD, pady=PAD)
            ctk.CTkLabel(wrap, text="您沒有上傳權限", font=FONT["h2"],
                         text_color=COLOR["ink"]).pack(anchor="w")
            return

        # Step 1: 選擇病人
        step1 = Card(self.root)
        step1.pack(fill="x", pady=(0, GAP))
        s1 = ctk.CTkFrame(step1, fg_color="transparent")
        s1.pack(fill="x", padx=PAD, pady=PAD)
        ctk.CTkLabel(s1, text="步驟 1：選擇病人", font=FONT["h2"],
                     text_color=COLOR["ink"]).pack(anchor="w")
        self.patientvar = ctk.StringVar()
        self.build_patient_radiolist(s1)

        # Step 2: 上傳檔案
        step2 = Card(self.root)
        step2.pack(fill="both", expand=True, pady=(0, 0))
        s2 = ctk.CTkFrame(step2, fg_color="transparent")
        s2.pack(fill="both", expand=True, padx=PAD, pady=PAD)
        ctk.CTkLabel(s2, text="步驟 2：上傳影像或影片", font=FONT["h2"],
                     text_color=COLOR["ink"]).pack(anchor="w")
        
        self.fileinfo = ctk.CTkLabel(s2, text="尚未選擇檔案", font=FONT["meta"],
                                     text_color=COLOR["inksubtle"])
        self.fileinfo.pack(anchor="w", pady=(6, 8))
        
        row = ctk.CTkFrame(s2, fg_color="transparent")
        row.pack(fill="x")
        
        SolidBtn(row, "📤 選擇並上傳檔案", self.pick_and_upload, w=160).pack(side="left")
        OutlineBtn(row, "🖼️ 上傳測試範例", self.upload_sample_image, w=180).pack(side="left", padx=8)
        
        ctk.CTkLabel(
            s2,
            text="📁 支援格式: JPG/PNG/BMP/DICOM (影像) | MP4/MOV/AVI/MKV (影片)",
            font=FONT["meta"], text_color=COLOR["muted"]
        ).pack(anchor="w", pady=(8, 0))

    def build_patient_radiolist(self, parent):
        """建立病人選擇列表"""
        for w in parent.winfo_children():
            if isinstance(w, ctk.CTkScrollableFrame):
                w.destroy()
        
        lst = ctk.CTkScrollableFrame(parent, fg_color=COLOR["surface"], height=150)
        lst.pack(fill="x", pady=(6, 0))
        
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, IFNULL(mrn,'') FROM patients ORDER BY name")
            rows = cursor.fetchall()
            conn.close()
        except Exception as e:
            self.toast(f"{e}", "danger")
            rows = []
        
        if rows:
            self.patientvar.set(str(rows[0][0]))
            for pid, name, mrn in rows:
                label = f"{name} (MRN:{mrn or '-'} ID:{pid})"
                ctk.CTkRadioButton(
                    lst, text=label, variable=self.patientvar, value=str(pid),
                    font=FONT["body"], text_color=COLOR["ink"]
                ).pack(anchor="w", pady=2)

    def pick_and_upload(self):
        """選擇檔案並上傳"""
        path = filedialog.askopenfilename(
            title="選擇影像或影片",
            filetypes=[
                ("所有支援格式", "*.jpg *.jpeg *.png *.bmp *.tiff *.tif *.dcm *.mp4 *.mov *.avi *.mkv *.wmv"),
                ("影像檔案", "*.jpg *.jpeg *.png *.bmp *.tiff *.tif *.dcm"),
                ("影片檔案", "*.mp4 *.mov *.avi *.mkv *.wmv"),
                ("所有檔案", "*.*")
            ]
        )
        if path:
            self.upload_path(path)

    def upload_sample_image(self):
        """上傳測試範例影像"""
        img = Image.new("RGB", (1200, 800), (245, 248, 255))
        d = ImageDraw.Draw(img)
        d.rectangle((60, 60, 1140, 740), outline=(20, 90, 255), width=6)
        try:
            fnt = ImageFont.truetype("Arial.ttf", 56)
        except:
            fnt = None
        d.text((120, 360), "IRIS TEST IMAGE", fill=(20, 90, 255), font=fnt, anchor="ls")
        tmp = "tmp_iris_test.jpg"
        img.save(tmp, "JPEG", quality=90)
        self.upload_path(tmp, overridename="iris_test.jpg")

    # ----- 這是被修改的核心函數 -----
    def upload_path(self, path, overridename=None):
        """
        處理檔案上傳：將檔案複製到 input 資料夾，並生成對應的 .meta.json。
        """
        try:
            # 1. 檢查是否已選擇病人
            if not self.patientvar.get():
                self.toast("請先選擇病人", "danger")
                return

            # 2. 定義 input 目錄，並確保它存在
            input_dir = ".medicalimages/input"
            os.makedirs(input_dir, exist_ok=True)

            # 3. 準備目標檔案路徑
            filename = overridename or os.path.basename(path)
            dest_path = os.path.join(input_dir, filename)
            meta_path = dest_path + ".meta.json"

            # 4. 防止重複提交
            if os.path.exists(dest_path) or os.path.exists(meta_path):
                self.toast(f"檔案 '{filename}' 已在處理佇列中，請勿重複提交。", "warning")
                return
            
            # 5. 判斷檔案類型與元資料
            ext = os.path.splitext(filename)[1].lower()
            file_size = os.path.getsize(path)
            
            mime_type = "application/octet-stream"  # 預設值
            is_dicom = False
            if ext in IMAGEEXTS:
                if ext == ".dcm":
                    mime_type = "application/dicom"
                    is_dicom = True
                elif ext == ".png":
                    mime_type = "image/png"
                else:
                    mime_type = "image/jpeg"
            elif ext in VIDEOEXTS:
                mime_type = "video/mp4" # 可根據需要細分
            
            # 6. 建立包含所有必要資訊的 meta 字典
            app_meta = {
                "patient_id": int(self.patientvar.get()),
                "uploader_id": self.user["id"],  # 假設 self.user 是一個包含 'id' 的字典
                "filename": filename,
                "mime": mime_type,
                "size_bytes": file_size,
                "is_dicom": is_dicom
            }

            # 7. 將 meta 字典寫入 .meta.json 檔案
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(app_meta, f, ensure_ascii=False, indent=4)
            
            # 8. 將原始檔案複製到 input 目錄
            shutil.copyfile(path, dest_path)

            # 9. 更新 UI，給予使用者正面回饋
            self.toast(f"檔案 '{filename}' 已提交至加密佇列。", "success")
            
            # 可以在這裡重設介面，或跳轉到影像清單頁
            # self.reload_images()
            # self.switch_tab("影像清單")

        except Exception as e:
            messagebox.showerror("錯誤", f"提交至佇列失敗: {e}")
            # 如果失敗，嘗試刪除可能已產生的孤立檔案
            if 'dest_path' in locals() and os.path.exists(dest_path):
                os.remove(dest_path)
            if 'meta_path' in locals() and os.path.exists(meta_path):
                os.remove(meta_path)
