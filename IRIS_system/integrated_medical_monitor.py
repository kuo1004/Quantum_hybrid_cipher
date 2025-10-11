#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
整合版醫療影像傳輸監控系統 - 增強版
可以監控實際運行的CA、Sender、Receiver服務器
增強日誌功能，詳細顯示所有操作和狀態
"""

import os
import time
import json
import socket
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
from datetime import datetime
import subprocess
import psutil
import queue

class EnhancedServerMonitor:
    """增強版服務器狀態監控類"""

    def __init__(self):
        self.servers = {
            'ca': {'host': '127.0.0.1', 'port': 8001, 'status': 'unknown', 'process': None, 'last_check': None},
            'sender': {'host': '127.0.0.1', 'port': 8002, 'status': 'unknown', 'process': None, 'last_check': None},
            'receiver': {'host': '127.0.0.1', 'port': 8003, 'status': 'unknown', 'process': None, 'last_check': None}
        }
        self.monitoring = False
        self.log_callback = None

    def set_log_callback(self, callback):
        """設置日誌回調函數"""
        self.log_callback = callback

    def log_message(self, message, level="INFO", server_type="SYSTEM"):
        """記錄日誌消息"""
        if self.log_callback:
            self.log_callback(message, level, server_type)

    def check_server_status(self, server_type):
        """檢查特定服務器的狀態"""
        server_info = self.servers[server_type]
        self.log_message(f"檢查 {server_type.upper()} 服務器狀態...", "INFO", server_type.upper())

        try:
            start_time = time.time()
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(3)
                result = sock.connect_ex((server_info['host'], server_info['port']))

                response_time = (time.time() - start_time) * 1000  # 毫秒

                if result == 0:
                    server_info['status'] = 'running'
                    server_info['last_check'] = datetime.now()
                    self.log_message(f"連接成功，響應時間：{response_time:.1f}ms", "SUCCESS", server_type.upper())
                    return True
                else:
                    server_info['status'] = 'stopped'
                    self.log_message(f"連接失敗，端口 {server_info['port']} 無響應", "WARNING", server_type.upper())
                    return False
        except Exception as e:
            server_info['status'] = 'error'
            self.log_message(f"檢查狀態時發生錯誤：{str(e)}", "ERROR", server_type.upper())
            return False

    def start_monitoring(self, callback):
        """開始監控所有服務器"""
        def monitor_thread():
            self.monitoring = True
            self.log_message("自動監控服務已啟動，每5秒檢查一次服務器狀態", "INFO", "MONITOR")

            while self.monitoring:
                try:
                    for server_type in self.servers:
                        old_status = self.servers[server_type]['status']
                        is_running = self.check_server_status(server_type)
                        new_status = self.servers[server_type]['status']

                        # 如果狀態改變，通知回調
                        if old_status != new_status:
                            status_change_msg = f"狀態變更：{old_status} → {new_status}"
                            self.log_message(status_change_msg, "INFO", server_type.upper())
                            callback(server_type, new_status, is_running)

                    time.sleep(5)  # 每5秒檢查一次
                except Exception as e:
                    self.log_message(f"監控循環發生錯誤：{str(e)}", "ERROR", "MONITOR")
                    time.sleep(5)

        threading.Thread(target=monitor_thread, daemon=True).start()

    def stop_monitoring(self):
        """停止監控"""
        self.monitoring = False
        self.log_message("自動監控服務已停止", "INFO", "MONITOR")

    def send_request_to_server(self, server_type, request_data):
        """向指定服務器發送請求"""
        server_info = self.servers[server_type]
        self.log_message(f"向 {server_type.upper()} 發送請求：{request_data}", "INFO", server_type.upper())

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(10)
                sock.connect((server_info['host'], server_info['port']))

                # 發送請求
                if isinstance(request_data, dict):
                    request_json = json.dumps(request_data)
                    sock.send(request_json.encode('utf-8'))
                    self.log_message(f"發送 JSON 請求，大小：{len(request_json)} bytes", "DEBUG", server_type.upper())
                else:
                    sock.send(request_data.encode('utf-8'))
                    self.log_message(f"發送文本請求，大小：{len(request_data)} bytes", "DEBUG", server_type.upper())

                # 接收響應
                response = sock.recv(4096)
                response_text = response.decode('utf-8')
                self.log_message(f"收到響應，大小：{len(response)} bytes", "SUCCESS", server_type.upper())

                # 嘗試解析 JSON 響應
                try:
                    response_json = json.loads(response_text)
                    self.log_message(f"響應內容：{json.dumps(response_json, indent=2, ensure_ascii=False)}", "INFO", server_type.upper())
                except:
                    self.log_message(f"響應內容：{response_text[:200]}...", "INFO", server_type.upper())

                return response_text

        except socket.timeout:
            self.log_message("請求超時（10秒）", "WARNING", server_type.upper())
            return "錯誤: 請求超時"
        except ConnectionRefusedError:
            self.log_message("連接被拒絕，服務器可能未啟動", "ERROR", server_type.upper())
            return "錯誤: 連接被拒絕"
        except Exception as e:
            self.log_message(f"請求發生錯誤：{str(e)}", "ERROR", server_type.upper())
            return f"錯誤: {str(e)}"

class DetailedLogger:
    """詳細日誌記錄器"""

    def __init__(self, log_widget, system_log_widget):
        self.log_widget = log_widget
        self.system_log_widget = system_log_widget
        self.log_queue = queue.Queue()
        self.processing_logs = True

        # 配置日誌顏色和樣式
        self.setup_log_styles()

        # 啟動日誌處理線程
        self.start_log_processor()

    def setup_log_styles(self):
        """設置日誌樣式"""
        # 主監控日誌樣式
        self.log_widget.tag_configure("INFO", foreground="blue", font=('Consolas', 9))
        self.log_widget.tag_configure("SUCCESS", foreground="green", font=('Consolas', 9, 'bold'))
        self.log_widget.tag_configure("WARNING", foreground="orange", font=('Consolas', 9))
        self.log_widget.tag_configure("ERROR", foreground="red", font=('Consolas', 9, 'bold'))
        self.log_widget.tag_configure("DEBUG", foreground="gray", font=('Consolas', 8))

        # CA服務器專用樣式
        self.log_widget.tag_configure("CA", foreground="purple", font=('Consolas', 9, 'bold'))
        self.log_widget.tag_configure("SENDER", foreground="blue", font=('Consolas', 9, 'bold'))
        self.log_widget.tag_configure("RECEIVER", foreground="green", font=('Consolas', 9, 'bold'))
        self.log_widget.tag_configure("MONITOR", foreground="navy", font=('Consolas', 9))
        self.log_widget.tag_configure("SYSTEM", foreground="black", font=('Consolas', 9))

        # 系統日誌樣式
        self.system_log_widget.tag_configure("INFO", foreground="blue")
        self.system_log_widget.tag_configure("SUCCESS", foreground="green", font=('Consolas', 9, 'bold'))
        self.system_log_widget.tag_configure("WARNING", foreground="orange")
        self.system_log_widget.tag_configure("ERROR", foreground="red", font=('Consolas', 9, 'bold'))

    def start_log_processor(self):
        """啟動日誌處理線程"""
        def process_logs():
            while self.processing_logs:
                try:
                    # 從隊列中獲取日誌消息
                    message, level, server_type, timestamp = self.log_queue.get(timeout=1)

                    # 格式化消息
                    formatted_message = f"[{timestamp}] [{server_type}] {message}\n"

                    # 添加到主監控日誌
                    self.log_widget.insert(tk.END, formatted_message, level)
                    self.log_widget.see(tk.END)

                    # 添加到系統日誌
                    system_formatted = f"[{timestamp}] [{level}] [{server_type}] {message}\n"
                    self.system_log_widget.insert(tk.END, system_formatted, level)
                    self.system_log_widget.see(tk.END)

                    # 限制日誌長度
                    self.limit_log_length(self.log_widget, 1000)
                    self.limit_log_length(self.system_log_widget, 2000)

                except queue.Empty:
                    continue
                except Exception as e:
                    print(f"日誌處理錯誤: {e}")

        threading.Thread(target=process_logs, daemon=True).start()

    def limit_log_length(self, widget, max_lines):
        """限制日誌長度"""
        try:
            lines = widget.get(1.0, tk.END).split('\n')
            if len(lines) > max_lines:
                # 刪除前面的行，保留最新的
                widget.delete(1.0, f"{len(lines)-max_lines}.0")
        except:
            pass

    def log(self, message, level="INFO", server_type="SYSTEM"):
        """記錄日誌"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]  # 包含毫秒
        try:
            self.log_queue.put((message, level, server_type, timestamp), timeout=1)
        except queue.Full:
            # 如果隊列滿了，跳過這條消息
            pass

    def stop(self):
        """停止日誌處理"""
        self.processing_logs = False

class EnhancedIntegratedMonitorGUI:
    """增強版整合監控系統GUI"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("醫療影像傳輸系統 - 增強監控台 v2.0")
        self.root.geometry("1500x1000")
        self.root.configure(bg='#f0f0f0')

        # 監控系統
        self.server_monitor = EnhancedServerMonitor()

        # 設置GUI
        self.setup_enhanced_ui()

        # 設置日誌系統
        self.logger = DetailedLogger(self.monitor_log, self.system_log)
        self.server_monitor.set_log_callback(self.logger.log)

        # 記錄啟動信息
        self.logger.log("醫療影像傳輸監控系統已啟動", "SUCCESS", "SYSTEM")
        self.logger.log(f"Python版本：{os.sys.version[:20]}...", "INFO", "SYSTEM")
        self.logger.log(f"工作目錄：{os.getcwd()}", "INFO", "SYSTEM")

        # 開始監控
        self.server_monitor.start_monitoring(self.on_server_status_change)

        # 開始目錄監控
        self.start_directory_monitoring()

    def setup_enhanced_ui(self):
        """設置增強版用戶界面"""

        # 主標題
        title_frame = ttk.Frame(self.root)
        title_frame.pack(fill=tk.X, padx=10, pady=5)

        title_label = ttk.Label(title_frame, text="🏥 醫療影像傳輸系統 - 增強監控台 v2.0", 
                               font=('Arial', 16, 'bold'))
        title_label.pack()

        # 狀態摘要欄
        self.setup_status_summary()

        # 創建主要的Notebook（標籤頁）
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 標籤頁1：實時監控
        self.setup_realtime_monitor_tab()

        # 標籤頁2：傳輸測試
        self.setup_transmission_test_tab()

        # 標籤頁3：詳細日誌
        self.setup_detailed_log_tab()

        # 標籤頁4：服務器管理
        self.setup_server_management_tab()

    def setup_status_summary(self):
        """設置狀態摘要欄"""
        summary_frame = ttk.Frame(self.root)
        summary_frame.pack(fill=tk.X, padx=10, pady=5)

        # 三方服務器快速狀態
        ca_summary = ttk.LabelFrame(summary_frame, text="🏛️ CA")
        ca_summary.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        self.ca_status_var = tk.StringVar(value="🔴 未知")
        ttk.Label(ca_summary, textvariable=self.ca_status_var, font=('Arial', 12, 'bold')).pack()

        sender_summary = ttk.LabelFrame(summary_frame, text="📤 Sender")
        sender_summary.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)

        self.sender_status_var = tk.StringVar(value="🔴 未知")
        ttk.Label(sender_summary, textvariable=self.sender_status_var, font=('Arial', 12, 'bold')).pack()

        receiver_summary = ttk.LabelFrame(summary_frame, text="📥 Receiver")
        receiver_summary.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))

        self.receiver_status_var = tk.StringVar(value="🔴 未知")
        ttk.Label(receiver_summary, textvariable=self.receiver_status_var, font=('Arial', 12, 'bold')).pack()

    def setup_realtime_monitor_tab(self):
        """設置實時監控標籤頁"""
        monitor_frame = ttk.Frame(self.notebook)
        self.notebook.add(monitor_frame, text="📊 實時監控")

        # 控制按鈕欄
        control_frame = ttk.Frame(monitor_frame)
        control_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(control_frame, text="🔄 刷新所有狀態", 
                  command=self.refresh_all_status).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="📋 查詢CA註冊", 
                  command=self.query_ca_registrations).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="📤 查詢Sender影像", 
                  command=self.query_sender_images).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="📥 查詢Receiver狀態", 
                  command=self.query_receiver_status).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="🗑️ 清除日誌", 
                  command=self.clear_monitor_log).pack(side=tk.LEFT, padx=5)

        # 服務器詳細狀態
        status_detail_frame = ttk.LabelFrame(monitor_frame, text="服務器詳細狀態", padding="10")
        status_detail_frame.pack(fill=tk.X, padx=5, pady=5)

        # 三欄布局
        ca_detail = ttk.LabelFrame(status_detail_frame, text="🏛️ CA服務器 (127.0.0.1:8001)")
        ca_detail.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        self.ca_uptime_var = tk.StringVar(value="最後檢查: 未檢查")
        ttk.Label(ca_detail, textvariable=self.ca_uptime_var, font=('Arial', 8)).pack(anchor=tk.W)
        ttk.Button(ca_detail, text="檢查狀態", 
                  command=lambda: self.check_server('ca')).pack(fill=tk.X, pady=2)

        sender_detail = ttk.LabelFrame(status_detail_frame, text="📤 Sender服務器 (127.0.0.1:8002)")
        sender_detail.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)

        self.sender_uptime_var = tk.StringVar(value="最後檢查: 未檢查")
        ttk.Label(sender_detail, textvariable=self.sender_uptime_var, font=('Arial', 8)).pack(anchor=tk.W)
        ttk.Button(sender_detail, text="檢查狀態", 
                  command=lambda: self.check_server('sender')).pack(fill=tk.X, pady=2)

        receiver_detail = ttk.LabelFrame(status_detail_frame, text="📥 Receiver服務器 (127.0.0.1:8003)")
        receiver_detail.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))

        self.receiver_uptime_var = tk.StringVar(value="最後檢查: 未檢查")
        ttk.Label(receiver_detail, textvariable=self.receiver_uptime_var, font=('Arial', 8)).pack(anchor=tk.W)
        ttk.Button(receiver_detail, text="檢查狀態", 
                  command=lambda: self.check_server('receiver')).pack(fill=tk.X, pady=2)

        # 實時監控日誌
        log_frame = ttk.LabelFrame(monitor_frame, text="實時監控日誌", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.monitor_log = scrolledtext.ScrolledText(log_frame, height=20, font=('Consolas', 9))
        self.monitor_log.pack(fill=tk.BOTH, expand=True)

    def setup_transmission_test_tab(self):
        """設置傳輸測試標籤頁"""
        test_frame = ttk.Frame(self.notebook)
        self.notebook.add(test_frame, text="🧪 傳輸測試")

        # 文件操作區
        file_frame = ttk.LabelFrame(test_frame, text="文件操作", padding="10")
        file_frame.pack(fill=tk.X, padx=5, pady=5)

        file_buttons = ttk.Frame(file_frame)
        file_buttons.pack(fill=tk.X)

        ttk.Button(file_buttons, text="📁 選擇測試影像", command=self.select_test_image, width=20).pack(side=tk.LEFT, padx=5)
        ttk.Button(file_buttons, text="📂 開啟輸入目錄", command=self.open_input_directory, width=20).pack(side=tk.LEFT, padx=5)
        ttk.Button(file_buttons, text="📂 開啟輸出目錄", command=self.open_output_directory, width=20).pack(side=tk.LEFT, padx=5)
        ttk.Button(file_buttons, text="📂 開啟接收目錄", command=self.open_received_directory, width=20).pack(side=tk.LEFT, padx=5)

        # 選中文件信息
        self.selected_file_info = scrolledtext.ScrolledText(file_frame, height=4)
        self.selected_file_info.pack(fill=tk.X, pady=(10, 0))

        # 傳輸狀態監控
        transmission_frame = ttk.LabelFrame(test_frame, text="傳輸狀態監控", padding="10")
        transmission_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 目錄監控狀態
        directories_info = ttk.Frame(transmission_frame)
        directories_info.pack(fill=tk.X, pady=(0, 10))

        # 三個目錄狀態
        input_dir_frame = ttk.LabelFrame(directories_info, text="📁 輸入目錄")
        input_dir_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        self.input_dir_status = tk.StringVar(value="檢查中...")
        ttk.Label(input_dir_frame, textvariable=self.input_dir_status).pack(anchor=tk.W)

        output_dir_frame = ttk.LabelFrame(directories_info, text="📦 輸出目錄")
        output_dir_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)

        self.output_dir_status = tk.StringVar(value="檢查中...")
        ttk.Label(output_dir_frame, textvariable=self.output_dir_status).pack(anchor=tk.W)

        received_dir_frame = ttk.LabelFrame(directories_info, text="📥 接收目錄")
        received_dir_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))

        self.received_dir_status = tk.StringVar(value="檢查中...")
        ttk.Label(received_dir_frame, textvariable=self.received_dir_status).pack(anchor=tk.W)

        # 傳輸日誌
        self.transmission_log = scrolledtext.ScrolledText(transmission_frame, height=15, font=('Consolas', 9))
        self.transmission_log.pack(fill=tk.BOTH, expand=True)

    def setup_detailed_log_tab(self):
        """設置詳細日誌標籤頁"""
        log_frame = ttk.Frame(self.notebook)
        self.notebook.add(log_frame, text="📋 詳細日誌")

        # 日誌控制
        log_control = ttk.Frame(log_frame)
        log_control.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(log_control, text="清除日誌", command=self.clear_all_logs).pack(side=tk.LEFT, padx=5)
        ttk.Button(log_control, text="保存日誌", command=self.save_all_logs).pack(side=tk.LEFT, padx=5)
        ttk.Button(log_control, text="刷新統計", command=self.refresh_statistics).pack(side=tk.LEFT, padx=5)

        # 日誌級別過濾
        filter_frame = ttk.LabelFrame(log_control, text="日誌級別")
        filter_frame.pack(side=tk.RIGHT, padx=5)

        self.show_debug = tk.BooleanVar(value=False)
        self.show_info = tk.BooleanVar(value=True)
        self.show_warning = tk.BooleanVar(value=True)
        self.show_error = tk.BooleanVar(value=True)

        ttk.Checkbutton(filter_frame, text="DEBUG", variable=self.show_debug).pack(side=tk.LEFT)
        ttk.Checkbutton(filter_frame, text="INFO", variable=self.show_info).pack(side=tk.LEFT)
        ttk.Checkbutton(filter_frame, text="WARNING", variable=self.show_warning).pack(side=tk.LEFT)
        ttk.Checkbutton(filter_frame, text="ERROR", variable=self.show_error).pack(side=tk.LEFT)

        # 系統詳細日誌
        self.system_log = scrolledtext.ScrolledText(log_frame, height=30, font=('Consolas', 9))
        self.system_log.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def setup_server_management_tab(self):
        """設置服務器管理標籤頁"""
        management_frame = ttk.Frame(self.notebook)
        self.notebook.add(management_frame, text="⚙️ 服務器管理")

        # 啟動指令參考
        startup_frame = ttk.LabelFrame(management_frame, text="服務器啟動指令", padding="10")
        startup_frame.pack(fill=tk.X, padx=5, pady=5)

        startup_info = ttk.Label(startup_frame, text="⚠️ 注意：服務器需要在外部終端機中啟動", 
                               foreground="red", font=('Arial', 10))
        startup_info.pack(pady=5)

        # 指令顯示
        commands_frame = ttk.Frame(startup_frame)
        commands_frame.pack(fill=tk.X, pady=5)

        ca_cmd = "python ca_server.py 127.0.0.1 8001"
        sender_cmd = "python sender_server_fixed.py 127.0.0.1 8002 127.0.0.1 8001"
        receiver_cmd = "python receiver_server_smart.py 127.0.0.1 8003 127.0.0.1 8001"

        for i, (name, cmd) in enumerate([("CA服務器", ca_cmd), ("Sender服務器", sender_cmd), ("Receiver服務器", receiver_cmd)]):
            cmd_frame = ttk.LabelFrame(commands_frame, text=f"{name}啟動命令")
            cmd_frame.pack(fill=tk.X, pady=2)

            cmd_text = tk.Text(cmd_frame, height=2, font=('Consolas', 10))
            cmd_text.pack(fill=tk.X, padx=5, pady=5)
            cmd_text.insert(1.0, cmd)
            cmd_text.config(state=tk.DISABLED)

        # 系統信息
        system_info_frame = ttk.LabelFrame(management_frame, text="系統信息", padding="10")
        system_info_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.system_info_text = scrolledtext.ScrolledText(system_info_frame, height=15, font=('Consolas', 9))
        self.system_info_text.pack(fill=tk.BOTH, expand=True)

        # 更新系統信息
        self.update_system_info()

    def on_server_status_change(self, server_type, status, is_running):
        """服務器狀態變更回調"""
        # 更新摘要狀態
        status_text = "🟢 運行中" if is_running else "🔴 停止"
        if status == 'error':
            status_text = "🟡 錯誤"

        if server_type == 'ca':
            self.ca_status_var.set(status_text)
            last_check = self.server_monitor.servers['ca'].get('last_check')
            if last_check:
                self.ca_uptime_var.set(f"最後檢查: {last_check.strftime('%H:%M:%S')}")
        elif server_type == 'sender':
            self.sender_status_var.set(status_text)
            last_check = self.server_monitor.servers['sender'].get('last_check')
            if last_check:
                self.sender_uptime_var.set(f"最後檢查: {last_check.strftime('%H:%M:%S')}")
        elif server_type == 'receiver':
            self.receiver_status_var.set(status_text)
            last_check = self.server_monitor.servers['receiver'].get('last_check')
            if last_check:
                self.receiver_uptime_var.set(f"最後檢查: {last_check.strftime('%H:%M:%S')}")

    def check_server(self, server_type):
        """手動檢查服務器狀態"""
        def check_thread():
            is_running = self.server_monitor.check_server_status(server_type)
            status = self.server_monitor.servers[server_type]['status']
            self.on_server_status_change(server_type, status, is_running)

        threading.Thread(target=check_thread, daemon=True).start()

    def refresh_all_status(self):
        """刷新所有服務器狀態"""
        self.logger.log("手動刷新所有服務器狀態", "INFO", "SYSTEM")
        for server_type in ['ca', 'sender', 'receiver']:
            self.check_server(server_type)

    def query_ca_registrations(self):
        """查詢CA註冊信息"""
        def query_thread():
            try:
                request = {'action': 'list_parties'}
                response = self.server_monitor.send_request_to_server('ca', request)
                self.logger.log(f"CA註冊查詢完成", "SUCCESS", "CA")
            except Exception as e:
                self.logger.log(f"CA註冊查詢失敗：{str(e)}", "ERROR", "CA")

        threading.Thread(target=query_thread, daemon=True).start()

    def query_sender_images(self):
        """查詢Sender可用影像"""
        def query_thread():
            try:
                request = {'action': 'request_image', 'receiver_id': 'monitor'}
                response = self.server_monitor.send_request_to_server('sender', request)
                self.logger.log(f"Sender影像查詢完成", "SUCCESS", "SENDER")
            except Exception as e:
                self.logger.log(f"Sender影像查詢失敗：{str(e)}", "ERROR", "SENDER")

        threading.Thread(target=query_thread, daemon=True).start()

    def query_receiver_status(self):
        """查詢Receiver狀態"""
        def query_thread():
            try:
                request = {'action': 'get_status', 'requester': 'monitor'}
                response = self.server_monitor.send_request_to_server('receiver', request)
                self.logger.log(f"Receiver狀態查詢完成", "SUCCESS", "RECEIVER")
            except Exception as e:
                self.logger.log(f"Receiver狀態查詢失敗：{str(e)}", "ERROR", "RECEIVER")

        threading.Thread(target=query_thread, daemon=True).start()

    def clear_monitor_log(self):
        """清除監控日誌"""
        self.monitor_log.delete(1.0, tk.END)
        self.logger.log("監控日誌已清除", "INFO", "SYSTEM")

    def select_test_image(self):
        """選擇測試影像"""
        file_path = filedialog.askopenfilename(
            title="選擇測試影像",
            filetypes=[
                ("影像文件", "*.png *.jpg *.jpeg *.bmp *.tiff"),
                ("所有文件", "*.*")
            ]
        )

        if file_path:
            try:
                import shutil
                input_dir = "./medical_images_input"
                os.makedirs(input_dir, exist_ok=True)

                filename = os.path.basename(file_path)
                dest_path = os.path.join(input_dir, filename)
                shutil.copy2(file_path, dest_path)

                file_size = os.path.getsize(file_path)

                # 記錄詳細日誌
                self.logger.log(f"用戶選擇測試影像：{filename}", "INFO", "SYSTEM")
                self.logger.log(f"文件大小：{file_size:,} bytes ({file_size/1024/1024:.2f} MB)", "INFO", "SYSTEM")
                self.logger.log(f"已複製到：{dest_path}", "SUCCESS", "SYSTEM")

                # 顯示文件信息
                info_text = f"""
已選擇並複製測試影像:
原始路徑: {file_path}
目標路徑: {dest_path}
文件大小: {file_size:,} bytes ({file_size/1024/1024:.2f} MB)
複製時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

系統將自動檢測並處理此影像...
                """.strip()

                self.selected_file_info.delete(1.0, tk.END)
                self.selected_file_info.insert(1.0, info_text)

                # 記錄到傳輸日誌
                timestamp = datetime.now().strftime("%H:%M:%S")
                log_message = f"[{timestamp}] 📷 已添加測試影像: {filename} ({file_size:,} bytes)\n"
                self.transmission_log.insert(tk.END, log_message)
                self.transmission_log.see(tk.END)

            except Exception as e:
                self.logger.log(f"複製測試影像失敗：{str(e)}", "ERROR", "SYSTEM")
                messagebox.showerror("錯誤", f"複製文件失敗: {str(e)}")

    def open_input_directory(self):
        """開啟輸入目錄"""
        self.open_directory("./medical_images_input")

    def open_output_directory(self):
        """開啟輸出目錄"""
        self.open_directory("./medical_images_output")

    def open_received_directory(self):
        """開啟接收目錄"""
        self.open_directory("./medical_images_received")

    def open_directory(self, path):
        """開啟指定目錄"""
        import platform

        os.makedirs(path, exist_ok=True)
        abs_path = os.path.abspath(path)

        self.logger.log(f"開啟目錄：{abs_path}", "INFO", "SYSTEM")

        try:
            system = platform.system()
            if system == "Windows":
                subprocess.run(f'explorer "{abs_path}"', shell=True)
            elif system == "Darwin":  # macOS
                subprocess.run(["open", abs_path])
            else:  # Linux
                subprocess.run(["xdg-open", abs_path])

            self.logger.log(f"目錄已開啟：{abs_path}", "SUCCESS", "SYSTEM")

        except Exception as e:
            self.logger.log(f"無法開啟目錄：{str(e)}", "WARNING", "SYSTEM")
            messagebox.showwarning("提醒", f"無法開啟目錄: {abs_path}\n錯誤: {str(e)}")

    def start_directory_monitoring(self):
        """開始目錄監控"""
        def monitor_directories():
            self.logger.log("目錄監控服務已啟動", "INFO", "SYSTEM")

            while True:
                try:
                    directories = {
                        'input': './medical_images_input',
                        'output': './medical_images_output',
                        'received': './medical_images_received'
                    }

                    for dir_type, path in directories.items():
                        if os.path.exists(path):
                            files = [f for f in os.listdir(path) 
                                    if os.path.isfile(os.path.join(path, f))]
                            count = len(files)

                            # 計算總大小
                            total_size = sum(os.path.getsize(os.path.join(path, f)) for f in files)
                            size_mb = total_size / 1024 / 1024

                            status_text = f"文件數量: {count}, 總大小: {size_mb:.1f} MB"

                            if dir_type == 'input':
                                old_status = self.input_dir_status.get()
                                if old_status != status_text:
                                    self.input_dir_status.set(status_text)
                                    self.logger.log(f"輸入目錄狀態更新：{status_text}", "DEBUG", "SYSTEM")
                            elif dir_type == 'output':
                                old_status = self.output_dir_status.get()
                                if old_status != status_text:
                                    self.output_dir_status.set(status_text)
                                    self.logger.log(f"輸出目錄狀態更新：{status_text}", "DEBUG", "SYSTEM")
                            elif dir_type == 'received':
                                old_status = self.received_dir_status.get()
                                if old_status != status_text:
                                    self.received_dir_status.set(status_text)
                                    self.logger.log(f"接收目錄狀態更新：{status_text}", "DEBUG", "SYSTEM")

                                    # 檢測新接收的文件
                                    if count > getattr(self, f'prev_{dir_type}_count', 0):
                                        new_files = count - getattr(self, f'prev_{dir_type}_count', 0)
                                        self.logger.log(f"檢測到 {new_files} 個新接收的文件", "SUCCESS", "RECEIVER")

                            setattr(self, f'prev_{dir_type}_count', count)
                        else:
                            if dir_type == 'input':
                                self.input_dir_status.set("目錄不存在")
                            elif dir_type == 'output':
                                self.output_dir_status.set("目錄不存在")
                            elif dir_type == 'received':
                                self.received_dir_status.set("目錄不存在")

                    time.sleep(3)  # 每3秒檢查一次
                except Exception as e:
                    self.logger.log(f"目錄監控錯誤：{str(e)}", "ERROR", "SYSTEM")
                    time.sleep(5)

        threading.Thread(target=monitor_directories, daemon=True).start()

    def clear_all_logs(self):
        """清除所有日誌"""
        self.monitor_log.delete(1.0, tk.END)
        self.transmission_log.delete(1.0, tk.END)
        self.system_log.delete(1.0, tk.END)
        self.logger.log("所有日誌已清除", "INFO", "SYSTEM")

    def save_all_logs(self):
        """保存所有日誌"""
        file_path = filedialog.asksaveasfilename(
            title="保存系統日誌",
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
        )

        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("=== 醫療影像傳輸系統監控日誌 ===\n")
                    f.write(f"生成時間: {datetime.now()}\n\n")

                    f.write("=== 實時監控日誌 ===\n")
                    f.write(self.monitor_log.get(1.0, tk.END))

                    f.write("\n=== 傳輸測試日誌 ===\n")
                    f.write(self.transmission_log.get(1.0, tk.END))

                    f.write("\n=== 詳細系統日誌 ===\n")
                    f.write(self.system_log.get(1.0, tk.END))

                self.logger.log(f"日誌已保存到：{file_path}", "SUCCESS", "SYSTEM")
                messagebox.showinfo("成功", f"日誌已保存到: {file_path}")
            except Exception as e:
                self.logger.log(f"保存日誌失敗：{str(e)}", "ERROR", "SYSTEM")
                messagebox.showerror("錯誤", f"保存日誌失敗: {str(e)}")

    def refresh_statistics(self):
        """刷新統計信息"""
        self.logger.log("刷新系統統計信息", "INFO", "SYSTEM")
        self.update_system_info()

        # 統計服務器狀態
        running_count = sum(1 for server in self.server_monitor.servers.values() if server['status'] == 'running')
        total_count = len(self.server_monitor.servers)
        self.logger.log(f"服務器狀態統計：{running_count}/{total_count} 個服務器運行中", "INFO", "SYSTEM")

    def update_system_info(self):
        """更新系統信息"""
        try:
            # 收集系統信息
            info_parts = []

            # 基本信息
            info_parts.append("=== 系統基本信息 ===")
            info_parts.append(f"當前時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            info_parts.append(f"Python版本: {os.sys.version}")
            info_parts.append(f"工作目錄: {os.getcwd()}")
            info_parts.append("")

            # 服務器狀態
            info_parts.append("=== 服務器狀態詳情 ===")
            for server_type, server_info in self.server_monitor.servers.items():
                status_icon = {"running": "🟢", "stopped": "🔴", "error": "🟡", "unknown": "⚪"}.get(server_info['status'], "❓")
                info_parts.append(f"{server_type.upper()}: {status_icon} {server_info['status']}")
                info_parts.append(f"  地址: {server_info['host']}:{server_info['port']}")
                if server_info['last_check']:
                    info_parts.append(f"  最後檢查: {server_info['last_check'].strftime('%Y-%m-%d %H:%M:%S')}")
                else:
                    info_parts.append(f"  最後檢查: 未檢查")
            info_parts.append("")

            # 目錄狀態
            info_parts.append("=== 目錄狀態 ===")
            directories = [
                ("輸入目錄", "./medical_images_input"),
                ("輸出目錄", "./medical_images_output"),
                ("接收目錄", "./medical_images_received")
            ]

            for name, path in directories:
                if os.path.exists(path):
                    files = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
                    total_size = sum(os.path.getsize(os.path.join(path, f)) for f in files)
                    info_parts.append(f"{name}: ✅ 存在")
                    info_parts.append(f"  文件數量: {len(files)}")
                    info_parts.append(f"  總大小: {total_size:,} bytes ({total_size/1024/1024:.2f} MB)")
                    info_parts.append(f"  路徑: {os.path.abspath(path)}")
                else:
                    info_parts.append(f"{name}: ❌ 不存在")
                    info_parts.append(f"  路徑: {os.path.abspath(path)}")
            info_parts.append("")

            # 啟動指令
            info_parts.append("=== 服務器啟動指令 ===")
            info_parts.append("1. python ca_server.py 127.0.0.1 8001")
            info_parts.append("2. python sender_server_fixed.py 127.0.0.1 8002 127.0.0.1 8001")
            info_parts.append("3. python receiver_server_smart.py 127.0.0.1 8003 127.0.0.1 8001")
            info_parts.append("")

            # 使用說明
            info_parts.append("=== 使用說明 ===")
            info_parts.append("1. 按順序啟動三個服務器（在不同終端機中）")
            info_parts.append("2. 在'傳輸測試'標籤頁選擇影像文件進行測試")
            info_parts.append("3. 在'實時監控'標籤頁觀察服務器狀態")
            info_parts.append("4. 在'詳細日誌'標籤頁查看完整的操作記錄")
            info_parts.append("5. 檢查目錄中的文件變化")

            info_text = "\n".join(info_parts)

            self.system_info_text.delete(1.0, tk.END)
            self.system_info_text.insert(1.0, info_text)

        except Exception as e:
            error_text = f"系統信息獲取失敗: {str(e)}\n\n詳細錯誤:\n{str(e)}"
            self.system_info_text.delete(1.0, tk.END)
            self.system_info_text.insert(1.0, error_text)
            self.logger.log(f"更新系統信息失敗：{str(e)}", "ERROR", "SYSTEM")

    def run(self):
        """運行GUI應用程序"""
        try:
            self.logger.log("GUI主循環開始", "INFO", "SYSTEM")
            self.root.mainloop()
        except KeyboardInterrupt:
            self.logger.log("收到中斷信號，準備關閉", "WARNING", "SYSTEM")
        except Exception as e:
            self.logger.log(f"GUI運行錯誤：{str(e)}", "ERROR", "SYSTEM")
        finally:
            self.cleanup()

    def cleanup(self):
        """清理資源"""
        try:
            self.logger.log("開始清理系統資源", "INFO", "SYSTEM")
            self.server_monitor.stop_monitoring()
            self.logger.stop()
            self.logger.log("系統資源清理完成", "INFO", "SYSTEM")
        except Exception as e:
            print(f"清理資源時發生錯誤: {e}")

def main():
    """主函數"""
    try:
        app = EnhancedIntegratedMonitorGUI()
        app.run()
    except Exception as e:
        print(f"監控系統啟動失敗: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()