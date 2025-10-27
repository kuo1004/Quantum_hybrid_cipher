# -*- coding: utf-8 -*-
"""
patients_tab.py - 病人管理（透過 API 獲取影像）
"""

import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox
from PIL import Image, ImageTk
from io import BytesIO
import base64
from .config import COLOR, FONT, PAD, GAP, Card, OutlineBtn
from .api_client import get_api_client


class PatientsTab:
    """病人管理標籤頁（透過 API 獲取影像）"""
    MIN_CARD_W = 360
    COL_GAP = 12

    def __init__(self, parent, user=None, root=None):
        self.parent = parent
        self.root = root or parent
        self.user = user or {"username": "User", "role": "guest"}
        self.api_client = get_api_client()
        
        # 快取縮圖
        self.thumbnail_cache = {}

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
        
        ctk.CTkLabel(left, text="🔎 搜尋：", font=FONT["body"]).pack(side="left", padx=(0, 6))
        
        self.qvar = tk.StringVar()
        self.qentry = ctk.CTkEntry(left, textvariable=self.qvar, height=40)
        self.qentry.pack(side="left", fill="x", expand=True)
        self.qentry.bind("<Return>", lambda e: self._query_and_render())

        right = ctk.CTkFrame(inner, fg_color="transparent")
        right.pack(side="right")
        
        OutlineBtn(right, "搜尋", self._query_and_render, w=80, h=40).pack(side="left", padx=(8, 0))

        role = self.user.get("role")
        if role in ("admin", "nurse"):
            OutlineBtn(right, "＋ 新增病人", self._open_add_dialog, w=110, h=40).pack(side="left", padx=(8, 0))

    def _build_list(self, parent):
        """病人列表"""
        wrap = ctk.CTkFrame(parent, fg_color="transparent")
        wrap.grid(row=1, column=0, sticky="nsew", padx=PAD, pady=(PAD, PAD))
        wrap.grid_rowconfigure(0, weight=1)
        wrap.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(wrap, highlightthickness=0, bg=COLOR["bg"])
        self.canvas.grid(row=0, column=0, sticky="nsew")
        
        vbar = ctk.CTkScrollbar(wrap, command=self.canvas.yview)
        vbar.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=vbar.set)

        self.inner = ctk.CTkFrame(self.canvas, fg_color=COLOR["bg"])
        self.inner_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")

        self.inner.bind("<Configure>", self._on_inner_cfg)
        self.canvas.bind("<Configure>", self._on_canvas_cfg)

        self.rows, self.cards = [], []

    def _build_detail(self, parent):
        """詳情面板"""
        self.detail = Card(parent)
        self.detail.grid(row=1, column=1, sticky="nsew", padx=(0, PAD), pady=(PAD, PAD))
        
        guide = ctk.CTkLabel(
            self.detail, 
            text="請從左側選擇病人查看詳情",
            font=FONT["body"], 
            text_color=COLOR.get("muted", "#94a3b8")
        )
        guide.place(relx=0.5, rely=0.5, anchor="center")

    def _on_inner_cfg(self, _evt=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_cfg(self, evt):
        self.canvas.itemconfig(self.inner_id, width=evt.width)
        self._relayout_cards(evt.width)

    def _relayout_cards(self, available_w):
        """重新排列卡片"""
        if available_w <= 0:
            return
        
        gutter = self.COL_GAP
        cols = max(1, min(3, int((available_w + gutter) / (self.MIN_CARD_W + gutter))))
        col_w = (available_w - gutter * (cols - 1)) // cols
        
        for c in range(cols):
            self.inner.grid_columnconfigure(c, weight=1, uniform="cards")
        
        for i, card in enumerate(self.cards):
            r, c = divmod(i, cols)
            card.grid(
                row=r, column=c, sticky="nsew",
                padx=(0 if c == 0 else gutter, 0), 
                pady=(0, gutter)
            )
            card.configure(width=col_w)

    def _query_and_render(self):
        """查詢並渲染（從後端）"""
        keyword = self.qvar.get().strip()
        
        try:
            # 從後端獲取病患列表
            patients = self.api_client.list_patients(keyword=keyword)
            self.rows = patients
            
        except Exception as e:
            messagebox.showerror("錯誤", f"載入病患列表失敗: {e}")
            self.rows = []

        # 清空舊卡片
        for w in self.inner.winfo_children():
            w.destroy()
        self.cards.clear()

        if not self.rows:
            empty = ctk.CTkLabel(
                self.inner, 
                text="沒有找到病人資料",
                font=FONT["body"], 
                text_color=COLOR.get("muted", "#94a3b8")
            )
            empty.grid(row=0, column=0, sticky="w", pady=GAP)
            self.inner.update_idletasks()
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            return

        # 創建卡片
        for row in self.rows:
            card = Card(self.inner)
            card.pack_propagate(False)
            
            box = ctk.CTkFrame(card, fg_color=COLOR["surface"])
            box.pack(fill="both", expand=True, padx=PAD, pady=PAD)

            title = f"{row.get('name','—')} (MRN:{row.get('mrn','—')})"
            ctk.CTkLabel(box, text=title, font=FONT["body"]).pack(anchor="w")

            sub = ctk.CTkFrame(box, fg_color="transparent")
            sub.pack(anchor="w", pady=(6, 0))
            
            bday = (row.get("birthday") or "—").split(" ")[0]
            btype = row.get("blood_type") or "—"
            
            ctk.CTkLabel(
                sub, 
                text=f"🎂 {bday}   🩸 {btype}",
                font=FONT["meta"], 
                text_color=COLOR.get("muted", "#64748b")
            ).pack(side="left")

            def _mk_show_detail(pid=row.get("id")):
                return lambda: self._show_detail(pid)
            
            OutlineBtn(box, "詳情", _mk_show_detail(), w=96, h=34).pack(anchor="w", pady=(10, 0))

            self.cards.append(card)

        self.inner.update_idletasks()
        self._relayout_cards(self.canvas.winfo_width() or self.inner.winfo_width())

    def _show_detail(self, pid):
        """顯示詳情（從後端）+ 載入照片按鈕"""
        for w in self.detail.winfo_children():
            w.destroy()
        
        wrap = ctk.CTkScrollableFrame(self.detail, fg_color=COLOR["surface"])
        wrap.pack(fill="both", expand=True, padx=PAD, pady=PAD)

        try:
            # 從後端獲取病患詳情
            patient = self.api_client.get_patient(pid)
            
            if not patient:
                ctk.CTkLabel(
                    wrap, 
                    text="找不到病患資料", 
                    font=FONT["body"], 
                    text_color=COLOR["danger"]
                ).pack(pady=PAD)
                return
            
        except Exception as e:
            ctk.CTkLabel(
                wrap, 
                text=f"讀取詳情失敗：{e}", 
                font=FONT["body"], 
                text_color=COLOR["danger"]
            ).pack(pady=PAD)
            return

        # 標題
        ctk.CTkLabel(wrap, text="病人資料", font=FONT["h1"]).pack(anchor="w", pady=(0, 8))
        
        # 病患資訊
        info = ctk.CTkFrame(wrap, fg_color="transparent")
        info.pack(fill="x", pady=(0, 12))

        fields = [
            ("name", "姓名"),
            ("mrn", "MRN"),
            ("gender", "性別"),
            ("birthday", "生日"),
            ("blood_type", "血型"),
            ("nationalid", "身份證"),
            ("phone", "電話"),
            ("created_at", "建立時間")
        ]
        
        for key, label in fields:
            line = ctk.CTkFrame(info, fg_color="transparent")
            line.pack(fill="x", pady=4)
            
            ctk.CTkLabel(
                line, 
                width=88, 
                text=label, 
                font=FONT["body"],
                text_color=COLOR.get("muted", "#64748b")
            ).pack(side="left")
            
            value = str(patient.get(key) or "—")
            if key == "gender":
                value = {"M": "男", "F": "女"}.get(value, value)
            
            ctk.CTkLabel(
                line, 
                text=value, 
                font=FONT["body"]
            ).pack(side="left")

        # 分隔線
        separator = ctk.CTkFrame(wrap, fg_color=COLOR.get("muted", "#94a3b8"), height=1)
        separator.pack(fill="x", pady=12)

        # 載入照片按鈕
        ctk.CTkButton(
            wrap,
            text="📷 載入此病人的所有照片",
            command=lambda: self._load_patient_images(pid, patient),
            font=FONT["body"],
            height=44,
            fg_color=COLOR.get("primary", "#3b82f6"),
            hover_color="#2563eb"
        ).pack(fill="x", pady=(0, 8))

        # 只有管理員可以刪除
        role = self.user.get("role", "")
        if role == "admin":
            ctk.CTkButton(
                wrap,
                text="🗑️ 刪除此病人",
                command=lambda: self._delete_patient(pid),
                font=FONT["body"],
                height=44,
                fg_color=COLOR.get("danger", "#ef4444"),
                hover_color="#dc2626"
            ).pack(fill="x", pady=(0, 8))

    def _load_patient_images(self, patient_id, patient_info):
        """載入病人的所有照片（透過 API）- 修正版"""
        # 清空詳情面板
        for w in self.detail.winfo_children():
            w.destroy()
        
        # 創建新的顯示區域
        wrap = ctk.CTkScrollableFrame(self.detail, fg_color=COLOR["surface"])
        wrap.pack(fill="both", expand=True, padx=PAD, pady=PAD)

        # 標題
        patient_name = patient_info.get('name', '未知')
        patient_mrn = patient_info.get('mrn', '-')
        
        title_frame = ctk.CTkFrame(wrap, fg_color="transparent")
        title_frame.pack(fill="x", pady=(0, 12))
        
        ctk.CTkLabel(
            title_frame,
            text=f"📷 {patient_name} (MRN:{patient_mrn}) 的照片",
            font=FONT["h1"]
        ).pack(side="left")
        
        OutlineBtn(
            title_frame,
            "← 返回",
            lambda: self._show_detail(patient_id),
            w=80,
            h=36
        ).pack(side="right")

        # 顯示載入中
        loading_label = ctk.CTkLabel(
            wrap,
            text="⏳ 正在從 Hospital Server 載入照片...",
            font=FONT["body"],
            text_color=COLOR.get("primary", "#3b82f6")
        )
        loading_label.pack(pady=20)

        # 強制更新 UI
        wrap.update()

        try:
            # ⭐⭐⭐ 關鍵修正：使用 get_patient_images 而不是 list_images ⭐⭐⭐
            print(f"📡 請求病患影像: patient_id={patient_id}")
            
            # 舊的（錯誤）：
            # result = self.api_client.list_images(patient_id=patient_id)
            
            # 新的（正確）：使用新 API，會自動包含縮圖
            result = self.api_client.get_patient_images(patient_id=patient_id, include_thumbnails=True)
            
            # 移除載入中標籤
            loading_label.destroy()
            
            # ⭐ 修正：檢查回傳格式
            if not result or result.get('status') != 'success':
                error_msg = result.get('message', '未知錯誤') if result else '無回應'
                ctk.CTkLabel(
                    wrap,
                    text=f"載入失敗：{error_msg}",
                    font=FONT["h2"],
                    text_color=COLOR.get("danger", "#ef4444")
                ).pack(pady=50)
                return
            
            images = result.get('images', [])
            
            if not images:
                ctk.CTkLabel(
                    wrap,
                    text="此病人尚無照片",
                    font=FONT["h2"],
                    text_color=COLOR.get("muted", "#94a3b8")
                ).pack(pady=50)
                return
            
            total = len(images)
            
            # 顯示統計
            stats_text = f"共找到 {total} 張照片（來自 Hospital Server）"
            ctk.CTkLabel(
                wrap,
                text=stats_text,
                font=FONT["body"],
                text_color=COLOR.get("primary", "#3b82f6")
            ).pack(anchor="w", pady=(0, 12))
            
            # 顯示每張照片（會自動載入縮圖，因為 API 已經回傳）
            for img in images:
                self._create_image_card_with_thumbnail(wrap, img, patient_id)
            
        except Exception as e:
            loading_label.destroy()
            messagebox.showerror("錯誤", f"載入照片失敗：{e}")
            import traceback
            traceback.print_exc()


    def _create_image_card_with_thumbnail(self, parent, img_data, patient_id):
        """
        創建影像卡片（縮圖已在 API 回傳中）
        
        ⭐ 關鍵：不需要異步載入，因為縮圖已經在 img_data['thumbnail'] 中
        """
        card = ctk.CTkFrame(
            parent,
            fg_color=COLOR.get("surfacealt", "#f1f5f9"),
            corner_radius=12
        )
        card.pack(fill="x", pady=(0, 8))
        
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=PAD, pady=PAD)
        
        # 左側：縮圖區域
        left = ctk.CTkFrame(inner, fg_color="transparent")
        left.pack(side="left", padx=(0, 12))
        
        # ⭐⭐⭐ 關鍵修正：直接從 API 回傳的資料解碼縮圖 ⭐⭐⭐
        thumbnail_b64 = img_data.get('thumbnail')
        
        if thumbnail_b64:
            try:
                # Base64 解碼
                thumbnail_bytes = base64.b64decode(thumbnail_b64)
                
                # 轉換為 PIL Image
                img = Image.open(BytesIO(thumbnail_bytes))
                img.thumbnail((80, 80), Image.Resampling.LANCZOS)
                
                # 轉換為 PhotoImage
                photo = ImageTk.PhotoImage(img)
                
                # 顯示縮圖
                thumbnail_label = ctk.CTkLabel(left, image=photo, text="")
                thumbnail_label.image = photo  # 保持引用
                thumbnail_label.pack()
                
                print(f"✅ 縮圖顯示成功: image_id={img_data['id']}")
                
            except Exception as e:
                print(f"❌ 縮圖解碼失敗: {e}")
                # 顯示錯誤圖示
                ctk.CTkLabel(
                    left,
                    text="❌",
                    font=("Arial", 48),
                    width=80,
                    height=80
                ).pack()
        else:
            # 沒有縮圖，顯示佔位圖示
            ctk.CTkLabel(
                left,
                text="🖼️",
                font=("Arial", 48),
                width=80,
                height=80
            ).pack()
        
        # 中間：資訊
        middle = ctk.CTkFrame(inner, fg_color="transparent")
        middle.pack(side="left", fill="both", expand=True)
        
        # 檔名
        filename = img_data.get('filename', '未知檔案')
        title_text = f"🌐 {filename}"
        ctk.CTkLabel(
            middle,
            text=title_text,
            font=FONT["h3"],
            anchor="w"
        ).pack(anchor="w")
        
        # 上傳時間
        uploaded_at = img_data.get('uploaded_at', '未知')
        time_text = f"📅 上傳時間: {uploaded_at}"
        ctk.CTkLabel(
            middle,
            text=time_text,
            font=FONT["meta"],
            text_color=COLOR.get("muted", "#64748b"),
            anchor="w"
        ).pack(anchor="w", pady=(4, 0))
        
        # ID
        image_id = img_data['id']
        id_text = f"🔖 影像 ID: {image_id}"
        ctk.CTkLabel(
            middle,
            text=id_text,
            font=FONT["meta"],
            text_color=COLOR.get("muted", "#64748b"),
            anchor="w"
        ).pack(anchor="w", pady=(2, 0))
        
        # 右側：操作按鈕
        right = ctk.CTkFrame(inner, fg_color="transparent")
        right.pack(side="right")
        
        OutlineBtn(
            right,
            "👁️ 查看",
            lambda: self._view_image(image_id, filename),
            w=100,
            h=36
        ).pack()

    def _load_thumbnail_async(self, image_id, label_widget):
        """異步載入縮圖"""
        def load():
            try:
                # 檢查快取
                if image_id in self.thumbnail_cache:
                    photo = self.thumbnail_cache[image_id]
                    label_widget.configure(image=photo, text="")
                    label_widget.image = photo
                    return
                
                # 從 API 獲取縮圖
                print(f"📥 載入縮圖: image_id={image_id}")
                thumbnail_bytes = self.api_client.get_image_thumbnail(image_id)
                
                if thumbnail_bytes:
                    # 轉換為 PIL Image
                    img = Image.open(BytesIO(thumbnail_bytes))
                    img.thumbnail((80, 80), Image.Resampling.LANCZOS)
                    
                    # 轉換為 PhotoImage
                    photo = ImageTk.PhotoImage(img)
                    
                    # 儲存到快取
                    self.thumbnail_cache[image_id] = photo
                    
                    # 更新 UI
                    label_widget.configure(image=photo, text="")
                    label_widget.image = photo
                    
                    print(f"✅ 縮圖載入成功: image_id={image_id}")
                else:
                    # 載入失敗，顯示圖示
                    label_widget.configure(text="🖼️")
                    print(f"⚠️ 縮圖載入失敗: image_id={image_id}")
                    
            except Exception as e:
                print(f"❌ 載入縮圖錯誤: {e}")
                label_widget.configure(text="❌")
        
        # 在背景執行
        self.root.after(100, load)

    def _view_image(self, image_id, filename):
        """查看完整影像（透過 API）"""
        try:
            # 顯示載入中
            loading_win = ctk.CTkToplevel(self.root)
            loading_win.title("載入中...")
            loading_win.geometry("300x100")
            loading_win.transient(self.root)
            
            ctk.CTkLabel(
                loading_win,
                text="⏳ 正在載入完整影像...",
                font=FONT["body"]
            ).pack(expand=True)
            
            loading_win.update()
            
            # 從 API 獲取完整影像
            print(f"📥 載入完整影像: image_id={image_id}")
            result = self.api_client.get_image_full(image_id)
            
            # 關閉載入視窗
            loading_win.destroy()
            
            if not result or result.get('status') != 'success':
                messagebox.showerror("錯誤", "無法載入影像")
                return
            
            # 解碼影像
            image_b64 = result.get('image_data')
            mime = result.get('mime', 'image/jpeg')
            
            if not image_b64:
                messagebox.showerror("錯誤", "影像資料為空")
                return
            
            image_bytes = base64.b64decode(image_b64)
            
            # 顯示影像視窗
            view_window = ctk.CTkToplevel(self.root)
            view_window.title(f"影像檢視 - {filename}")
            view_window.geometry("800x900")
            
            # 頂部資訊
            info_frame = ctk.CTkFrame(view_window, fg_color=COLOR["surface"])
            info_frame.pack(fill="x", padx=20, pady=20)
            
            info_text = (
                f"📁 檔名: {filename}\n"
                f"🔖 影像 ID: {image_id}\n"
                f"📦 MIME: {mime}\n"
                f"💾 檔案大小: {len(image_bytes) / 1024 / 1024:.2f} MB"
            )
            
            ctk.CTkLabel(
                info_frame,
                text=info_text,
                font=FONT["body"],
                justify="left"
            ).pack(padx=20, pady=20)
            
            # 影像顯示區域
            image_frame = ctk.CTkScrollableFrame(view_window, fg_color=COLOR["bg"])
            image_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
            
            # 載入並顯示影像
            img = Image.open(BytesIO(image_bytes))
            img.thumbnail((750, 750), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            
            image_label = ctk.CTkLabel(image_frame, image=photo, text="")
            image_label.image = photo
            image_label.pack(pady=20)
            
            print(f"✅ 完整影像顯示成功: {filename}")
            
        except Exception as e:
            messagebox.showerror("錯誤", f"無法開啟影像: {e}")
            import traceback
            traceback.print_exc()

    def _delete_patient(self, pid):
        """刪除病人（只有管理員）"""
        role = self.user.get("role", "")
        if role != "admin":
            messagebox.showwarning("權限不足", "只有管理員可以刪除病人")
            return
        
        # 確認對話框
        if not messagebox.askyesno(
            "確認刪除",
            f"確定要刪除病人 ID {pid} 嗎？\n\n此操作無法復原！"
        ):
            return
        
        try:
            result = self.api_client.delete_patient(pid)
            
            if result and result.get('status') == 'success':
                messagebox.showinfo("成功", "病人已刪除")
                self._query_and_render()
                
                # 清空詳情面板
                for w in self.detail.winfo_children():
                    w.destroy()
                
                guide = ctk.CTkLabel(
                    self.detail, 
                    text="請從左側選擇病人查看詳情",
                    font=FONT["body"], 
                    text_color=COLOR.get("muted", "#94a3b8")
                )
                guide.place(relx=0.5, rely=0.5, anchor="center")
            else:
                error_msg = result.get('message', '刪除失敗') if result else '刪除失敗'
                messagebox.showerror("失敗", error_msg)
                
        except Exception as e:
            messagebox.showerror("錯誤", f"刪除失敗: {e}")

    def _open_add_dialog(self):
        """新增病人對話框"""
        role = self.user.get("role")
        if role not in ("admin", "nurse"):
            return

        win = ctk.CTkToplevel(self.root)
        win.title("新增病人")
        win.geometry("520x420")
        win.transient(self.root)
        win.grab_set()

        frame = ctk.CTkFrame(win, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=18, pady=18)
        frame.grid_columnconfigure(0, weight=0, minsize=88)
        frame.grid_columnconfigure(1, weight=1)

        def L(r, text):
            ctk.CTkLabel(frame, text=text, anchor="w").grid(
                row=r, column=0, sticky="w", pady=6, padx=(0, 12)
            )

        self._e_name = ctk.CTkEntry(frame, placeholder_text="必填")
        self._e_mrn = ctk.CTkEntry(frame, placeholder_text="必填")
        self._e_birthday = ctk.CTkEntry(frame, placeholder_text="YYYY-MM-DD")
        self._e_gender = ctk.CTkOptionMenu(frame, values=["", "M", "F"])
        self._e_bloodtype = ctk.CTkOptionMenu(frame, values=["", "A", "B", "AB", "O"])
        self._e_nationalid = ctk.CTkEntry(frame, placeholder_text="")
        self._e_phone = ctk.CTkEntry(frame, placeholder_text="")

        r = 0
        L(r, "姓名 *"); self._e_name.grid(row=r, column=1, sticky="ew", pady=6); r += 1
        L(r, "MRN *"); self._e_mrn.grid(row=r, column=1, sticky="ew", pady=6); r += 1
        L(r, "生日"); self._e_birthday.grid(row=r, column=1, sticky="ew", pady=6); r += 1
        L(r, "性別"); self._e_gender.grid(row=r, column=1, sticky="ew", pady=6); r += 1
        L(r, "血型"); self._e_bloodtype.grid(row=r, column=1, sticky="ew", pady=6); r += 1
        L(r, "身份證"); self._e_nationalid.grid(row=r, column=1, sticky="ew", pady=6); r += 1
        L(r, "電話"); self._e_phone.grid(row=r, column=1, sticky="ew", pady=6); r += 1

        btns = ctk.CTkFrame(frame, fg_color="transparent")
        btns.grid(row=r, column=0, columnspan=2, sticky="e", pady=(12, 0))
        
        ctk.CTkButton(btns, text="取消", command=win.destroy).pack(side="right")
        ctk.CTkButton(
            btns, 
            text="新增",
            command=lambda: self._create_patient_and_close(win)
        ).pack(side="right", padx=(8, 0))

    def _create_patient_and_close(self, win):
        """創建病患（透過後端）"""
        name = self._e_name.get().strip()
        mrn = self._e_mrn.get().strip()
        
        if not name or not mrn:
            messagebox.showwarning("缺少必填", "姓名與 MRN 必填")
            return

        patient_data = {
            "name": name,
            "mrn": mrn,
            "birthday": self._e_birthday.get().strip() or None,
            "gender": self._e_gender.get().strip() or None,
            "blood_type": self._e_bloodtype.get().strip() or None,
            "nationalid": self._e_nationalid.get().strip() or None,
            "phone": self._e_phone.get().strip() or None
        }

        try:
            result = self.api_client.create_patient(patient_data)
            
            if result and result.get('status') == 'success':
                win.destroy()
                self._query_and_render()
                messagebox.showinfo("成功", f"已新增：{name}（MRN:{mrn}）")
            else:
                error_msg = result.get('message', '創建失敗') if result else '創建失敗'
                messagebox.showerror("失敗", error_msg)
                
        except Exception as e:
            messagebox.showerror("錯誤", f"創建失敗: {e}")