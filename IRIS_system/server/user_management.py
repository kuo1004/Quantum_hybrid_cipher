#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IRIS 使用者管理系統
用於新增、編輯、刪除使用者的圖形化介面
"""

import os
import sys
import sqlite3
from datetime import datetime
import customtkinter as ctk
from tkinter import messagebox, ttk
import tkinter as tk


class UserManagementApp:
    """IRIS 使用者管理介面"""
    
    def __init__(self, db_path: str = "IRIS_database.db"):
        self.db_path = db_path
        
        # 檢查資料庫是否存在
        if not os.path.exists(db_path):
            messagebox.showerror("錯誤", f"找不到資料庫: {db_path}")
            sys.exit(1)
        
        # 設定外觀
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
        
        # 建立主視窗
        self.root = ctk.CTk()
        self.root.title("IRIS 使用者管理系統")
        self.root.geometry("1100x700")
        self.root.minsize(900, 600)
        
        # 顏色主題
        self.colors = {
            "primary": "#2563eb",
            "success": "#16a34a",
            "danger": "#dc2626",
            "warning": "#d97706",
            "bg": "#f8fafc",
            "card": "#ffffff",
            "text": "#1e293b",
            "text_light": "#64748b",
            "border": "#e2e8f0"
        }
        
        # 載入資料
        self.roles = self._load_roles()
        self.departments = self._load_departments()
        
        # 建立介面
        self._setup_ui()
        
        # 載入使用者列表
        self._refresh_user_list()
    
    def _connect_db(self):
        """連接資料庫"""
        return sqlite3.connect(self.db_path)
    
    def _load_roles(self) -> dict:
        """載入角色列表"""
        conn = self._connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, code, name FROM roles")
        roles = {row[0]: {"code": row[1], "name": row[2]} for row in cursor.fetchall()}
        conn.close()
        return roles
    
    def _load_departments(self) -> dict:
        """載入科別列表"""
        conn = self._connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, code, name FROM clinical_departments")
        depts = {row[0]: {"code": row[1], "name": row[2]} for row in cursor.fetchall()}
        conn.close()
        return depts
    
    def _setup_ui(self):
        """建立使用者介面"""
        self.root.configure(fg_color=self.colors["bg"])
        
        # 主容器
        main = ctk.CTkFrame(self.root, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=20, pady=20)
        
        # 標題
        header = ctk.CTkFrame(main, fg_color="transparent")
        header.pack(fill="x", pady=(0, 20))
        
        ctk.CTkLabel(
            header, text="👥 IRIS 使用者管理系統",
            font=("Microsoft JhengHei", 24, "bold"),
            text_color=self.colors["primary"]
        ).pack(side="left")
        
        ctk.CTkLabel(
            header, text=f"資料庫: {self.db_path}",
            font=("Arial", 12),
            text_color=self.colors["text_light"]
        ).pack(side="right")
        
        # 內容區域
        content = ctk.CTkFrame(main, fg_color="transparent")
        content.pack(fill="both", expand=True)
        
        # 左側：使用者列表
        left_panel = ctk.CTkFrame(content, fg_color=self.colors["card"], corner_radius=12)
        left_panel.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        self._create_user_list_panel(left_panel)
        
        # 右側：表單
        right_panel = ctk.CTkFrame(content, fg_color=self.colors["card"], corner_radius=12, width=400)
        right_panel.pack(side="right", fill="y")
        right_panel.pack_propagate(False)
        
        self._create_form_panel(right_panel)
    
    def _create_user_list_panel(self, parent):
        """建立使用者列表面板"""
        # 標題列
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.pack(fill="x", padx=15, pady=15)
        
        ctk.CTkLabel(
            header, text="📋 使用者列表",
            font=("Microsoft JhengHei", 16, "bold"),
            text_color=self.colors["text"]
        ).pack(side="left")
        
        # 重新整理按鈕
        ctk.CTkButton(
            header, text="🔄 重新整理", width=100,
            command=self._refresh_user_list,
            fg_color=self.colors["text_light"],
            hover_color="#475569"
        ).pack(side="right")
        
        # 搜尋列
        search_frame = ctk.CTkFrame(parent, fg_color="transparent")
        search_frame.pack(fill="x", padx=15, pady=(0, 10))
        
        self.search_var = ctk.StringVar()
        self.search_var.trace("w", lambda *args: self._filter_users())
        
        ctk.CTkEntry(
            search_frame, 
            textvariable=self.search_var,
            placeholder_text="🔍 搜尋使用者名稱或姓名...",
            height=36
        ).pack(fill="x")
        
        # 使用者列表（使用 Treeview）
        list_frame = ctk.CTkFrame(parent, fg_color="transparent")
        list_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        
        # 設定 Treeview 樣式
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", 
                       font=("Microsoft JhengHei", 11),
                       rowheight=35,
                       background="white",
                       fieldbackground="white")
        style.configure("Treeview.Heading", 
                       font=("Microsoft JhengHei", 11, "bold"),
                       background="#f1f5f9",
                       foreground="#334155")
        style.map("Treeview", background=[("selected", "#dbeafe")])
        
        # 建立 Treeview
        columns = ("id", "username", "full_name", "role", "department", "status")
        self.user_tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="browse")
        
        # 設定欄位
        self.user_tree.heading("id", text="ID")
        self.user_tree.heading("username", text="帳號")
        self.user_tree.heading("full_name", text="姓名")
        self.user_tree.heading("role", text="角色")
        self.user_tree.heading("department", text="科別")
        self.user_tree.heading("status", text="狀態")
        
        self.user_tree.column("id", width=50, anchor="center")
        self.user_tree.column("username", width=100)
        self.user_tree.column("full_name", width=100)
        self.user_tree.column("role", width=100)
        self.user_tree.column("department", width=100)
        self.user_tree.column("status", width=70, anchor="center")
        
        # 捲軸
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.user_tree.yview)
        self.user_tree.configure(yscrollcommand=scrollbar.set)
        
        self.user_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # 綁定選取事件
        self.user_tree.bind("<<TreeviewSelect>>", self._on_user_select)
    
    def _create_form_panel(self, parent):
        """建立表單面板"""
        # 標題
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=20)
        
        self.form_title = ctk.CTkLabel(
            header, text="➕ 新增使用者",
            font=("Microsoft JhengHei", 16, "bold"),
            text_color=self.colors["text"]
        )
        self.form_title.pack(side="left")
        
        # 表單內容
        form = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        
        # 帳號
        ctk.CTkLabel(form, text="帳號 *", font=("Microsoft JhengHei", 12),
                     text_color=self.colors["text"]).pack(anchor="w", pady=(0, 5))
        self.username_entry = ctk.CTkEntry(form, height=38, placeholder_text="輸入帳號")
        self.username_entry.pack(fill="x", pady=(0, 15))
        
        # 密碼
        ctk.CTkLabel(form, text="密碼 *", font=("Microsoft JhengHei", 12),
                     text_color=self.colors["text"]).pack(anchor="w", pady=(0, 5))
        self.password_entry = ctk.CTkEntry(form, height=38, placeholder_text="輸入密碼", show="●")
        self.password_entry.pack(fill="x", pady=(0, 15))
        
        # 姓名
        ctk.CTkLabel(form, text="姓名", font=("Microsoft JhengHei", 12),
                     text_color=self.colors["text"]).pack(anchor="w", pady=(0, 5))
        self.fullname_entry = ctk.CTkEntry(form, height=38, placeholder_text="輸入姓名")
        self.fullname_entry.pack(fill="x", pady=(0, 15))
        
        # Email
        ctk.CTkLabel(form, text="Email", font=("Microsoft JhengHei", 12),
                     text_color=self.colors["text"]).pack(anchor="w", pady=(0, 5))
        self.email_entry = ctk.CTkEntry(form, height=38, placeholder_text="輸入 Email")
        self.email_entry.pack(fill="x", pady=(0, 15))
        
        # 電話
        ctk.CTkLabel(form, text="電話", font=("Microsoft JhengHei", 12),
                     text_color=self.colors["text"]).pack(anchor="w", pady=(0, 5))
        self.phone_entry = ctk.CTkEntry(form, height=38, placeholder_text="輸入電話")
        self.phone_entry.pack(fill="x", pady=(0, 15))
        
        # 員工編號
        ctk.CTkLabel(form, text="員工編號", font=("Microsoft JhengHei", 12),
                     text_color=self.colors["text"]).pack(anchor="w", pady=(0, 5))
        self.employee_id_entry = ctk.CTkEntry(form, height=38, placeholder_text="輸入員工編號")
        self.employee_id_entry.pack(fill="x", pady=(0, 15))
        
        # 角色
        ctk.CTkLabel(form, text="角色 *", font=("Microsoft JhengHei", 12),
                     text_color=self.colors["text"]).pack(anchor="w", pady=(0, 5))
        role_values = [f"{r['name']} ({r['code']})" for r in self.roles.values()]
        self.role_combo = ctk.CTkComboBox(form, values=role_values, height=38, state="readonly")
        self.role_combo.pack(fill="x", pady=(0, 15))
        self.role_combo.set(role_values[0] if role_values else "")
        
        # 科別
        ctk.CTkLabel(form, text="所屬科別", font=("Microsoft JhengHei", 12),
                     text_color=self.colors["text"]).pack(anchor="w", pady=(0, 5))
        dept_values = ["(無)"] + [f"{d['name']} ({d['code']})" for d in self.departments.values()]
        self.dept_combo = ctk.CTkComboBox(form, values=dept_values, height=38, state="readonly")
        self.dept_combo.pack(fill="x", pady=(0, 15))
        self.dept_combo.set("(無)")
        
        # 啟用狀態
        self.is_active_var = ctk.BooleanVar(value=True)
        self.active_check = ctk.CTkCheckBox(
            form, text="啟用帳號", variable=self.is_active_var,
            font=("Microsoft JhengHei", 12)
        )
        self.active_check.pack(anchor="w", pady=(0, 20))
        
        # 按鈕區域
        btn_frame = ctk.CTkFrame(parent, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(0, 20))
        
        # 新增/更新按鈕
        self.save_btn = ctk.CTkButton(
            btn_frame, text="💾 新增使用者", height=40,
            font=("Microsoft JhengHei", 13, "bold"),
            fg_color=self.colors["success"],
            hover_color="#15803d",
            command=self._save_user
        )
        self.save_btn.pack(fill="x", pady=(0, 10))
        
        # 刪除按鈕
        self.delete_btn = ctk.CTkButton(
            btn_frame, text="🗑️ 刪除使用者", height=40,
            font=("Microsoft JhengHei", 13, "bold"),
            fg_color=self.colors["danger"],
            hover_color="#b91c1c",
            command=self._delete_user
        )
        self.delete_btn.pack(fill="x", pady=(0, 10))
        
        # 清除按鈕
        ctk.CTkButton(
            btn_frame, text="🔄 清除表單", height=40,
            font=("Microsoft JhengHei", 13),
            fg_color=self.colors["text_light"],
            hover_color="#475569",
            command=self._clear_form
        ).pack(fill="x")
        
        # 目前選取的使用者 ID
        self.selected_user_id = None
    
    def _refresh_user_list(self):
        """重新載入使用者列表"""
        # 清空列表
        for item in self.user_tree.get_children():
            self.user_tree.delete(item)
        
        # 載入使用者
        conn = self._connect_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.id, u.username, u.full_name, u.role_id, u.clinical_dept_id, u.is_active
            FROM users u
            ORDER BY u.id
        """)
        
        for row in cursor.fetchall():
            user_id, username, full_name, role_id, dept_id, is_active = row
            
            role_name = self.roles.get(role_id, {}).get("name", "未知")
            dept_name = self.departments.get(dept_id, {}).get("name", "-") if dept_id else "-"
            status = "✅ 啟用" if is_active else "❌ 停用"
            
            self.user_tree.insert("", "end", values=(
                user_id, username, full_name or "-", role_name, dept_name, status
            ))
        
        conn.close()
    
    def _filter_users(self):
        """篩選使用者"""
        search_text = self.search_var.get().lower()
        
        for item in self.user_tree.get_children():
            values = self.user_tree.item(item, "values")
            username = str(values[1]).lower()
            full_name = str(values[2]).lower()
            
            if search_text in username or search_text in full_name:
                self.user_tree.reattach(item, "", "end")
            else:
                self.user_tree.detach(item)
    
    def _on_user_select(self, event):
        """選取使用者時載入資料到表單"""
        selection = self.user_tree.selection()
        if not selection:
            return
        
        item = selection[0]
        values = self.user_tree.item(item, "values")
        user_id = int(values[0])
        
        # 載入完整使用者資料
        conn = self._connect_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, username, password, full_name, email, phone, 
                   role_id, clinical_dept_id, employee_id, is_active
            FROM users WHERE id = ?
        """, (user_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            self.selected_user_id = row[0]
            
            # 填入表單
            self.username_entry.delete(0, "end")
            self.username_entry.insert(0, row[1])
            
            self.password_entry.delete(0, "end")
            self.password_entry.insert(0, row[2])
            
            self.fullname_entry.delete(0, "end")
            self.fullname_entry.insert(0, row[3] or "")
            
            self.email_entry.delete(0, "end")
            self.email_entry.insert(0, row[4] or "")
            
            self.phone_entry.delete(0, "end")
            self.phone_entry.insert(0, row[5] or "")
            
            self.employee_id_entry.delete(0, "end")
            self.employee_id_entry.insert(0, row[8] or "")
            
            # 設定角色
            role_id = row[6]
            if role_id in self.roles:
                role_text = f"{self.roles[role_id]['name']} ({self.roles[role_id]['code']})"
                self.role_combo.set(role_text)
            
            # 設定科別
            dept_id = row[7]
            if dept_id and dept_id in self.departments:
                dept_text = f"{self.departments[dept_id]['name']} ({self.departments[dept_id]['code']})"
                self.dept_combo.set(dept_text)
            else:
                self.dept_combo.set("(無)")
            
            # 設定啟用狀態
            self.is_active_var.set(bool(row[9]))
            
            # 更新按鈕文字
            self.form_title.configure(text=f"✏️ 編輯使用者 (ID: {user_id})")
            self.save_btn.configure(text="💾 更新使用者")
    
    def _clear_form(self):
        """清除表單"""
        self.selected_user_id = None
        
        self.username_entry.delete(0, "end")
        self.password_entry.delete(0, "end")
        self.fullname_entry.delete(0, "end")
        self.email_entry.delete(0, "end")
        self.phone_entry.delete(0, "end")
        self.employee_id_entry.delete(0, "end")
        
        role_values = [f"{r['name']} ({r['code']})" for r in self.roles.values()]
        if role_values:
            self.role_combo.set(role_values[0])
        
        self.dept_combo.set("(無)")
        self.is_active_var.set(True)
        
        self.form_title.configure(text="➕ 新增使用者")
        self.save_btn.configure(text="💾 新增使用者")
        
        # 取消選取
        for item in self.user_tree.selection():
            self.user_tree.selection_remove(item)
    
    def _get_role_id_from_combo(self) -> int:
        """從下拉選單取得角色 ID"""
        text = self.role_combo.get()
        for role_id, role_info in self.roles.items():
            if f"{role_info['name']} ({role_info['code']})" == text:
                return role_id
        return 1  # 預設 admin
    
    def _get_dept_id_from_combo(self):
        """從下拉選單取得科別 ID"""
        text = self.dept_combo.get()
        if text == "(無)":
            return None
        for dept_id, dept_info in self.departments.items():
            if f"{dept_info['name']} ({dept_info['code']})" == text:
                return dept_id
        return None
    
    def _save_user(self):
        """儲存使用者"""
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()
        full_name = self.fullname_entry.get().strip() or None
        email = self.email_entry.get().strip() or None
        phone = self.phone_entry.get().strip() or None
        employee_id = self.employee_id_entry.get().strip() or None
        role_id = self._get_role_id_from_combo()
        dept_id = self._get_dept_id_from_combo()
        is_active = self.is_active_var.get()
        
        # 驗證
        if not username:
            messagebox.showerror("錯誤", "請輸入帳號")
            return
        
        if not password:
            messagebox.showerror("錯誤", "請輸入密碼")
            return
        
        conn = self._connect_db()
        cursor = conn.cursor()
        
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            if self.selected_user_id:
                # 更新
                cursor.execute("""
                    UPDATE users SET
                        username = ?, password = ?, full_name = ?, email = ?,
                        phone = ?, role_id = ?, clinical_dept_id = ?,
                        employee_id = ?, is_active = ?, updated_at = ?
                    WHERE id = ?
                """, (username, password, full_name, email, phone, role_id,
                      dept_id, employee_id, is_active, now, self.selected_user_id))
                
                conn.commit()
                messagebox.showinfo("成功", f"使用者 {username} 已更新")
            else:
                # 檢查帳號是否重複
                cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
                if cursor.fetchone():
                    messagebox.showerror("錯誤", f"帳號 {username} 已存在")
                    return
                
                # 新增
                cursor.execute("""
                    INSERT INTO users (username, password, full_name, email, phone,
                                       role_id, clinical_dept_id, employee_id, is_active,
                                       created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (username, password, full_name, email, phone, role_id,
                      dept_id, employee_id, is_active, now, now))
                
                conn.commit()
                messagebox.showinfo("成功", f"使用者 {username} 已新增")
            
            self._clear_form()
            self._refresh_user_list()
            
        except Exception as e:
            messagebox.showerror("錯誤", f"儲存失敗: {e}")
        finally:
            conn.close()
    
    def _delete_user(self):
        """刪除使用者"""
        if not self.selected_user_id:
            messagebox.showwarning("警告", "請先選取要刪除的使用者")
            return
        
        username = self.username_entry.get()
        
        if not messagebox.askyesno("確認刪除", f"確定要刪除使用者 {username} 嗎？\n此操作無法復原！"):
            return
        
        conn = self._connect_db()
        cursor = conn.cursor()
        
        try:
            cursor.execute("DELETE FROM users WHERE id = ?", (self.selected_user_id,))
            conn.commit()
            
            messagebox.showinfo("成功", f"使用者 {username} 已刪除")
            self._clear_form()
            self._refresh_user_list()
            
        except Exception as e:
            messagebox.showerror("錯誤", f"刪除失敗: {e}")
        finally:
            conn.close()
    
    def run(self):
        """啟動應用程式"""
        self.root.mainloop()


def main():
    """主程式入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="IRIS 使用者管理系統")
    parser.add_argument("--db", default="IRIS_database.db", help="資料庫路徑")
    args = parser.parse_args()
    
    app = UserManagementApp(db_path=args.db)
    app.run()


if __name__ == "__main__":
    main()