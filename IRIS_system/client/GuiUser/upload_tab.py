# -*- coding: utf-8 -*-
"""
upload_tab.py - 上傳影像功能模組（後端整合版 + 本地暫存）
"""

import os
import time
import base64
from PIL import Image, ImageDraw, ImageFont
import customtkinter as ctk
from tkinter import messagebox, filedialog
from .config import COLOR, FONT, Card, SolidBtn, OutlineBtn, PAD, GAP, can, IMAGEEXTS, VIDEOEXTS
from .api_client import get_api_client


# 導入加密模組
try:
    from sender import Sender
    from signature_utils import sign_bytes
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    print("⚠️ 警告: 加密模組未安裝")


class UploadTab:
    """上傳影像標籤頁（後端整合版 + 本地暫存）"""
    
    def __init__(self, root, user, toast_callback, reload_images_callback, 
                 switch_tab_callback, local_manager=None):
        self.root = root
        self.user = user
        self.toast = toast_callback
        self.reload_images = reload_images_callback
        self.switch_tab = switch_tab_callback
        self.local_manager = local_manager  # ← 新增：本地影像管理器（可選）
        self.patientvar = None
        self.fileinfo = None
        self.api_client = get_api_client()
        
        # 初始化 Sender（用於加密）
        self.sender = None
        if CRYPTO_AVAILABLE:
            try:
                self.sender = Sender(f"GUI_Client_{user['username']}")
                print(f"✅ Sender 初始化成功: {self.sender.sender_id}")
            except Exception as e:
                print(f"⚠️ Sender 初始化失敗: {e}")
        
        self.setup_ui()
    
    def setup_ui(self):
        """設置上傳介面（完全保持原樣）"""
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
        ctk.CTkLabel(s2, text="步驟 2：上傳影像", font=FONT["h2"],
                     text_color=COLOR["ink"]).pack(anchor="w")
        
        self.fileinfo = ctk.CTkLabel(s2, text="尚未選擇檔案", font=FONT["meta"],
                                     text_color=COLOR["inksubtle"])
        self.fileinfo.pack(anchor="w", pady=(6, 8))
        
        row = ctk.CTkFrame(s2, fg_color="transparent")
        row.pack(fill="x")
        
        SolidBtn(row, "📤 選擇並上傳檔案", self.pick_and_upload, w=160).pack(side="left")
        OutlineBtn(row, "🖼️ 上傳測試範例", self.upload_sample_image, w=180).pack(side="left", padx=8)
        
        # 加密狀態提示
        crypto_status = "✅ 加密模組已載入" if CRYPTO_AVAILABLE and self.sender else "⚠️ 加密模組未載入"
        crypto_color = COLOR["success"] if CRYPTO_AVAILABLE and self.sender else COLOR["warning"]
        
        ctk.CTkLabel(
            s2,
            text=f"📁 支援格式: JPG/PNG/BMP/DICOM | {crypto_status}",
            font=FONT["meta"], text_color=crypto_color
        ).pack(anchor="w", pady=(8, 0))

    def build_patient_radiolist(self, parent):
        """建立病人選擇列表（從後端獲取）"""
        for w in parent.winfo_children():
            if isinstance(w, ctk.CTkScrollableFrame):
                w.destroy()
        
        lst = ctk.CTkScrollableFrame(parent, fg_color=COLOR["surface"], height=150)
        lst.pack(fill="x", pady=(6, 0))
        
        # 從後端 API 獲取病患列表
        try:
            patients = self.api_client.list_patients()
            
            if not patients:
                ctk.CTkLabel(
                    lst,
                    text="⚠️ 無法從 Server 獲取病患列表",
                    font=FONT["body"],
                    text_color=COLOR["danger"]
                ).pack(anchor="w", pady=4)
                return
            
            if patients:
                self.patientvar.set(str(patients[0]['id']))
                for patient in patients:
                    pid = patient['id']
                    name = patient.get('name', '未知')
                    mrn = patient.get('mrn', '-')
                    label = f"{name} (MRN:{mrn} ID:{pid})"
                    ctk.CTkRadioButton(
                        lst, text=label, variable=self.patientvar, value=str(pid),
                        font=FONT["body"], text_color=COLOR["ink"]
                    ).pack(anchor="w", pady=2)
            else:
                ctk.CTkLabel(
                    lst,
                    text="尚無病患資料，請先在「病人管理」中新增",
                    font=FONT["body"],
                    text_color=COLOR["muted"]
                ).pack(anchor="w", pady=4)
                
        except Exception as e:
            ctk.CTkLabel(
                lst,
                text=f"❌ 載入病患列表失敗: {e}",
                font=FONT["body"],
                text_color=COLOR["danger"]
            ).pack(anchor="w", pady=4)

    def pick_and_upload(self):
        """選擇檔案並上傳"""
        path = filedialog.askopenfilename(
            title="選擇影像",
            filetypes=[
                ("影像檔案", "*.jpg *.jpeg *.png *.bmp *.tiff *.tif *.dcm"),
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

    def upload_path(self, path, overridename=None):
        """
        上傳檔案到後端（+ 本地暫存）
        
        Args:
            path: 檔案路徑
            overridename: 覆蓋檔名（可選）
        """
        try:
            # 1. 檢查是否已選擇病人
            if not self.patientvar.get():
                self.toast("請先選擇病人", "danger")
                return
            
            patient_id = self.patientvar.get()
            
            # 2. 獲取病患資訊（用於本地暫存）
            patient_info = self._get_patient_info(patient_id)
            
            # 3. 檢查加密模組
            if not CRYPTO_AVAILABLE or not self.sender:
                messagebox.showerror("錯誤", "加密模組未載入，無法上傳")
                return
            
            # 4. 讀取檔案
            filename = overridename or os.path.basename(path)
            self.fileinfo.configure(text=f"正在處理: {filename}")
            
            with open(path, 'rb') as f:
                imagedata = f.read()
            
            # ========== 新增：暫存到本地 ==========
            if self.local_manager:
                try:
                    local_image_info = self.local_manager.add_image(
                        image_path=path,
                        patient_id=patient_id,
                        patient_name=patient_info.get('name', '未知'),
                        mrn=patient_info.get('mrn', '-'),
                        upload_time=time.strftime("%Y-%m-%d %H:%M:%S")
                    )
                    if local_image_info:
                        print(f"✅ 本地暫存成功: {local_image_info['local_filename']}")
                except Exception as e:
                    print(f"⚠️ 本地暫存失敗: {e}")
            # ========== 本地暫存結束 ==========
            
            # 5. 準備元資料
            app_meta = {
                "patient_id": int(patient_id),
                "uploader_id": self.user["id"],
                "filename": filename,
                "mime": self._get_mime_type(path),
                "upload_time": time.time()
            }
            
            # 6. 獲取 Server 憑證
            self.toast("獲取 Server 憑證...", "info")
            server_certificate = self.api_client.get_server_certificate()
            
            if not server_certificate:
                messagebox.showerror("錯誤", "無法獲取 Server 憑證")
                return
            
            # 7. 簽章
            self.toast("簽署資料...", "info")
            signature = sign_bytes(self.sender.private_key, imagedata)
            
            # 8. 加密
            self.toast("加密資料...", "info")
            transmission_package = self.sender.encrypt_and_prepare_transmission(
                plaintext_bytes=imagedata,
                receiver_certificate=server_certificate,
                signature=signature,
                app_meta=app_meta
            )
            
            # 9. 上傳到 Server
            self.toast("傳送到 Server...", "info")
            result = self.api_client.upload_image(transmission_package)
            
            if result and result.get('status') == 'success':
                image_id = result.get('image_id')
                self.toast(f"✅ 上傳成功！Image ID: {image_id}", "success")
                self.fileinfo.configure(text=f"✅ {filename} - 上傳完成")
                
                # ========== 新增：更新本地狀態 ==========
                if self.local_manager and local_image_info:
                    self.local_manager.update_status(local_image_info['id'], 'uploaded')
                # ========== 更新狀態結束 ==========
                
                # 刷新影像列表
                if self.reload_images:
                    self.reload_images()
                
                # 切換到影像清單頁
                if self.switch_tab:
                    self.switch_tab("影像清單")
            else:
                error_msg = result.get('message', '未知錯誤') if result else '上傳失敗'
                messagebox.showerror("上傳失敗", error_msg)
                self.fileinfo.configure(text=f"❌ {filename} - 上傳失敗")
                
                # ========== 新增：標記為錯誤 ==========
                if self.local_manager and local_image_info:
                    self.local_manager.update_status(local_image_info['id'], 'error')
                # ========== 標記錯誤結束 ==========
            
        except Exception as e:
            messagebox.showerror("錯誤", f"上傳失敗: {e}")
            self.fileinfo.configure(text="上傳失敗")
            import traceback
            traceback.print_exc()
    
    def _get_patient_info(self, patient_id):
        """獲取病患資訊"""
        try:
            patients = self.api_client.list_patients()
            for patient in patients:
                if str(patient['id']) == str(patient_id):
                    return patient
        except:
            pass
        return {'name': '未知', 'mrn': '-'}
    
    def _get_mime_type(self, file_path):
        """根據副檔名判斷 MIME 類型"""
        ext = os.path.splitext(file_path)[1].lower()
        
        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.bmp': 'image/bmp',
            '.dcm': 'application/dicom',
            '.dat': 'application/octet-stream'
        }
        
        return mime_types.get(ext, 'application/octet-stream')