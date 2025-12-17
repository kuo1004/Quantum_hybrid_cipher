# -*- coding: utf-8 -*-
"""
upload_tab.py - 上傳影像功能模組（IRIS 資料庫整合版）
支援：
1. 雙重科別選擇（臨床科別 + 影像檢查科別）
2. 完整加密傳輸
3. 本地暫存
"""

import os
import time
import base64
from PIL import Image, ImageDraw, ImageFont
import customtkinter as ctk
from tkinter import messagebox, filedialog
from .config import COLOR, FONT, Card, SolidBtn, OutlineBtn, PAD, GAP, can
from .api_client import get_api_client

# 導入加密模組
try:
    from sender import Sender
    from signature_utils import sign_bytes
    CRYPTO_AVAILABLE = True
except ImportError as e:
    CRYPTO_AVAILABLE = False
    print("⚠️ 警告: 加密模組未安裝")


class UploadTab:
    """上傳影像標籤頁（IRIS 資料庫整合版）"""
    
    def __init__(self, root, user, toast_callback, reload_images_callback, 
                 switch_tab_callback, local_manager=None):
        self.root = root
        self.user = user
        self.toast = toast_callback
        self.reload_images = reload_images_callback
        self.switch_tab = switch_tab_callback
        self.local_manager = local_manager
        
        # UI 變數
        self.patientvar = None
        self.modality_var = None
        self.clinical_var = None
        self.fileinfo = None
        
        self.api_client = get_api_client()
        
        # 初始化 Sender
        self.sender = None
        if CRYPTO_AVAILABLE:
            try:
                self.sender = Sender(f"GUI_Client_{user['username']}")
                print(f"✅ Sender 初始化成功")
            except Exception as e:
                print(f"⚠️ Sender 初始化失敗: {e}")
        
        self.setup_ui()
    
    def setup_ui(self):
        """設置上傳介面"""
        if not can(self.user.get("role", "guest"), "upload"):
            card = Card(self.root)
            card.pack(fill="both", expand=True)
            wrap = ctk.CTkFrame(card, fg_color=COLOR["surface"])
            wrap.pack(fill="x", padx=PAD, pady=PAD)
            ctk.CTkLabel(wrap, text="您沒有上傳權限", font=FONT["h2"],
                         text_color=COLOR["ink"]).pack(anchor="w")
            return

        # ========== 建立滾動框架 ==========
        scroll_frame = ctk.CTkScrollableFrame(
            self.root,
            fg_color="transparent",
            scrollbar_button_color="#CCCCCC",        # 灰色
            scrollbar_button_hover_color="#999999"   # 深灰色（滑鼠移上去時）
        )
        scroll_frame.pack(fill="both", expand=True, padx=0, pady=0)
        
        # ========== 安全狀態提示卡 ==========
        security_card = Card(scroll_frame)
        security_card.pack(fill="x", pady=(0, GAP))
        
        sec_frame = ctk.CTkFrame(security_card, fg_color="transparent")
        sec_frame.pack(fill="x", padx=PAD, pady=PAD)
        
        ctk.CTkLabel(
            sec_frame, 
            text="🔐 安全加密傳輸", 
            font=FONT["h2"],
            text_color=COLOR["ink"]
        ).pack(anchor="w")
        
        if CRYPTO_AVAILABLE and self.sender:
            status_text = "✅ 加密模組已啟動 - 您的影像將受到完整保護"
            status_color = COLOR["success"]
        else:
            status_text = "⚠️ 加密模組未載入 - 無法上傳影像"
            status_color = COLOR["danger"]
        
        ctk.CTkLabel(
            sec_frame,
            text=status_text,
            font=FONT["body"],
            text_color=status_color
        ).pack(anchor="w", pady=(6, 0))

        # ========== Step 1: 選擇病人 ==========
        step1 = Card(scroll_frame)
        step1.pack(fill="x", pady=(0, GAP))
        s1 = ctk.CTkFrame(step1, fg_color="transparent")
        s1.pack(fill="x", padx=PAD, pady=PAD)
        
        ctk.CTkLabel(s1, text="步驟 1：選擇病人（可輸入姓名或身分證字號快速搜尋）", font=FONT["h2"],
                     text_color=COLOR["ink"]).pack(anchor="w")
        
        self.patientvar = ctk.StringVar()
        self.build_patient_search(s1)

        # ========== Step 2: 選擇科別 ==========
        step2 = Card(scroll_frame)
        step2.pack(fill="x", pady=(0, GAP))
        s2 = ctk.CTkFrame(step2, fg_color="transparent")
        s2.pack(fill="x", padx=PAD, pady=PAD)
        
        ctk.CTkLabel(s2, text="步驟 2：選擇本次檢查科別並上傳影像/影片", font=FONT["h2"],
                     text_color=COLOR["ink"]).pack(anchor="w")
        
        # 科別選擇區域
        dept_frame = ctk.CTkFrame(s2, fg_color=COLOR["surface"], corner_radius=8)
        dept_frame.pack(fill="x", pady=(8, 0))
        dept_inner = ctk.CTkFrame(dept_frame, fg_color="transparent")
        dept_inner.pack(fill="x", padx=PAD, pady=PAD)
        
        # 影像檢查科別
        mod_row = ctk.CTkFrame(dept_inner, fg_color="transparent")
        mod_row.pack(fill="x", pady=(0, 8))
        
        ctk.CTkLabel(
            mod_row,
            text="📷 影像檢查類別:",
            font=FONT["body"],
            text_color=COLOR["ink"]
        ).pack(side="left", padx=(0, 12))
        
        self.modality_var = ctk.StringVar()
        self.modality_dropdown = ctk.CTkOptionMenu(
            mod_row,
            variable=self.modality_var,
            values=["CT", "MR", "CR", "DX", "US", "NM", "PT", "XA", "MG", "RF", "ES", "OT"],
            width=200,
            height=36,
            corner_radius=8,
            font=FONT["body"]
        )
        self.modality_dropdown.pack(side="left")
        self.modality_var.set("CR")  # 預設 X光片
        
        # 臨床科別
        clin_row = ctk.CTkFrame(dept_inner, fg_color="transparent")
        clin_row.pack(fill="x")
        
        ctk.CTkLabel(
            clin_row,
            text="🏥 臨床科別:",
            font=FONT["body"],
            text_color=COLOR["ink"]
        ).pack(side="left", padx=(0, 12))
        
        self.clinical_var = ctk.StringVar()
        self.clinical_dropdown = ctk.CTkOptionMenu(
            clin_row,
            variable=self.clinical_var,
            values=["CARD-心臟內科", "NEU-神經內科", "ORTHO-骨科", "GI-腸胃內科", 
                   "RESP-胸腔內科", "ENDO-內分泌科", "ONCO-腫瘤科", "SURG-外科"],
            width=200,
            height=36,
            corner_radius=8,
            font=FONT["body"]
        )
        self.clinical_dropdown.pack(side="left")
        self.clinical_var.set("CARD-心臟內科")  # 預設心臟內科

        # ========== Step 3: 上傳檔案 ==========
        step3 = Card(scroll_frame)
        step3.pack(fill="x", pady=(0, GAP))
        s3 = ctk.CTkFrame(step3, fg_color="transparent")
        s3.pack(fill="x", padx=PAD, pady=PAD)
        
        ctk.CTkLabel(s3, text="步驟 3：選擇並上傳影像/影片", font=FONT["h2"],
                     text_color=COLOR["ink"]).pack(anchor="w")
        
        self.fileinfo = ctk.CTkLabel(s3, text="尚未選擇檔案", font=FONT["meta"],
                                     text_color=COLOR["inksubtle"])
        self.fileinfo.pack(anchor="w", pady=(6, 8))
        
        row = ctk.CTkFrame(s3, fg_color="transparent")
        row.pack(fill="x")
        
        upload_btn = SolidBtn(row, "📤 選擇並上傳檔案", self.pick_and_upload, w=160)
        upload_btn.pack(side="left")
        if not (CRYPTO_AVAILABLE and self.sender):
            upload_btn.configure(state="disabled")
        
        OutlineBtn(row, "🖼️ 上傳測試範例", self.upload_sample_image, w=180).pack(side="left", padx=8)
        
        # 支援格式說明
        format_frame = ctk.CTkFrame(s3, fg_color="transparent")
        format_frame.pack(fill="x", pady=(8, 0))
        
        ctk.CTkLabel(
            format_frame,
            text="📁 支援影像:  PNG, DICOM (.dcm)",
            font=FONT["meta"], 
            text_color=COLOR["muted"]
        ).pack(anchor="w")
        
        ctk.CTkLabel(
            format_frame,
            text="🎬 支援影片: MP4",
            font=FONT["meta"], 
            text_color=COLOR["muted"]
        ).pack(anchor="w", pady=(2, 0))

    def build_patient_search(self, parent):
        """建立病人搜尋和列表"""
        # 搜尋框
        search_frame = ctk.CTkFrame(parent, fg_color="transparent")
        search_frame.pack(fill="x", pady=(6, 0))
        
        ctk.CTkLabel(
            search_frame,
            text="🔎 病人搜尋:",
            font=FONT["body"],
            text_color=COLOR["inksubtle"]
        ).pack(side="left", padx=(0, 8))
        
        self.search_var = ctk.StringVar()
        self.search_var.trace('w', lambda *args: self.filter_patients())
        
        search_entry = ctk.CTkEntry(
            search_frame,
            textvariable=self.search_var,
            placeholder_text="輸入姓名或身分證字號",
            width=300,
            height=36,
            corner_radius=8,
            font=FONT["body"]
        )
        search_entry.pack(side="left", padx=(0, 8))
        
        OutlineBtn(search_frame, "清除", lambda: self.search_var.set(""), w=80).pack(side="left")
        
        # 病人列表
        self.patient_list_frame = ctk.CTkScrollableFrame(
            parent, 
            fg_color=COLOR["surface"], 
            height=200
        )
        self.patient_list_frame.pack(fill="x", pady=(8, 0))
        
        # 載入病人列表
        self.load_patients()
    
    def load_patients(self):
        """從後端載入病人列表"""
        try:
            result = self.api_client.list_patients()
            
            if result and result.get('patients'):
                self.all_patients = result['patients']
                self.filter_patients()
            else:
                self.all_patients = []
                ctk.CTkLabel(
                    self.patient_list_frame,
                    text="⚠️ 無法載入病患列表或無病患資料",
                    font=FONT["body"],
                    text_color=COLOR["danger"]
                ).pack(anchor="w", pady=4)
                
        except Exception as e:
            self.all_patients = []
            ctk.CTkLabel(
                self.patient_list_frame,
                text=f"❌ 載入病患列表失敗: {e}",
                font=FONT["body"],
                text_color=COLOR["danger"]
            ).pack(anchor="w", pady=4)
    
    def filter_patients(self):
        """篩選病人列表"""
        # 清空現有列表
        for widget in self.patient_list_frame.winfo_children():
            widget.destroy()
        
        keyword = self.search_var.get().strip().lower()
        
        # 篩選病人
        if keyword:
            filtered = [
                p for p in self.all_patients 
                if keyword in p.get('name', '').lower() or 
                   keyword in p.get('national_id', '').lower() or
                   keyword in p.get('mrn', '').lower()
            ]
        else:
            filtered = self.all_patients
        
        # 顯示篩選結果
        if not filtered:
            ctk.CTkLabel(
                self.patient_list_frame,
                text="找不到符合的病患",
                font=FONT["body"],
                text_color=COLOR["muted"]
            ).pack(anchor="w", pady=4)
            return
        
        # 預選第一個
        if filtered and not self.patientvar.get():
            self.patientvar.set(str(filtered[0]['id']))
        
        # 顯示病人列表
        for patient in filtered:
            pid = patient['id']
            name = patient.get('name', '未知')
            mrn = patient.get('mrn', '-')
            national_id = patient.get('national_id', '-')
            birthday = patient.get('birthday', '-')
            gender_map = {'M': '男', 'F': '女', 'O': '其他'}
            gender = gender_map.get(patient.get('gender', 'O'), '未知')
            
            # 病人卡片
            patient_card = ctk.CTkFrame(
                self.patient_list_frame,
                fg_color=COLOR["surfacealt"],
                corner_radius=8
            )
            patient_card.pack(fill="x", pady=2)
            
            # Radio button + 資訊
            radio_frame = ctk.CTkFrame(patient_card, fg_color="transparent")
            radio_frame.pack(fill="x", padx=8, pady=8)
            
            ctk.CTkRadioButton(
                radio_frame,
                text=f"{name} ({gender})",
                variable=self.patientvar,
                value=str(pid),
                font=FONT["body"],
                text_color=COLOR["ink"]
            ).pack(side="left")
            
            # 詳細資訊
            info_frame = ctk.CTkFrame(radio_frame, fg_color="transparent")
            info_frame.pack(side="right")
            
            info_text = f"MRN:{mrn} | 身分證:{national_id} | 生日:{birthday}"
            ctk.CTkLabel(
                info_frame,
                text=info_text,
                font=FONT["meta"],
                text_color=COLOR["inksubtle"]
            ).pack()

    def pick_and_upload(self):
        """選擇檔案並上傳"""
        path = filedialog.askopenfilename(
            title="選擇影像或影片",
            filetypes=[
                ("所有醫療檔案", "*.jpg *.jpeg *.png *.bmp *.tiff *.tif *.dcm *.mp4 *.avi *.mov *.mkv *.wmv"),
                ("影像檔案", "*.jpg *.jpeg *.png *.bmp *.tiff *.tif *.dcm"),
                ("影片檔案", "*.mp4 *.avi *.mov *.mkv *.wmv *.flv *.webm"),
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
        """上傳檔案（完整加密傳輸流程）"""
        try:
            # 1. 檢查選擇
            if not self.patientvar.get():
                self.toast("請先選擇病人", "danger")
                return
            
            patient_id = self.patientvar.get()
            
            # 2. 檢查加密模組
            if not CRYPTO_AVAILABLE or not self.sender:
                messagebox.showerror("錯誤", "加密模組未載入，無法上傳")
                return
            
            # 3. 讀取檔案
            filename = overridename or os.path.basename(path)
            file_ext = os.path.splitext(filename)[1].lower()
            
            # 判斷檔案類型
            video_exts = ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm']
            if file_ext in video_exts:
                file_type = "影片"
                file_icon = "🎬"
            else:
                file_type = "影像"
                file_icon = "🖼️"
            
            self.fileinfo.configure(text=f"📂 讀取{file_type}: {filename}")
            
            with open(path, 'rb') as f:
                imagedata = f.read()
            
            file_size_mb = len(imagedata) / (1024 * 1024)
            if file_size_mb > 100:
                if not messagebox.askyesno(
                    "檔案較大",
                    f"檔案大小: {file_size_mb:.1f} MB\n\n是否繼續上傳？"
                ):
                    self.fileinfo.configure(text="❌ 已取消上傳")
                    return
            
            print(f"\n🔐 開始加密傳輸流程")
            print(f"   類型: {file_type}")
            print(f"   檔案: {filename}")
            print(f"   大小: {file_size_mb:.2f} MB")
            
            # 4. 本地暫存
            patient_info = self._get_patient_info(patient_id)
            if self.local_manager:
                try:
                    local_image_info = self.local_manager.add_image(
                        image_path=path,
                        patient_id=patient_id,
                        patient_name=patient_info.get('name', '未知'),
                        mrn=patient_info.get('mrn', '-'),
                        upload_time=time.strftime("%Y-%m-%d %H:%M:%S")
                    )
                except Exception as e:
                    print(f"⚠️ 本地暫存失敗: {e}")
            
            # 5. 準備元資料（包含科別資訊）
            modality_code = self.modality_var.get()
            clinical_full = self.clinical_var.get()
            clinical_code = clinical_full.split('-')[0] if '-' in clinical_full else clinical_full
            
            app_meta = {
                "patient_id": int(patient_id),
                "uploader_id": self.user["id"],
                "filename": filename,
                "mime": self._get_mime_type(path),
                "upload_time": time.time(),
                "modality_dept_code": modality_code,
                "clinical_dept_code": clinical_code
            }
            
            # 6-9. 加密傳輸流程
            self.fileinfo.configure(text=f"🔐 獲取 Server 憑證...")
            server_certificate = self.api_client.get_server_certificate()
            
            if not server_certificate:
                messagebox.showerror("錯誤", "無法獲取 Server 憑證")
                return
            
            self.fileinfo.configure(text=f"✍️ 簽署資料...")
            signature = sign_bytes(self.sender.private_key, imagedata)
            
            self.fileinfo.configure(text=f"🔐 加密資料...")
            transmission_package = self.sender.encrypt_and_prepare_transmission(
                plaintext_bytes=imagedata,
                receiver_certificate=server_certificate,
                signature=signature,
                app_meta=app_meta
            )
            
            self.fileinfo.configure(text=f"📤 傳送到 Server...")
            result = self.api_client.upload_image(transmission_package)
            
            # 10. 處理結果
            if result and result.get('status') == 'success':
                image_id = result.get('image_id')
                self.toast(f"✅ 上傳成功！Image ID: {image_id}", "success")
                self.fileinfo.configure(text=f"✅ {filename} - 上傳完成")
                
                if self.local_manager and 'local_image_info' in locals():
                    self.local_manager.update_status(local_image_info['id'], 'uploaded')
                
                if self.reload_images:
                    self.reload_images()
                
                if self.switch_tab:
                    self.switch_tab("影像清單")
            else:
                error_msg = result.get('message', '未知錯誤') if result else '上傳失敗'
                messagebox.showerror("上傳失敗", error_msg)
                self.fileinfo.configure(text=f"❌ {filename} - 上傳失敗")
            
        except Exception as e:
            messagebox.showerror("錯誤", f"上傳失敗: {e}")
            self.fileinfo.configure(text="上傳失敗")
            import traceback
            traceback.print_exc()
    
    def _get_patient_info(self, patient_id):
        """獲取病患資訊"""
        for patient in self.all_patients:
            if str(patient['id']) == str(patient_id):
                return patient
        return {'name': '未知', 'mrn': '-'}
    
    def _get_mime_type(self, file_path):
        """根據副檔名判斷 MIME 類型"""
        ext = os.path.splitext(file_path)[1].lower()
        
        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.bmp': 'image/bmp',
            '.tiff': 'image/tiff',
            '.tif': 'image/tiff',
            '.dcm': 'application/dicom',
            '.mp4': 'video/mp4',
            '.avi': 'video/x-msvideo',
            '.mov': 'video/quicktime',
            '.mkv': 'video/x-matroska',
            '.wmv': 'video/x-ms-wmv',
        }
        
        return mime_types.get(ext, 'application/octet-stream')