# -*- coding: utf-8 -*-
"""
patients_tab.py - 病人清單（自適應多欄 + 權限新增）
- 左側清單依視窗寬度自動 1~3 欄
- 針對目前 DB 欄位：
    id, name, birthday, bloodtype, mrn, nationalid, gender, phone, created_at
- 只有 admin / nurse（含「管理員」「護士」字樣）能看到右上角「＋ 新增病人」
"""

import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox

# 樣式（從 config 載入；沒有就給預設）
try:
    from GuiUser.config import COLOR, FONT, PAD, GAP, Card, OutlineBtn
except Exception:
    COLOR = {
        "bg": "#F5F7FB", "surface": "#FFFFFF", "surfacealt": "#EAEFF8",
        "primary": "#3b82f6", "chip": "#E8EEF9",
        "success": "#16a34a", "danger": "#ef4444", "muted": "#94a3b8"
    }
    FONT = {
        "logo": ("PingFang TC", 18, "bold"),
        "meta": ("PingFang TC", 12),
        "body": ("PingFang TC", 14),
        "h1": ("PingFang TC", 20, "bold"),
        "tag": ("PingFang TC", 12, "bold"),
    }
    PAD, GAP = 12, 12
    class Card(ctk.CTkFrame):
        def __init__(self, master, **kw):
            super().__init__(master, fg_color=COLOR["surface"], corner_radius=12)
    class OutlineBtn(ctk.CTkButton):
        def __init__(self, master, text, command, w=96, h=36, **kw):
            super().__init__(master, text=text, command=command, width=w, height=h,
                             fg_color="transparent", border_width=1, border_color=COLOR["primary"],
                             text_color=COLOR["primary"])

from .database import connect_db


class PatientsTab:
    MIN_CARD_W = 360   # 卡片目標寬度
    COL_GAP = 12       # 卡片欄間距

    def __init__(self, parent, user=None, root=None):
        self.parent = parent
        self.root = root or parent
        self.user = user or {"username": "User", "role": "guest"}

        # 外層：左清單 + 右詳情
        parent.grid_rowconfigure(1, weight=1)
        parent.grid_columnconfigure(0, weight=2)
        parent.grid_columnconfigure(1, weight=3)

        self._build_search(parent)
        self._build_list(parent)
        self._build_detail(parent)

        # 快捷鍵（admin/nurse）
        role = (self.user or {}).get("role")
        if role in ("admin", "nurse", "管理員", "護士"):
            try:
                self.root.bind("<Command-n>", lambda e: self._open_add_dialog())  # macOS
            except Exception:
                pass
            self.root.bind("<Control-n>", lambda e: self._open_add_dialog())      # Win/Linux

        self._query_and_render()

    # ---------------- 上方搜尋列 ----------------
    def _build_search(self, parent):
        bar = Card(parent); bar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=PAD, pady=(PAD, 0))
        inner = ctk.CTkFrame(bar, fg_color=COLOR["surface"]); inner.pack(fill="x", padx=PAD, pady=PAD)

        # 左側：搜尋輸入
        left = ctk.CTkFrame(inner, fg_color="transparent"); left.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(left, text="🔎 搜尋：", font=FONT["body"]).pack(side="left", padx=(0, 6))
        self.qvar = tk.StringVar()
        self.qentry = ctk.CTkEntry(left, textvariable=self.qvar, height=40)
        self.qentry.pack(side="left", fill="x", expand=True)
        self.qentry.bind("<Return>", lambda e: self._query_and_render())

        # 右側：功能鍵
        right = ctk.CTkFrame(inner, fg_color="transparent"); right.pack(side="right")
        OutlineBtn(right, "搜尋", self._query_and_render, w=80, h=40).pack(side="left", padx=(8, 0))

        role = (self.user or {}).get("role")
        if role in ("admin", "nurse", "管理員", "護士"):
            OutlineBtn(right, "＋ 新增病人", self._open_add_dialog, w=110, h=40).pack(side="left", padx=(8, 0))

    # ---------------- 左側清單（自適應多欄） ----------------
    def _build_list(self, parent):
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

    # ---------------- 右側詳情 ----------------
    def _build_detail(self, parent):
        self.detail = Card(parent)
        self.detail.grid(row=1, column=1, sticky="nsew", padx=(0, PAD), pady=(PAD, PAD))
        guide = ctk.CTkLabel(self.detail, text="請從左側選擇病人查看詳情",
                             font=FONT["body"], text_color=COLOR.get("muted", "#94a3b8"))
        guide.place(relx=0.5, rely=0.5, anchor="center")

    # ---------------- 捲動 / 版面 ----------------
    def _on_inner_cfg(self, _evt=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_cfg(self, evt):
        self.canvas.itemconfig(self.inner_id, width=evt.width)
        self._relayout_cards(evt.width)

    def _relayout_cards(self, available_w):
        if available_w <= 0:
            return
        gutter = self.COL_GAP
        cols = max(1, min(3, int((available_w + gutter) / (self.MIN_CARD_W + gutter))))
        col_w = (available_w - gutter * (cols - 1)) // cols
        for c in range(cols):
            self.inner.grid_columnconfigure(c, weight=1, uniform="cards")
        for i, card in enumerate(self.cards):
            r, c = divmod(i, cols)
            card.grid(row=r, column=c, sticky="nsew",
                      padx=(0 if c == 0 else gutter, 0), pady=(0, gutter))
            card.configure(width=col_w)

    # ---------------- 讀取與渲染 ----------------
    def _query_and_render(self):
        kw_raw = self.qvar.get().strip()
        kw = f"%{kw_raw}%" if kw_raw else "%"
        try:
            con = connect_db()
            cur = con.cursor()
            # 針對目前表：bloodtype → AS blood_type；沒有 updated_at → 用 created_at / id
            sql = """
                SELECT
                    id,
                    name,
                    mrn,
                    birthday,
                    bloodtype AS blood_type
                FROM patients
                WHERE (name LIKE ? OR mrn LIKE ?)
                ORDER BY COALESCE(created_at, id) DESC
                LIMIT 500
            """
            cur.execute(sql, (kw, kw))
            rows = cur.fetchall()
            headers = [d[0] for d in cur.description]
            self.rows = [dict(zip(headers, r)) for r in rows]
            con.close()
        except Exception as e:
            messagebox.showerror("資料庫錯誤", str(e))
            self.rows = []

        # 清空舊卡
        for w in self.inner.winfo_children():
            w.destroy()
        self.cards.clear()

        if not self.rows:
            empty = ctk.CTkLabel(self.inner, text="沒有找到病人資料",
                                 font=FONT["body"], text_color=COLOR.get("muted", "#94a3b8"))
            empty.grid(row=0, column=0, sticky="w", pady=GAP)
            self.inner.update_idletasks()
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            return

        # 卡片
        for row in self.rows:
            card = Card(self.inner)
            card.pack_propagate(False)
            box = ctk.CTkFrame(card, fg_color=COLOR["surface"])
            box.pack(fill="both", expand=True, padx=PAD, pady=PAD)

            title = f"{row.get('name','—')} (MRN:{row.get('mrn','—')})"
            ctk.CTkLabel(box, text=title, font=FONT["body"]).pack(anchor="w")

            sub = ctk.CTkFrame(box, fg_color="transparent"); sub.pack(anchor="w", pady=(6, 0))
            bday  = (row.get("birthday") or "—").split(" ")[0]
            btype = row.get("blood_type") or "—"
            ctk.CTkLabel(sub, text=f"🎂 {bday}   🩸 {btype}",
                         font=FONT["meta"], text_color=COLOR.get("muted", "#64748b")).pack(side="left")

            def _mk_show_detail(pid=row.get("id")):
                return lambda: self._show_detail(pid)
            OutlineBtn(box, "詳情", _mk_show_detail(), w=96, h=34).pack(anchor="w", pady=(10, 0))

            self.cards.append(card)

        # 依目前寬度排一次
        self.inner.update_idletasks()
        self._relayout_cards(self.canvas.winfo_width() or self.inner.winfo_width())

    # ---------------- 詳情 ----------------
    def _show_detail(self, pid):
        for w in self.detail.winfo_children():
            w.destroy()
        wrap = ctk.CTkFrame(self.detail, fg_color=COLOR["surface"])
        wrap.pack(fill="both", expand=True, padx=PAD, pady=PAD)

        try:
            con = connect_db(); cur = con.cursor()
            sql = """
                SELECT
                    id, name, mrn, gender, birthday,
                    bloodtype AS blood_type,
                    nationalid, phone, created_at
                FROM patients
                WHERE id=?
            """
            cur.execute(sql, (pid,))
            row = cur.fetchone()
            headers = [d[0] for d in cur.description]
            data = dict(zip(headers, row)) if row else {}
            con.close()
        except Exception as e:
            ctk.CTkLabel(wrap, text=f"讀取詳情失敗：{e}", font=FONT["body"], text_color=COLOR["danger"]).pack(pady=PAD)
            return

        ctk.CTkLabel(wrap, text="病人資料", font=FONT["h1"]).pack(anchor="w")
        info = ctk.CTkFrame(wrap, fg_color="transparent"); info.pack(fill="x", pady=(8, 0))

        fields = [
            ("name","姓名"),("mrn","MRN"),("gender","性別"),("birthday","生日"),
            ("blood_type","血型"),("nationalid","身分證"),("phone","電話"),("created_at","建立時間")
        ]
        for key, label in fields:
            line = ctk.CTkFrame(info, fg_color="transparent"); line.pack(fill="x", pady=4)
            ctk.CTkLabel(line, width=88, text=label, font=FONT["body"],
                         text_color=COLOR.get("muted", "#64748b")).pack(side="left")
            ctk.CTkLabel(line, text=str((data.get(key) or "—")), font=FONT["body"]).pack(side="left")

    # ---------------- 新增病人（admin/nurse） ----------------
    def _open_add_dialog(self):
        role = (self.user or {}).get("role")
        if role not in ("admin", "nurse", "管理員", "護士"):
            return

        win = ctk.CTkToplevel(self.root)
        win.title("新增病人")
        win.geometry("520x420")
        win.transient(self.root); win.grab_set()

        # 內容外框
        frame = ctk.CTkFrame(win, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=18, pady=18)
        # 用 grid 做整齊欄位：兩欄（標籤、輸入）
        frame.grid_columnconfigure(0, weight=0, minsize=88)
        frame.grid_columnconfigure(1, weight=1)

        def L(r, text):
            ctk.CTkLabel(frame, text=text, anchor="w").grid(row=r, column=0, sticky="w", pady=6, padx=(0,12))

        # 欄位
        self._e_name       = ctk.CTkEntry(frame, placeholder_text="必填")
        self._e_mrn        = ctk.CTkEntry(frame, placeholder_text="必填")
        self._e_birthday   = ctk.CTkEntry(frame, placeholder_text="YYYY-MM-DD")
        self._e_gender     = ctk.CTkOptionMenu(frame, values=["", "M", "F"])
        self._e_bloodtype  = ctk.CTkOptionMenu(frame, values=["", "A", "B", "AB", "O"])
        self._e_nationalid = ctk.CTkEntry(frame, placeholder_text="")
        self._e_phone      = ctk.CTkEntry(frame, placeholder_text="")

        r = 0
        L(r, "姓名 *");      self._e_name.grid(     row=r, column=1, sticky="ew", pady=6); r+=1
        L(r, "MRN *");       self._e_mrn.grid(      row=r, column=1, sticky="ew", pady=6); r+=1
        L(r, "生日");        self._e_birthday.grid( row=r, column=1, sticky="ew", pady=6); r+=1
        L(r, "性別");        self._e_gender.grid(   row=r, column=1, sticky="ew", pady=6); r+=1
        L(r, "血型");        self._e_bloodtype.grid(row=r, column=1, sticky="ew", pady=6); r+=1
        L(r, "身分證");      self._e_nationalid.grid(row=r, column=1, sticky="ew", pady=6); r+=1
        L(r, "電話");        self._e_phone.grid(    row=r, column=1, sticky="ew", pady=6); r+=1

        # 按鈕列
        btns = ctk.CTkFrame(frame, fg_color="transparent")
        btns.grid(row=r, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ctk.CTkButton(btns, text="取消", command=win.destroy).pack(side="right")
        ctk.CTkButton(btns, text="新增",
                      command=lambda: self._create_patient_and_close(win)).pack(side="right", padx=(8,0))

    def _create_patient_and_close(self, win):
        name = self._e_name.get().strip()
        mrn  = self._e_mrn.get().strip()
        if not name or not mrn:
            messagebox.showwarning("缺少必填", "姓名與 MRN 必填")
            return

        birthday   = self._e_birthday.get().strip() or None
        gender     = self._e_gender.get().strip() or None
        bloodtype  = self._e_bloodtype.get().strip() or None
        nationalid = self._e_nationalid.get().strip() or None
        phone      = self._e_phone.get().strip() or None

        try:
            con = connect_db(); cur = con.cursor()
            # MRN 唯一性（避免重複）
            cur.execute("SELECT 1 FROM patients WHERE mrn=?", (mrn,))
            if cur.fetchone():
                con.close()
                messagebox.showwarning("重複 MRN", f"MRN「{mrn}」已存在")
                return

            cur.execute("""
                INSERT INTO patients (name, birthday, bloodtype, mrn, nationalid, gender, phone, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (name, birthday, bloodtype, mrn, nationalid, gender, phone))
            con.commit(); con.close()
        except Exception as e:
            messagebox.showerror("寫入失敗", str(e))
            return

        try: win.destroy()
        except: pass
        self._query_and_render()
        messagebox.showinfo("成功", f"已新增：{name}（MRN:{mrn}）")
