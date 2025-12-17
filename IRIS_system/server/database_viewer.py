#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
database_viewer.py - Medical System 資料庫檢視器

功能：
- 瀏覽所有資料表
- 查看資料表結構
- 查詢資料
- 檢視影像和縮圖
- 匯出資料為 CSV
- 執行自訂 SQL 查詢
"""

import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk
import io
import csv
from datetime import datetime

class DatabaseViewer:
    def __init__(self, db_path=None):

        import os
        
        # 如果沒有指定路徑，自動搜尋
        if db_path is None:
            possible_paths = [
                "IRIS_database.db",      
                "IRIS_database.db",
                "../IRIS_database.db",
            ]
            
            best_db = None
            max_size = 0
            
            for path in possible_paths:
                if os.path.exists(path):
                    size = os.path.getsize(path)
                    print(f"✅ 找到: {path} ({size} bytes)")
                    
                    # 選擇檔案最大的（通常有最多資料）
                    if size > max_size:
                        max_size = size
                        best_db = path
            
            if best_db:
                db_path = best_db
                print(f"🎯 使用: {db_path}")
            else:
                print(f"⚠️ 找不到資料庫，將使用: .medical_system.db")
                db_path = ".medical_system.db"
        
        self.db_path = db_path
        self.conn = None
        self.current_table = None
        
        # 建立主視窗
        self.root = tk.Tk()
        self.root.title(f"資料庫檢視器 - {db_path}")
        self.root.geometry("1200x700")
        
        self.setup_ui()
        self.connect_database()
        
    def connect_database(self):
        """連接資料庫"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            
            # 檢查資料庫內容
            cursor = self.conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            
            # 統計資料數量
            total_records = 0
            for table in tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
                    count = cursor.fetchone()[0]
                    total_records += count
                except:
                    pass
            
            status_msg = f"✅ 已連接: {self.db_path} | {len(tables)} 個表格 | {total_records} 筆資料"
            
            if total_records == 0:
                status_msg += " ⚠️ (空的)"
                print("⚠️ 警告: 資料庫是空的")
                print("💡 提示: 檢查是否有其他資料庫檔案")
            
            self.status_label.config(text=status_msg, fg="green" if total_records > 0 else "orange")
            self.load_tables()
            
        except sqlite3.Error as e:
            messagebox.showerror("連接錯誤", f"無法連接資料庫: {e}")
            self.status_label.config(text="❌ 連接失敗", fg="red")
    
    def setup_ui(self):
        """建立使用者介面"""
        # 頂部工具列
        toolbar = tk.Frame(self.root, bg="#f0f0f0", height=50)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        tk.Button(toolbar, text="🔄 重新整理", command=self.refresh, 
                 bg="#4CAF50", fg="white", padx=10).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="📊 資料庫統計", command=self.show_statistics,
                 bg="#2196F3", fg="white", padx=10).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="📤 匯出 CSV", command=self.export_csv,
                 bg="#FF9800", fg="white", padx=10).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="🔍 SQL 查詢", command=self.show_sql_query,
                 bg="#9C27B0", fg="white", padx=10).pack(side=tk.LEFT, padx=2)
        
        # 狀態列
        self.status_label = tk.Label(self.root, text="準備就緒", 
                                     bg="#f0f0f0", anchor=tk.W, padx=10)
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)
        
        # 主要區域：左側表格列表 + 右側資料顯示
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 左側面板：表格列表
        left_panel = tk.Frame(main_frame, width=200, bg="white")
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))
        
        tk.Label(left_panel, text="📋 資料表", bg="white", 
                font=("Arial", 12, "bold")).pack(pady=5)
        
        # 表格列表框
        self.table_listbox = tk.Listbox(left_panel, font=("Arial", 10))
        self.table_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.table_listbox.bind('<<ListboxSelect>>', self.on_table_select)
        
        # 右側面板：分頁介面
        right_panel = tk.Frame(main_frame)
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 建立分頁
        self.notebook = ttk.Notebook(right_panel)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # 分頁1：資料內容
        self.data_frame = tk.Frame(self.notebook)
        self.notebook.add(self.data_frame, text="📊 資料內容")
        
        # 搜尋框
        search_frame = tk.Frame(self.data_frame)
        search_frame.pack(fill=tk.X, padx=5, pady=5)
        
        tk.Label(search_frame, text="🔍 搜尋:").pack(side=tk.LEFT, padx=5)
        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(search_frame, textvariable=self.search_var)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        tk.Button(search_frame, text="搜尋", command=self.search_data).pack(side=tk.LEFT, padx=5)
        
        # 資料表格
        data_table_frame = tk.Frame(self.data_frame)
        data_table_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 滾動條
        scrollbar_y = tk.Scrollbar(data_table_frame)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        
        scrollbar_x = tk.Scrollbar(data_table_frame, orient=tk.HORIZONTAL)
        scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Treeview 表格
        self.tree = ttk.Treeview(data_table_frame, 
                                yscrollcommand=scrollbar_y.set,
                                xscrollcommand=scrollbar_x.set)
        self.tree.pack(fill=tk.BOTH, expand=True)
        
        scrollbar_y.config(command=self.tree.yview)
        scrollbar_x.config(command=self.tree.xview)
        
        # 雙擊事件：查看詳細資料
        self.tree.bind('<Double-Button-1>', self.show_detail)
        
        # 分頁2：表格結構
        self.structure_frame = tk.Frame(self.notebook)
        self.notebook.add(self.structure_frame, text="🏗️ 表格結構")
        
        structure_text_frame = tk.Frame(self.structure_frame)
        structure_text_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        structure_scrollbar = tk.Scrollbar(structure_text_frame)
        structure_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.structure_text = tk.Text(structure_text_frame, wrap=tk.WORD,
                                     yscrollcommand=structure_scrollbar.set,
                                     font=("Courier", 10))
        self.structure_text.pack(fill=tk.BOTH, expand=True)
        structure_scrollbar.config(command=self.structure_text.yview)
    
    def load_tables(self):
        """載入所有表格名稱"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' 
            ORDER BY name
            """)
            
            tables = cursor.fetchall()
            
            self.table_listbox.delete(0, tk.END)
            for table in tables:
                self.table_listbox.insert(tk.END, table[0])
            
            self.status_label.config(text=f"✅ 找到 {len(tables)} 個資料表")
            
        except sqlite3.Error as e:
            messagebox.showerror("錯誤", f"載入表格失敗: {e}")
    
    def on_table_select(self, event):
        """選擇表格時的處理"""
        selection = self.table_listbox.curselection()
        if selection:
            table_name = self.table_listbox.get(selection[0])
            self.current_table = table_name
            self.load_table_data(table_name)
            self.load_table_structure(table_name)
    
    def load_table_data(self, table_name):
        """載入表格資料"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(f"SELECT * FROM {table_name}")
            
            rows = cursor.fetchall()
            columns = [description[0] for description in cursor.description]
            
            # 清空現有資料
            self.tree.delete(*self.tree.get_children())
            
            # 設定欄位
            self.tree['columns'] = columns
            self.tree['show'] = 'headings'
            
            # 設定欄位標題
            for col in columns:
                self.tree.heading(col, text=col, command=lambda c=col: self.sort_by_column(c))
                
                # 根據欄位名稱設定寬度
                if col in ['id']:
                    width = 50
                elif col in ['imagedata', 'thumbdata', 'original_data', 'thumbnail']:
                    width = 80
                elif col in ['created_at', 'uploaded_at', 'timestamp']:
                    width = 150
                else:
                    width = 120
                
                self.tree.column(col, width=width, minwidth=50)
            
            # 插入資料
            for row in rows:
                values = []
                for i, value in enumerate(row):
                    # 處理 BLOB 資料
                    if isinstance(value, bytes):
                        values.append(f"<BLOB: {len(value)} bytes>")
                    elif value is None:
                        values.append("<NULL>")
                    else:
                        values.append(str(value))
                
                self.tree.insert('', tk.END, values=values)
            
            self.status_label.config(text=f"✅ {table_name}: {len(rows)} 筆資料")
            
        except sqlite3.Error as e:
            messagebox.showerror("錯誤", f"載入資料失敗: {e}")
    
    def load_table_structure(self, table_name):
        """載入表格結構"""
        try:
            cursor = self.conn.cursor()
            
            # 取得表格建立語句
            cursor.execute(f"""
            SELECT sql FROM sqlite_master 
            WHERE type='table' AND name='{table_name}'
            """)
            
            create_sql = cursor.fetchone()[0]
            
            # 取得欄位資訊
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            
            # 取得索引資訊
            cursor.execute(f"PRAGMA index_list({table_name})")
            indexes = cursor.fetchall()
            
            # 取得外鍵資訊
            cursor.execute(f"PRAGMA foreign_key_list({table_name})")
            foreign_keys = cursor.fetchall()
            
            # 顯示結構資訊
            self.structure_text.delete(1.0, tk.END)
            
            self.structure_text.insert(tk.END, "=== 表格建立語句 ===\n\n")
            self.structure_text.insert(tk.END, f"{create_sql}\n\n")
            
            self.structure_text.insert(tk.END, "=== 欄位資訊 ===\n\n")
            self.structure_text.insert(tk.END, f"{'欄位名稱':<20} {'類型':<15} {'非空':<8} {'預設值':<15} {'主鍵'}\n")
            self.structure_text.insert(tk.END, "-" * 80 + "\n")
            
            for col in columns:
                cid, name, col_type, notnull, dflt_value, pk = col
                self.structure_text.insert(tk.END, 
                    f"{name:<20} {col_type:<15} {'YES' if notnull else 'NO':<8} "
                    f"{str(dflt_value) if dflt_value else 'NULL':<15} {'YES' if pk else 'NO'}\n")
            
            if indexes:
                self.structure_text.insert(tk.END, "\n=== 索引 ===\n\n")
                for idx in indexes:
                    self.structure_text.insert(tk.END, f"- {idx[1]} (unique: {idx[2]})\n")
            
            if foreign_keys:
                self.structure_text.insert(tk.END, "\n=== 外鍵約束 ===\n\n")
                for fk in foreign_keys:
                    self.structure_text.insert(tk.END, 
                        f"- {fk[3]} → {fk[2]}.{fk[4]}\n")
            
        except sqlite3.Error as e:
            messagebox.showerror("錯誤", f"載入結構失敗: {e}")
    
    def show_detail(self, event):
        """顯示選中資料的詳細資訊（包含影像）"""
        selection = self.tree.selection()
        if not selection or not self.current_table:
            return
        
        item = self.tree.item(selection[0])
        values = item['values']
        
        # 建立詳細視窗
        detail_window = tk.Toplevel(self.root)
        detail_window.title(f"詳細資料 - {self.current_table}")
        detail_window.geometry("800x600")
        
        # 取得欄位名稱
        columns = self.tree['columns']
        
        # 從資料庫取得原始資料（包含 BLOB）
        try:
            cursor = self.conn.cursor()
            # 假設第一個欄位是 id
            record_id = values[0]
            cursor.execute(f"SELECT * FROM {self.current_table} WHERE {columns[0]} = ?", (record_id,))
            row = cursor.fetchone()
            
            # 建立可滾動的 Frame
            canvas = tk.Canvas(detail_window)
            scrollbar = tk.Scrollbar(detail_window, orient="vertical", command=canvas.yview)
            scrollable_frame = tk.Frame(canvas)
            
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            
            # 顯示每個欄位
            for i, col in enumerate(columns):
                frame = tk.Frame(scrollable_frame, pady=5)
                frame.pack(fill=tk.X, padx=10)
                
                tk.Label(frame, text=f"{col}:", font=("Arial", 10, "bold"), 
                        width=20, anchor='w').pack(side=tk.LEFT)
                
                value = row[i]
                
                # 處理 BLOB 資料（影像）
                if isinstance(value, bytes):
                    if col in ['imagedata', 'thumbdata', 'original_data', 'thumbnail']:
                        try:
                            # 嘗試顯示影像
                            img = Image.open(io.BytesIO(value))
                            img.thumbnail((400, 300))
                            photo = ImageTk.PhotoImage(img)
                            
                            img_label = tk.Label(frame, image=photo)
                            img_label.image = photo  # 保持參考
                            img_label.pack(side=tk.LEFT)
                            
                            tk.Label(frame, text=f"({len(value)} bytes, {img.format} {img.size})",
                                   fg="gray").pack(side=tk.LEFT, padx=5)
                        except Exception as e:
                            tk.Label(frame, text=f"<BLOB: {len(value)} bytes>",
                                   fg="blue").pack(side=tk.LEFT)
                    else:
                        tk.Label(frame, text=f"<BLOB: {len(value)} bytes>",
                               fg="blue").pack(side=tk.LEFT)
                elif value is None:
                    tk.Label(frame, text="<NULL>", fg="gray").pack(side=tk.LEFT)
                else:
                    text_widget = tk.Text(frame, height=1, width=50)
                    text_widget.insert(1.0, str(value))
                    text_widget.config(state=tk.DISABLED)
                    text_widget.pack(side=tk.LEFT)
            
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            
        except sqlite3.Error as e:
            messagebox.showerror("錯誤", f"載入詳細資料失敗: {e}")
    
    def search_data(self):
        """搜尋資料"""
        if not self.current_table:
            messagebox.showwarning("警告", "請先選擇一個表格")
            return
        
        keyword = self.search_var.get().strip()
        if not keyword:
            self.load_table_data(self.current_table)
            return
        
        try:
            cursor = self.conn.cursor()
            cursor.execute(f"PRAGMA table_info({self.current_table})")
            columns = [col[1] for col in cursor.fetchall()]
            
            # 建立搜尋條件（排除 BLOB 欄位）
            text_columns = [col for col in columns 
                          if col not in ['imagedata', 'thumbdata', 'original_data', 'thumbnail']]
            
            where_clause = " OR ".join([f"{col} LIKE ?" for col in text_columns])
            params = [f"%{keyword}%" for _ in text_columns]
            
            query = f"SELECT * FROM {self.current_table} WHERE {where_clause}"
            cursor.execute(query, params)
            
            rows = cursor.fetchall()
            
            # 清空並重新載入
            self.tree.delete(*self.tree.get_children())
            
            for row in rows:
                values = []
                for value in row:
                    if isinstance(value, bytes):
                        values.append(f"<BLOB: {len(value)} bytes>")
                    elif value is None:
                        values.append("<NULL>")
                    else:
                        values.append(str(value))
                
                self.tree.insert('', tk.END, values=values)
            
            self.status_label.config(text=f"🔍 搜尋結果: {len(rows)} 筆資料")
            
        except sqlite3.Error as e:
            messagebox.showerror("錯誤", f"搜尋失敗: {e}")
    
    def sort_by_column(self, col):
        """按欄位排序"""
        # 簡化版排序（實際專案應該重新查詢資料庫）
        items = [(self.tree.set(k, col), k) for k in self.tree.get_children('')]
        items.sort()
        
        for index, (val, k) in enumerate(items):
            self.tree.move(k, '', index)
    
    def export_csv(self):
        """匯出為 CSV"""
        if not self.current_table:
            messagebox.showwarning("警告", "請先選擇一個表格")
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"{self.current_table}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        
        if not filename:
            return
        
        try:
            cursor = self.conn.cursor()
            cursor.execute(f"SELECT * FROM {self.current_table}")
            
            rows = cursor.fetchall()
            columns = [description[0] for description in cursor.description]
            
            with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(columns)
                
                for row in rows:
                    values = []
                    for value in row:
                        if isinstance(value, bytes):
                            values.append(f"<BLOB: {len(value)} bytes>")
                        elif value is None:
                            values.append("")
                        else:
                            values.append(value)
                    writer.writerow(values)
            
            messagebox.showinfo("成功", f"已匯出 {len(rows)} 筆資料到:\n{filename}")
            self.status_label.config(text=f"✅ 已匯出到 {filename}")
            
        except Exception as e:
            messagebox.showerror("錯誤", f"匯出失敗: {e}")
    
    def show_sql_query(self):
        """顯示 SQL 查詢視窗"""
        query_window = tk.Toplevel(self.root)
        query_window.title("SQL 查詢")
        query_window.geometry("800x600")
        
        # SQL 輸入區
        tk.Label(query_window, text="輸入 SQL 查詢:", font=("Arial", 10, "bold")).pack(pady=5)
        
        sql_frame = tk.Frame(query_window)
        sql_frame.pack(fill=tk.X, padx=10, pady=5)
        
        sql_scrollbar = tk.Scrollbar(sql_frame)
        sql_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        sql_text = tk.Text(sql_frame, height=5, yscrollcommand=sql_scrollbar.set)
        sql_text.pack(fill=tk.X)
        sql_scrollbar.config(command=sql_text.yview)
        
        # 按鈕
        btn_frame = tk.Frame(query_window)
        btn_frame.pack(pady=5)
        
        def execute_query():
            query = sql_text.get(1.0, tk.END).strip()
            if not query:
                return
            
            try:
                cursor = self.conn.cursor()
                cursor.execute(query)
                
                if query.upper().startswith('SELECT'):
                    rows = cursor.fetchall()
                    columns = [description[0] for description in cursor.description]
                    
                    # 清空結果
                    result_tree.delete(*result_tree.get_children())
                    
                    # 設定欄位
                    result_tree['columns'] = columns
                    result_tree['show'] = 'headings'
                    
                    for col in columns:
                        result_tree.heading(col, text=col)
                        result_tree.column(col, width=120)
                    
                    # 插入資料
                    for row in rows:
                        values = []
                        for value in row:
                            if isinstance(value, bytes):
                                values.append(f"<BLOB: {len(value)} bytes>")
                            elif value is None:
                                values.append("<NULL>")
                            else:
                                values.append(str(value))
                        result_tree.insert('', tk.END, values=values)
                    
                    result_label.config(text=f"✅ 查詢成功: {len(rows)} 筆結果", fg="green")
                else:
                    self.conn.commit()
                    result_label.config(text="✅ 執行成功", fg="green")
                
            except sqlite3.Error as e:
                result_label.config(text=f"❌ 錯誤: {e}", fg="red")
        
        tk.Button(btn_frame, text="執行", command=execute_query, 
                 bg="#4CAF50", fg="white", padx=20).pack(side=tk.LEFT, padx=5)
        
        # 結果顯示區
        result_label = tk.Label(query_window, text="", font=("Arial", 9))
        result_label.pack(pady=5)
        
        result_frame = tk.Frame(query_window)
        result_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        result_scrollbar_y = tk.Scrollbar(result_frame)
        result_scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        
        result_scrollbar_x = tk.Scrollbar(result_frame, orient=tk.HORIZONTAL)
        result_scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        
        result_tree = ttk.Treeview(result_frame,
                                  yscrollcommand=result_scrollbar_y.set,
                                  xscrollcommand=result_scrollbar_x.set)
        result_tree.pack(fill=tk.BOTH, expand=True)
        
        result_scrollbar_y.config(command=result_tree.yview)
        result_scrollbar_x.config(command=result_tree.xview)
    
    def show_statistics(self):
        """顯示資料庫統計資訊"""
        stats_window = tk.Toplevel(self.root)
        stats_window.title("資料庫統計")
        stats_window.geometry("600x400")
        
        text_frame = tk.Frame(stats_window)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        scrollbar = tk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        text = tk.Text(text_frame, yscrollcommand=scrollbar.set, font=("Courier", 10))
        text.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=text.yview)
        
        try:
            cursor = self.conn.cursor()
            
            text.insert(tk.END, "=== 資料庫統計資訊 ===\n\n")
            text.insert(tk.END, f"資料庫路徑: {self.db_path}\n\n")
            
            # 檔案大小
            import os
            if os.path.exists(self.db_path):
                size = os.path.getsize(self.db_path)
                text.insert(tk.END, f"檔案大小: {size:,} bytes ({size/1024/1024:.2f} MB)\n\n")
            
            # 表格統計
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            
            text.insert(tk.END, f"資料表數量: {len(tables)}\n\n")
            text.insert(tk.END, "=== 各表格資料量 ===\n\n")
            
            for table in tables:
                table_name = table[0]
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                text.insert(tk.END, f"  {table_name:<30} {count:>10} 筆\n")
            
            # 影像統計
            text.insert(tk.END, "\n=== 影像資料統計 ===\n\n")
            
            if 'imageuploads' in [t[0] for t in tables]:
                cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN imagedata IS NOT NULL THEN 1 ELSE 0 END) as has_image,
                    SUM(CASE WHEN thumbdata IS NOT NULL THEN 1 ELSE 0 END) as has_thumb,
                    SUM(LENGTH(imagedata)) as total_image_size,
                    SUM(LENGTH(thumbdata)) as total_thumb_size
                FROM imageuploads
                """)
                
                stats = cursor.fetchone()
                text.insert(tk.END, f"  總影像數: {stats[0]}\n")
                text.insert(tk.END, f"  有完整影像: {stats[1]}\n")
                text.insert(tk.END, f"  有縮圖: {stats[2]}\n")
                
                if stats[3]:
                    text.insert(tk.END, f"  完整影像總大小: {stats[3]/1024/1024:.2f} MB\n")
                if stats[4]:
                    text.insert(tk.END, f"  縮圖總大小: {stats[4]/1024:.2f} KB\n")
            
        except sqlite3.Error as e:
            text.insert(tk.END, f"\n錯誤: {e}")
        
        text.config(state=tk.DISABLED)
    
    def refresh(self):
        """重新整理"""
        if self.current_table:
            self.load_table_data(self.current_table)
            self.load_table_structure(self.current_table)
    
    def run(self):
        """執行主迴圈"""
        self.root.mainloop()
    
    def __del__(self):
        """關閉資料庫連接"""
        if self.conn:
            self.conn.close()

# 命令列模式
def cli_mode(db_path):
    """命令列檢視模式"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print(f"\n{'='*60}")
        print(f"資料庫檢視器 - {db_path}")
        print(f"{'='*60}\n")
        
        # 列出所有表格
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        print(f"📋 資料表列表 ({len(tables)} 個):\n")
        for i, table in enumerate(tables, 1):
            cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
            count = cursor.fetchone()[0]
            print(f"  {i}. {table[0]:<30} ({count} 筆資料)")
        
        print(f"\n{'='*60}\n")
        
        # 影像統計
        if 'imageuploads' in [t[0] for t in tables]:
            print("📸 影像統計:\n")
            cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN imagedata IS NOT NULL THEN 1 ELSE 0 END) as has_image,
                SUM(CASE WHEN thumbdata IS NOT NULL THEN 1 ELSE 0 END) as has_thumb
            FROM imageuploads
            """)
            
            stats = cursor.fetchone()
            print(f"  總數: {stats[0]}")
            print(f"  有完整影像: {stats[1]}")
            print(f"  有縮圖: {stats[2]}")
            print(f"  無資料: {stats[0] - max(stats[1], stats[2])}")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"❌ 錯誤: {e}")

if __name__ == "__main__":
    import sys
    
    # 檢查命令列參數
    if len(sys.argv) > 1:
        if sys.argv[1] == "--cli":
            # 命令列模式
            db_path = sys.argv[2] if len(sys.argv) > 2 else "medical_system.db"
            cli_mode(db_path)
        else:
            # GUI 模式，指定資料庫路徑
            viewer = DatabaseViewer(sys.argv[1])
            viewer.run()
    else:
        # 預設 GUI 模式
        viewer = DatabaseViewer()
        viewer.run()