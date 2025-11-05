# -*- coding: utf-8 -*-
"""
patients_tab.py - 病人管理（完整版）
支援：
1. 顯示完整病患資訊
2. 搜尋功能（姓名、MRN、身分證）
3. 查看病患詳細資料
4. 新增病患功能（完整對話框）
5. 刪除病患功能
6. 載入並顯示病患影像（含縮圖）✨ 新功能
"""

import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox
from PIL import Image, ImageTk
from io import BytesIO
import base64
from .config import COLOR, FONT, PAD, GAP, Card, OutlineBtn, SolidBtn
from .api_client import get_api_client


class PatientsTab:
    """病人管理標籤頁（完整版）"""
    MIN_CARD_W = 360
    COL_GAP = 12

    def __init__(self, parent, user=None, root=None):
        self.parent = parent
        self.root = root or parent
        self.user = user or {"username": "User", "role": "guest", "clinical_dept_id": None}
        self.api_client = get_api_client()
        
        # 快取
        self.thumbnail_cache = {}
        self.all_patients = []
        self.selected_patient = None
        self.images_frame = None  # 用於存儲影像顯示區域

        parent.grid_rowconfigure(1, weight=1)
        parent.grid_columnconfigure(0, weight=2)
        parent.grid_columnconfigure(1, weight=3)

        self._build_search(parent)
        self._build_list(parent)
        self._build_detail(parent)

        self._query_and_render()

    def _build_search(self, parent):
        """搜尋列"""
        bar = Card(parent)
        bar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=PAD, pady=(PAD, 0))
        inner = ctk.CTkFrame(bar, fg_color=COLOR["surface"])
        inner.pack(fill="x", padx=PAD, pady=PAD)

        left = ctk.CTkFrame(inner, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True)
        
        ctk.CTkLabel(left, text="🔎 搜尋病人：", font=FONT["body"]).pack(side="left", padx=(0, 6))
        
        self.search_entry = ctk.CTkEntry(
            left, 
            placeholder_text="輸入姓名、MRN 或身分證",
            width=300, 
            height=36,
            corner_radius=8,
            font=FONT["body"]
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        
        OutlineBtn(left, "🔍 搜尋", self._query_and_render, w=80).pack(side="left", padx=(0, 4))
        OutlineBtn(left, "清除", self._clear_search, w=80).pack(side="left")

        right = ctk.CTkFrame(inner, fg_color="transparent")
        right.pack(side="right")
        
        SolidBtn(right, "+ 新增病人", self._show_add_patient_dialog, w=120).pack(side="right")

    def _build_list(self, parent):
        """病人列表"""
        list_card = Card(parent)
        list_card.grid(row=1, column=0, sticky="nsew", padx=(PAD, self.COL_GAP // 2), pady=(GAP, PAD))

        title_frame = ctk.CTkFrame(list_card, fg_color=COLOR["surface"])
        title_frame.pack(fill="x", padx=PAD, pady=(PAD, 0))
        
        ctk.CTkLabel(
            title_frame, 
            text="病人列表", 
            font=FONT["h2"], 
            text_color=COLOR["ink"]
        ).pack(side="left")
        
        self.count_label = ctk.CTkLabel(
            title_frame, 
            text="共 0 筆病人", 
            font=FONT["meta"], 
            text_color=COLOR["inksubtle"]
        )
        self.count_label.pack(side="right")

        self.list_scroll = ctk.CTkScrollableFrame(list_card, fg_color=COLOR["surface"])
        self.list_scroll.pack(fill="both", expand=True, padx=PAD, pady=PAD)

    def _build_detail(self, parent):
        """病人詳細資料"""
        detail_card = Card(parent)
        detail_card.grid(row=1, column=1, sticky="nsew", padx=(self.COL_GAP // 2, PAD), pady=(GAP, PAD))

        self.detail_scroll = ctk.CTkScrollableFrame(detail_card, fg_color=COLOR["surface"])
        self.detail_scroll.pack(fill="both", expand=True, padx=PAD, pady=PAD)

        self._show_empty_detail()

    def _clear_search(self):
        """清除搜尋"""
        self.search_entry.delete(0, 'end')
        self._query_and_render()

    def _query_and_render(self):
        """查詢並渲染病人列表"""
        keyword = self.search_entry.get().strip()
        
        try:
            # 從後端獲取病人列表
            result = self.api_client.list_patients(keyword=keyword)
            
            if result and isinstance(result, (list, dict)):
                # 處理不同的回傳格式
                if isinstance(result, dict) and 'patients' in result:
                    self.all_patients = result['patients']
                elif isinstance(result, list):
                    self.all_patients = result
                else:
                    self.all_patients = []
                
                self._render_patient_list(self.all_patients)
            else:
                self.all_patients = []
                self._show_empty_list("無病患資料")
                
        except Exception as e:
            print(f"❌ 查詢病患失敗: {e}")
            self._show_empty_list(f"查詢失敗: {e}")

    def _render_patient_list(self, patients):
        """渲染病人列表"""
        # 清空現有列表
        for widget in self.list_scroll.winfo_children():
            widget.destroy()

        self.count_label.configure(text=f"共 {len(patients)} 筆病人")

        if not patients:
            self._show_empty_list("找不到符合條件的病患")
            return

        # 渲染每個病人卡片
        for patient in patients:
            self._create_patient_card(patient)

    def _create_patient_card(self, patient):
        """創建病人卡片"""
        card = ctk.CTkFrame(
            self.list_scroll,
            fg_color=COLOR["surfacealt"],
            corner_radius=12
        )
        card.pack(fill="x", pady=(0, 8))

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=PAD, pady=PAD)

        # 上方：姓名和性別
        top = ctk.CTkFrame(inner, fg_color="transparent")
        top.pack(fill="x", anchor="w")

        name = patient.get('name', '未知')
        gender_map = {'M': '👨 男', 'F': '👩 女', 'O': '⚧ 其他'}
        gender = gender_map.get(patient.get('gender', 'O'), '❓')

        ctk.CTkLabel(
            top,
            text=f"{name} ({gender})",
            font=FONT["h3"],
            text_color=COLOR["ink"],
            anchor="w"
        ).pack(side="left")

        # 中間：基本資訊
        info_items = [
            f"📋 MRN: {patient.get('mrn', '-')}",
            f"🎂 {patient.get('birthday', '-')}",
            f"🩸 {patient.get('blood_type', '-')}",
        ]

        for item in info_items:
            ctk.CTkLabel(
                inner,
                text=item,
                font=FONT["meta"],
                text_color=COLOR["inksubtle"],
                anchor="w"
            ).pack(anchor="w", pady=(2, 0))

        # 下方：操作按鈕
        bottom = ctk.CTkFrame(inner, fg_color="transparent")
        bottom.pack(fill="x", pady=(8, 0))

        OutlineBtn(
            bottom,
            "查看詳情",
            lambda p=patient: self._show_patient_detail(p),
            w=100,
            h=32
        ).pack(side="left")

    def _show_empty_list(self, message):
        """顯示空列表訊息"""
        for widget in self.list_scroll.winfo_children():
            widget.destroy()

        self.count_label.configure(text="共 0 筆病人")

        empty_frame = ctk.CTkFrame(
            self.list_scroll,
            fg_color=COLOR["surfacealt"],
            corner_radius=12
        )
        empty_frame.pack(fill="both", expand=True, pady=50)

        ctk.CTkLabel(
            empty_frame,
            text=f"📭 {message}",
            font=FONT["h2"],
            text_color=COLOR["muted"]
        ).pack(expand=True, pady=50)

    def _show_empty_detail(self):
        """顯示空詳細資料"""
        for widget in self.detail_scroll.winfo_children():
            widget.destroy()

        empty = ctk.CTkFrame(
            self.detail_scroll,
            fg_color=COLOR["surfacealt"],
            corner_radius=12
        )
        empty.pack(fill="both", expand=True, pady=50)

        ctk.CTkLabel(
            empty,
            text="👈 請選擇病人查看詳細資料",
            font=FONT["h2"],
            text_color=COLOR["muted"]
        ).pack(expand=True, pady=50)

    def _show_patient_detail(self, patient):
        """顯示病人詳細資料"""
        self.selected_patient = patient

        # 清空詳細資料區
        for widget in self.detail_scroll.winfo_children():
            widget.destroy()

        # 標題
        title_frame = ctk.CTkFrame(self.detail_scroll, fg_color="transparent")
        title_frame.pack(fill="x", pady=(0, GAP))

        ctk.CTkLabel(
            title_frame,
            text="病人資料",
            font=FONT["h1"],
            text_color=COLOR["ink"]
        ).pack(side="left")

        OutlineBtn(
            title_frame,
            "刪除病人",
            lambda: self._delete_patient(patient),
            w=100
        ).pack(side="right")

        # 基本資料卡片
        self._create_basic_info_card(patient)
        
        # 聯絡資料卡片
        self._create_contact_info_card(patient)
        
        # 醫療資料卡片
        self._create_medical_info_card(patient)
        
        # 影像記錄（初始顯示空白，點載入照片後才顯示）
        self._create_images_card(patient)

    def _create_basic_info_card(self, patient):
        """創建基本資料卡片"""
        basic_card = ctk.CTkFrame(
            self.detail_scroll,
            fg_color=COLOR["surfacealt"],
            corner_radius=12
        )
        basic_card.pack(fill="x", pady=(0, GAP))

        basic_inner = ctk.CTkFrame(basic_card, fg_color="transparent")
        basic_inner.pack(fill="x", padx=PAD, pady=PAD)

        ctk.CTkLabel(
            basic_inner,
            text="基本資料",
            font=FONT["h2"],
            text_color=COLOR["ink"]
        ).pack(anchor="w", pady=(0, 8))

        gender_map = {'M': '男性', 'F': '女性', 'O': '其他'}
        
        basic_info = [
            ("姓名", patient.get('name', '-')),
            ("病歷號 (MRN)", patient.get('mrn', '-')),
            ("病患 ID", patient.get('patient_id', '-')),
            ("身分證", patient.get('national_id', '-')),
            ("生日", patient.get('birthday', '-')),
            ("性別", gender_map.get(patient.get('gender', 'O'), '未知')),
            ("血型", patient.get('blood_type', '-')),
        ]

        for label, value in basic_info:
            self._create_info_row(basic_inner, label, value)

    def _create_contact_info_card(self, patient):
        """創建聯絡資料卡片"""
        contact_card = ctk.CTkFrame(
            self.detail_scroll,
            fg_color=COLOR["surfacealt"],
            corner_radius=12
        )
        contact_card.pack(fill="x", pady=(0, GAP))

        contact_inner = ctk.CTkFrame(contact_card, fg_color="transparent")
        contact_inner.pack(fill="x", padx=PAD, pady=PAD)

        ctk.CTkLabel(
            contact_inner,
            text="聯絡資訊",
            font=FONT["h2"],
            text_color=COLOR["ink"]
        ).pack(anchor="w", pady=(0, 8))

        contact_info = [
            ("電話", patient.get('phone', '-')),
            ("手機", patient.get('mobile', '-')),
            ("Email", patient.get('email', '-')),
            ("地址", patient.get('address', '-')),
            ("緊急聯絡人", patient.get('emergency_contact', '-')),
            ("緊急電話", patient.get('emergency_phone', '-')),
        ]

        for label, value in contact_info:
            self._create_info_row(contact_inner, label, value)

    def _create_medical_info_card(self, patient):
        """創建醫療資料卡片"""
        medical_card = ctk.CTkFrame(
            self.detail_scroll,
            fg_color=COLOR["surfacealt"],
            corner_radius=12
        )
        medical_card.pack(fill="x", pady=(0, GAP))

        medical_inner = ctk.CTkFrame(medical_card, fg_color="transparent")
        medical_inner.pack(fill="x", padx=PAD, pady=PAD)

        ctk.CTkLabel(
            medical_inner,
            text="醫療資訊",
            font=FONT["h2"],
            text_color=COLOR["ink"]
        ).pack(anchor="w", pady=(0, 8))

        medical_info = [
            ("主治醫師", patient.get('doctor_name', '-')),
            ("科別", patient.get('clinical_dept_name', '-')),
            ("保險 ID", patient.get('insurance_id', '-')),
            ("備註", patient.get('notes', '-')),
        ]

        for label, value in medical_info:
            self._create_info_row(medical_inner, label, value)

    def _create_images_card(self, patient):
        """創建影像記錄卡片"""
        images_card = ctk.CTkFrame(
            self.detail_scroll,
            fg_color=COLOR["surfacealt"],
            corner_radius=12
        )
        images_card.pack(fill="x", pady=(0, GAP))

        images_inner = ctk.CTkFrame(images_card, fg_color="transparent")
        images_inner.pack(fill="x", padx=PAD, pady=PAD)

        # 標題
        title_frame = ctk.CTkFrame(images_inner, fg_color="transparent")
        title_frame.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(
            title_frame,
            text="病患影像",
            font=FONT["h2"],
            text_color=COLOR["ink"]
        ).pack(side="left")

        SolidBtn(
            title_frame,
            "📥 載入照片",
            lambda: self._load_patient_images(patient),
            w=100,
            h=32
        ).pack(side="right")

        # 影像顯示區域（初始為空）
        self.images_frame = ctk.CTkFrame(images_inner, fg_color="transparent")
        self.images_frame.pack(fill="both", expand=True, pady=(8, 0))

        # 初始提示
        ctk.CTkLabel(
            self.images_frame,
            text="點擊「載入照片」按鈕查看病患影像",
            font=FONT["meta"],
            text_color=COLOR["inksubtle"]
        ).pack(pady=20)

    def _load_patient_images(self, patient):
        """載入病患影像（從後端請求）✨ 新功能"""
        if not self.images_frame:
            print("⚠️ 影像顯示區域尚未初始化")
            return

        # 清空現有內容
        for widget in self.images_frame.winfo_children():
            widget.destroy()

        # 顯示載入中
        loading_label = ctk.CTkLabel(
            self.images_frame,
            text="🔄 正在載入影像...",
            font=FONT["body"],
            text_color=COLOR["primary"]
        )
        loading_label.pack(pady=20)
        self.images_frame.update()

        try:
            patient_id = patient.get('id')
            
            # 獲取使用者的科別ID（如果有）
            clinical_dept_id = self.user.get('clinical_dept_id')
            
            # 從後端請求影像列表
            print(f"📥 請求病患 {patient_id} 的影像（科別: {clinical_dept_id}）")
            
            result = self.api_client.list_images(
                patient_id=patient_id,
                clinical_dept_id=clinical_dept_id,
                limit=12
            )
            
            # 清除載入中提示
            loading_label.destroy()
            
            if result and result.get('images'):
                images = result['images']
                
                # 顯示影像數量
                count_label = ctk.CTkLabel(
                    self.images_frame,
                    text=f"共 {len(images)} 筆影像記錄",
                    font=FONT["meta"],
                    text_color=COLOR["inksubtle"]
                )
                count_label.pack(anchor="w", pady=(0, 8))

                # 創建影像網格
                images_grid = ctk.CTkFrame(self.images_frame, fg_color="transparent")
                images_grid.pack(fill="both", expand=True)

                # 顯示每個影像（包含縮圖）
                for idx, img in enumerate(images):
                    self._create_image_card_with_thumbnail(images_grid, img, idx)
                    
                print(f"✅ 成功載入 {len(images)} 張影像")
            else:
                # 沒有影像
                ctk.CTkLabel(
                    self.images_frame,
                    text="📭 此病患尚無影像記錄",
                    font=FONT["body"],
                    text_color=COLOR["muted"]
                ).pack(pady=20)
                
        except Exception as e:
            # 清除載入中提示
            if loading_label.winfo_exists():
                loading_label.destroy()
                
            print(f"❌ 載入影像失敗: {e}")
            import traceback
            traceback.print_exc()
            
            ctk.CTkLabel(
                self.images_frame,
                text=f"❌ 載入影像失敗: {str(e)}",
                font=FONT["body"],
                text_color=COLOR["danger"]
            ).pack(pady=20)

    def _create_image_card_with_thumbnail(self, parent, image, index):
        """創建包含縮圖的影像卡片"""
        card = ctk.CTkFrame(
            parent,
            fg_color=COLOR["surface"],
            corner_radius=8
        )
        card.pack(fill="x", pady=4)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=8, pady=8)

        # 左側：縮圖
        try:
            image_id = image.get('id')
            
            # 嘗試從快取獲取縮圖
            if image_id in self.thumbnail_cache:
                thumbnail = self.thumbnail_cache[image_id]
            else:
                # 從後端獲取縮圖
                thumbnail_data = self.api_client.get_image_thumbnail(image_id)
                
                if thumbnail_data:
                    # 轉換為 PIL Image
                    pil_image = Image.open(BytesIO(thumbnail_data))
                    pil_image.thumbnail((80, 80))
                    
                    # 轉換為 CTkImage
                    thumbnail = ctk.CTkImage(
                        light_image=pil_image,
                        dark_image=pil_image,
                        size=(80, 80)
                    )
                    
                    # 存入快取
                    self.thumbnail_cache[image_id] = thumbnail
                else:
                    thumbnail = None
            
            if thumbnail:
                thumbnail_label = ctk.CTkLabel(
                    inner,
                    image=thumbnail,
                    text=""
                )
                thumbnail_label.pack(side="left", padx=(0, 12))
        except Exception as e:
            print(f"⚠️ 載入縮圖失敗: {e}")
            # 顯示預設圖示
            ctk.CTkLabel(
                inner,
                text="🖼️",
                font=("Arial", 40),
                width=80,
                height=80
            ).pack(side="left", padx=(0, 12))

        # 右側：影像資訊
        info_frame = ctk.CTkFrame(inner, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True)

        # 檔案名稱
        filename = image.get('filename', '未知')
        ctk.CTkLabel(
            info_frame,
            text=f"📁 {filename}",
            font=FONT["body"],
            text_color=COLOR["ink"],
            anchor="w"
        ).pack(anchor="w")

        # 檢查類型和科別
        modality = image.get('modality_dept_name', '-')
        clinical = image.get('clinical_dept_name', '-')
        
        ctk.CTkLabel(
            info_frame,
            text=f"📷 {modality} | 🏥 {clinical}",
            font=FONT["meta"],
            text_color=COLOR["inksubtle"],
            anchor="w"
        ).pack(anchor="w", pady=(2, 0))

        # 上傳時間和上傳者
        upload_date = image.get('uploaded_at', '-')
        uploader = image.get('uploader_name', '-')
        
        ctk.CTkLabel(
            info_frame,
            text=f"📅 {upload_date} | 👤 {uploader}",
            font=FONT["meta"],
            text_color=COLOR["inksubtle"],
            anchor="w"
        ).pack(anchor="w", pady=(2, 0))

        # 操作按鈕
        btn_frame = ctk.CTkFrame(inner, fg_color="transparent")
        btn_frame.pack(side="right")

        OutlineBtn(
            btn_frame,
            "查看",
            lambda: self._view_image(image),
            w=60,
            h=28
        ).pack()

    def _view_image(self, image):
        """查看完整影像 - 下載並用系統預設程式打開"""
        try:
            import tempfile
            import os
            import subprocess
            import platform
            
            # 從後端獲取完整影像
            print(f"📥 下載影像: {image.get('filename')}")
            
            image_data = self.api_client.get_image_full(image['id'])
            
            if not image_data:
                messagebox.showerror("錯誤", "無法獲取影像資料")
                return
            
            # 取得檔案副檔名
            filename = image.get('filename', 'image.jpg')
            ext = os.path.splitext(filename)[1] or '.jpg'
            
            # 建立臨時檔案
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp_file:
                tmp_file.write(image_data)
                tmp_path = tmp_file.name
            
            print(f"💾 臨時檔案: {tmp_path}")
            
            # 用系統預設程式打開
            system = platform.system()
            
            try:
                if system == 'Windows':
                    os.startfile(tmp_path)
                elif system == 'Darwin':  # macOS
                    subprocess.run(['open', tmp_path], check=True)
                else:  # Linux
                    subprocess.run(['xdg-open', tmp_path], check=True)
                
                print(f"✅ 已打開影像: {filename}")
                
                # 可選：提示使用者
                # messagebox.showinfo("提示", f"已在預設程式中打開:\n{filename}")
                
            except Exception as open_error:
                print(f"⚠️ 打開檔案失敗: {open_error}")
                # 備用方案：顯示檔案位置讓使用者手動打開
                messagebox.showinfo(
                    "影像已下載", 
                    f"影像已儲存至:\n{tmp_path}\n\n請手動開啟查看"
                )
            
        except Exception as e:
            print(f"❌ 打開影像失敗: {e}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("錯誤", f"打開影像失敗: {str(e)}")
    def _create_info_row(self, parent, label, value):
        """創建資訊列"""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=2)

        ctk.CTkLabel(
            row,
            text=f"{label}:",
            font=FONT["body"],
            text_color=COLOR["inksubtle"],
            width=120,
            anchor="w"
        ).pack(side="left")

        ctk.CTkLabel(
            row,
            text=value or "-",
            font=FONT["body"],
            text_color=COLOR["ink"],
            anchor="w"
        ).pack(side="left", fill="x", expand=True)

    def _delete_patient(self, patient):
        """刪除病人"""
        if not messagebox.askyesno(
            "確認刪除",
            f"確定要刪除病患「{patient.get('name', '未知')}」嗎？\n\n此操作無法復原！"
        ):
            return

        try:
            result = self.api_client.delete_patient(patient['id'])
            
            if result and result.get('status') == 'success':
                messagebox.showinfo("成功", "病患已刪除")
                self._query_and_render()
                self._show_empty_detail()
            else:
                messagebox.showerror("錯誤", "刪除失敗")
        except Exception as e:
            messagebox.showerror("錯誤", f"刪除失敗: {e}")

    def _show_add_patient_dialog(self):
        """顯示新增病人對話框"""
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("新增病人")
        dialog.geometry("600x800")
        dialog.transient(self.root)
        dialog.grab_set()

        # 主容器
        main_frame = ctk.CTkScrollableFrame(dialog, fg_color=COLOR["bg"])
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(
            main_frame,
            text="新增病人",
            font=FONT["h1"],
            text_color=COLOR["ink"]
        ).pack(anchor="w", pady=(0, 20))

        # 欄位
        fields = {}

        # 基本資料
        self._add_section_title(main_frame, "基本資料")
        
        fields['name'] = self._add_field(main_frame, "姓名 *", required=True)
        fields['mrn'] = self._add_field(main_frame, "病歷號 (MRN) *", required=True)
        fields['patient_id'] = self._add_field(main_frame, "病患 ID *", required=True)
        fields['national_id'] = self._add_field(main_frame, "身分證字號")
        fields['birthday'] = self._add_field(main_frame, "生日 (YYYY-MM-DD) *", required=True)
        
        # 性別
        gender_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        gender_frame.pack(fill="x", pady=4)
        ctk.CTkLabel(gender_frame, text="性別 *:", font=FONT["body"], width=120, anchor="w").pack(side="left")
        fields['gender'] = ctk.StringVar(value="M")
        gender_menu = ctk.CTkOptionMenu(
            gender_frame, 
            variable=fields['gender'],
            values=["M", "F", "O"],
            width=200
        )
        gender_menu.pack(side="left")

        fields['blood_type'] = self._add_field(main_frame, "血型")

        # 聯絡資訊
        self._add_section_title(main_frame, "聯絡資訊")
        
        fields['phone'] = self._add_field(main_frame, "電話")
        fields['mobile'] = self._add_field(main_frame, "手機")
        fields['email'] = self._add_field(main_frame, "Email")
        fields['address'] = self._add_field(main_frame, "地址")
        fields['emergency_contact'] = self._add_field(main_frame, "緊急聯絡人")
        fields['emergency_phone'] = self._add_field(main_frame, "緊急電話")

        # 醫療資訊
        self._add_section_title(main_frame, "醫療資訊")
        
        fields['insurance_id'] = self._add_field(main_frame, "保險 ID")
        fields['notes'] = self._add_field(main_frame, "備註", multiline=True)

        # 按鈕
        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.pack(fill="x", pady=(20, 0))

        SolidBtn(
            button_frame,
            "確認新增",
            lambda: self._save_new_patient(fields, dialog),
            w=120
        ).pack(side="right", padx=(8, 0))

        OutlineBtn(
            button_frame,
            "取消",
            dialog.destroy,
            w=100
        ).pack(side="right")

    def _add_section_title(self, parent, title):
        """添加區段標題"""
        ctk.CTkLabel(
            parent,
            text=title,
            font=FONT["h2"],
            text_color=COLOR["ink"]
        ).pack(anchor="w", pady=(16, 8))

    def _add_field(self, parent, label, required=False, multiline=False):
        """添加欄位"""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=4)

        label_text = f"{label}:" if not required else f"{label}:"
        ctk.CTkLabel(
            row, 
            text=label_text, 
            font=FONT["body"], 
            width=120, 
            anchor="w"
        ).pack(side="left")

        if multiline:
            entry = ctk.CTkTextbox(row, height=80, font=FONT["body"])
        else:
            entry = ctk.CTkEntry(row, height=36, font=FONT["body"])
        
        entry.pack(side="left", fill="x", expand=True)

        return entry

    def _save_new_patient(self, fields, dialog):
        """儲存新病人"""
        try:
            # 收集資料
            patient_data = {
                'name': fields['name'].get().strip(),
                'mrn': fields['mrn'].get().strip(),
                'patient_id': fields['patient_id'].get().strip(),
                'national_id': fields['national_id'].get().strip(),
                'birthday': fields['birthday'].get().strip(),
                'gender': fields['gender'].get(),
                'blood_type': fields['blood_type'].get().strip(),
                'phone': fields['phone'].get().strip(),
                'mobile': fields['mobile'].get().strip(),
                'email': fields['email'].get().strip(),
                'address': fields['address'].get().strip(),
                'emergency_contact': fields['emergency_contact'].get().strip(),
                'emergency_phone': fields['emergency_phone'].get().strip(),
                'insurance_id': fields['insurance_id'].get().strip(),
                'notes': fields['notes'].get("1.0", "end-1c").strip() if hasattr(fields['notes'], 'get') else '',
            }

            # 驗證必填欄位
            required = ['name', 'mrn', 'patient_id', 'birthday']
            for field in required:
                if not patient_data.get(field):
                    messagebox.showerror("錯誤", f"請填寫 {field}")
                    return

            # 呼叫 API 新增
            result = self.api_client.add_patient(patient_data)

            if result and result.get('status') == 'success':
                messagebox.showinfo("成功", "病患新增成功")
                dialog.destroy()
                self._query_and_render()
            else:
                error_msg = result.get('message', '新增失敗') if result else '新增失敗'
                messagebox.showerror("錯誤", error_msg)

        except Exception as e:
            messagebox.showerror("錯誤", f"新增失敗: {e}")
            import traceback
            traceback.print_exc()