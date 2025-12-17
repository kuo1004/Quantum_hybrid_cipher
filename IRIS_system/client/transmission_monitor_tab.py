# -*- coding: utf-8 -*-
"""
transmission_monitor_tab.py - 傳輸流程視覺化監控標籤頁
顯示 CA Server ↔ App Server ↔ Client 之間的即時傳輸動態
"""

import customtkinter as ctk
import requests
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional
import queue


class TransmissionMonitorTab:
    """傳輸流程監控標籤頁"""
    
    def __init__(self, parent, user, endpoints_config):
        """
        初始化傳輸監控標籤頁
        
        Args:
            parent: 父容器
            user: 使用者資訊
            endpoints_config: 端點配置
        """
        self.parent = parent
        self.user = user
        self.endpoints = endpoints_config
        self.running = False
        self.update_thread = None
        
        # 存儲狀態數據
        self.status_data = {
            'ca_server': None,
            'app_server': None,
            'clients': {}
        }
        
        # 傳輸記錄佇列
        self.transmission_queue = queue.Queue(maxsize=10)
        self.log_queue = queue.Queue(maxsize=100)
        
        self.build_ui()
        self.start_monitoring()
    
    def build_ui(self):
        """建立 UI"""
        # 主容器 - 使用深色背景
        main_container = ctk.CTkFrame(self.parent, fg_color="#1a1f2e")
        main_container.pack(fill="both", expand=True)
        
        # 標題區域
        header = ctk.CTkFrame(main_container, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=20)
        
        title_frame = ctk.CTkFrame(header, fg_color="transparent")
        title_frame.pack(side="left")
        
        ctk.CTkLabel(
            title_frame,
            text="⚡ 系統傳輸監控面板",
            font=("Microsoft JhengHei", 28, "bold"),
            text_color="white"
        ).pack(anchor="w")
        
        ctk.CTkLabel(
            title_frame,
            text="即時監控 CA Server、Application Server 與 Client 連線狀態",
            font=("Microsoft JhengHei", 13),
            text_color="#8b92a8"
        ).pack(anchor="w", pady=(5, 0))
        
        # 最後更新時間
        update_frame = ctk.CTkFrame(header, fg_color="transparent")
        update_frame.pack(side="right")
        
        ctk.CTkLabel(
            update_frame,
            text="最後更新",
            font=("Microsoft JhengHei", 11),
            text_color="#8b92a8"
        ).pack()
        
        self.last_update_label = ctk.CTkLabel(
            update_frame,
            text="--:--:--",
            font=("Microsoft JhengHei", 18, "bold"),
            text_color="white"
        )
        self.last_update_label.pack()
        
        # 狀態卡片區域
        cards_container = ctk.CTkFrame(main_container, fg_color="transparent")
        cards_container.pack(fill="x", padx=20, pady=(0, 20))
        
        # 三個狀態卡片
        self.ca_card = self.create_status_card(
            cards_container,
            "🏛️ CA Server",
            "ca_server",
            "#9b59b6"  # 紫色
        )
        self.ca_card.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        self.app_card = self.create_status_card(
            cards_container,
            "🏥 App Server",
            "app_server",
            "#3498db"  # 藍色
        )
        self.app_card.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        self.clients_card = self.create_clients_card(cards_container)
        self.clients_card.pack(side="left", fill="both", expand=True)
        
        # 下半部分 - 傳輸記錄和日誌
        bottom_container = ctk.CTkFrame(main_container, fg_color="transparent")
        bottom_container.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        # 即時傳輸記錄
        left_panel = ctk.CTkFrame(bottom_container, fg_color="#232936", corner_radius=15)
        left_panel.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        ctk.CTkLabel(
            left_panel,
            text="📊 即時傳輸記錄",
            font=("Microsoft JhengHei", 18, "bold"),
            text_color="white"
        ).pack(padx=20, pady=(20, 10), anchor="w")
        
        # 傳輸記錄容器（可滾動）
        self.transmission_container = ctk.CTkScrollableFrame(
            left_panel,
            fg_color="transparent"
        )
        self.transmission_container.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        
        # 系統日誌
        right_panel = ctk.CTkFrame(bottom_container, fg_color="#232936", corner_radius=15)
        right_panel.pack(side="right", fill="both", expand=True)
        
        ctk.CTkLabel(
            right_panel,
            text="📝 系統日誌",
            font=("Microsoft JhengHei", 18, "bold"),
            text_color="white"
        ).pack(padx=20, pady=(20, 10), anchor="w")
        
        self.log_text = ctk.CTkTextbox(
            right_panel,
            font=("Consolas", 11),
            fg_color="#1a1f2e",
            text_color="#8b92a8"
        )
        self.log_text.pack(fill="both", expand=True, padx=15, pady=(0, 15))
    
    def create_status_card(self, parent, title, server_id, accent_color):
        """創建狀態卡片"""
        card = ctk.CTkFrame(parent, fg_color="#232936", corner_radius=15)
        
        # 標題行
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 10))
        
        ctk.CTkLabel(
            header,
            text=title,
            font=("Microsoft JhengHei", 16, "bold"),
            text_color="white"
        ).pack(side="left")
        
        status_badge = ctk.CTkLabel(
            header,
            text="● 離線",
            font=("Microsoft JhengHei", 12),
            text_color="#95a5a6"
        )
        status_badge.pack(side="right")
        
        # CPU 使用率
        cpu_container = ctk.CTkFrame(card, fg_color="transparent")
        cpu_container.pack(fill="x", padx=20, pady=(5, 0))
        
        cpu_label_frame = ctk.CTkFrame(cpu_container, fg_color="transparent")
        cpu_label_frame.pack(fill="x")
        
        ctk.CTkLabel(
            cpu_label_frame,
            text="CPU 使用率",
            font=("Microsoft JhengHei", 12),
            text_color="#8b92a8"
        ).pack(side="left")
        
        cpu_value_label = ctk.CTkLabel(
            cpu_label_frame,
            text="0.0%",
            font=("Microsoft JhengHei", 12, "bold"),
            text_color="white"
        )
        cpu_value_label.pack(side="right")
        
        cpu_bar = ctk.CTkProgressBar(
            cpu_container,
            height=8,
            progress_color=accent_color
        )
        cpu_bar.set(0)
        cpu_bar.pack(fill="x", pady=(5, 0))
        
        # 記憶體使用率
        mem_container = ctk.CTkFrame(card, fg_color="transparent")
        mem_container.pack(fill="x", padx=20, pady=(10, 0))
        
        mem_label_frame = ctk.CTkFrame(mem_container, fg_color="transparent")
        mem_label_frame.pack(fill="x")
        
        ctk.CTkLabel(
            mem_label_frame,
            text="記憶體使用率",
            font=("Microsoft JhengHei", 12),
            text_color="#8b92a8"
        ).pack(side="left")
        
        mem_value_label = ctk.CTkLabel(
            mem_label_frame,
            text="0.0%",
            font=("Microsoft JhengHei", 12, "bold"),
            text_color="white"
        )
        mem_value_label.pack(side="right")
        
        mem_bar = ctk.CTkProgressBar(
            mem_container,
            height=8,
            progress_color=accent_color
        )
        mem_bar.set(0)
        mem_bar.pack(fill="x", pady=(5, 0))
        
        # 統計資訊
        stats_frame = ctk.CTkFrame(card, fg_color="transparent")
        stats_frame.pack(fill="x", padx=20, pady=(15, 20))
        
        stats_label = ctk.CTkLabel(
            stats_frame,
            text="請求數\n0",
            font=("Microsoft JhengHei", 11),
            text_color="#8b92a8",
            anchor="w"
        )
        stats_label.pack(side="left", fill="x", expand=True)
        
        # 儲存組件引用
        if not hasattr(self, 'ui_components'):
            self.ui_components = {}
        
        self.ui_components[server_id] = {
            'status_badge': status_badge,
            'cpu_bar': cpu_bar,
            'cpu_value': cpu_value_label,
            'mem_bar': mem_bar,
            'mem_value': mem_value_label,
            'stats': stats_label
        }
        
        return card
    
    def create_clients_card(self, parent):
        """創建客戶端卡片"""
        card = ctk.CTkFrame(parent, fg_color="#232936", corner_radius=15)
        
        # 標題行
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 10))
        
        ctk.CTkLabel(
            header,
            text="👥 Clients",
            font=("Microsoft JhengHei", 16, "bold"),
            text_color="white"
        ).pack(side="left")
        
        self.clients_count_label = ctk.CTkLabel(
            header,
            text="0/0",
            font=("Microsoft JhengHei", 20, "bold"),
            text_color="#2ecc71"
        )
        self.clients_count_label.pack(side="right")
        
        # 客戶端列表容器
        self.clients_list_container = ctk.CTkFrame(card, fg_color="transparent")
        self.clients_list_container.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        # 動態創建客戶端項目
        self.client_items = {}
        
        return card
    
    def add_client_item(self, client_id, client_name):
        """添加客戶端項目"""
        if client_id in self.client_items:
            return
        
        item_frame = ctk.CTkFrame(
            self.clients_list_container,
            fg_color="#1a1f2e",
            corner_radius=8
        )
        item_frame.pack(fill="x", pady=5)
        
        # 狀態指示器
        status_dot = ctk.CTkLabel(
            item_frame,
            text="●",
            font=("Microsoft JhengHei", 16),
            text_color="#95a5a6",
            width=30
        )
        status_dot.pack(side="left", padx=(10, 5))
        
        # 客戶端名稱
        name_label = ctk.CTkLabel(
            item_frame,
            text=client_name,
            font=("Microsoft JhengHei", 12, "bold"),
            text_color="white"
        )
        name_label.pack(side="left", padx=(0, 10))
        
        # 延遲顯示
        latency_label = ctk.CTkLabel(
            item_frame,
            text="-- ms",
            font=("Microsoft JhengHei", 11),
            text_color="#8b92a8"
        )
        latency_label.pack(side="right", padx=10, pady=10)
        
        self.client_items[client_id] = {
            'frame': item_frame,
            'status_dot': status_dot,
            'name': name_label,
            'latency': latency_label
        }
    
    def add_transmission_record(self, from_node, to_node, trans_type, status):
        """添加傳輸記錄"""
        # 創建傳輸記錄項目
        record = ctk.CTkFrame(
            self.transmission_container,
            fg_color="#1a1f2e",
            corner_radius=10
        )
        record.pack(fill="x", pady=5)
        
        # 左側 - 傳輸資訊
        left_frame = ctk.CTkFrame(record, fg_color="transparent")
        left_frame.pack(side="left", fill="both", expand=True, padx=15, pady=10)
        
        # 傳輸路徑
        path_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        path_frame.pack(anchor="w")
        
        ctk.CTkLabel(
            path_frame,
            text=from_node,
            font=("Microsoft JhengHei", 12, "bold"),
            text_color="white"
        ).pack(side="left")
        
        ctk.CTkLabel(
            path_frame,
            text=" → ",
            font=("Microsoft JhengHei", 12),
            text_color="#8b92a8"
        ).pack(side="left")
        
        ctk.CTkLabel(
            path_frame,
            text=to_node,
            font=("Microsoft JhengHei", 12, "bold"),
            text_color="white"
        ).pack(side="left")
        
        # 傳輸類型
        ctk.CTkLabel(
            left_frame,
            text=trans_type,
            font=("Microsoft JhengHei", 11),
            text_color="#8b92a8"
        ).pack(anchor="w", pady=(3, 0))
        
        # 右側 - 狀態和時間
        right_frame = ctk.CTkFrame(record, fg_color="transparent")
        right_frame.pack(side="right", padx=15, pady=10)
        
        # 狀態
        status_color = "#2ecc71" if status == "success" else "#e74c3c"
        status_text = "SUCCESS" if status == "success" else "FAILED"
        
        ctk.CTkLabel(
            right_frame,
            text=status_text,
            font=("Microsoft JhengHei", 11, "bold"),
            text_color=status_color
        ).pack(anchor="e")
        
        # 時間
        ctk.CTkLabel(
            right_frame,
            text=datetime.now().strftime("%H:%M:%S"),
            font=("Microsoft JhengHei", 10),
            text_color="#8b92a8"
        ).pack(anchor="e", pady=(3, 0))
        
        # 限制顯示的記錄數量
        records = self.transmission_container.winfo_children()
        if len(records) > 10:
            records[0].destroy()
        
        # 動畫效果 - 淡入
        record.configure(fg_color="#2c3e50")
        self.parent.after(100, lambda: record.configure(fg_color="#1a1f2e"))
    
    def fetch_endpoint_status(self, url):
        """獲取端點狀態"""
        try:
            response = requests.get(f"{url}/api/status", timeout=3)
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return None
    
    def update_monitoring_data(self):
        """更新監控數據（在背景執行緒中）"""
        while self.running:
            try:
                # 更新 CA Server
                if 'ca_server' in self.endpoints:
                    url = self.endpoints['ca_server']['url']
                    data = self.fetch_endpoint_status(url)
                    self.status_data['ca_server'] = data
                    self.update_server_ui('ca_server', data)
                
                # 更新 App Server
                if 'app_server' in self.endpoints:
                    url = self.endpoints['app_server']['url']
                    data = self.fetch_endpoint_status(url)
                    self.status_data['app_server'] = data
                    self.update_server_ui('app_server', data)
                
                # 更新 Clients
                if 'clients' in self.endpoints:
                    connected = 0
                    total = len(self.endpoints['clients'])
                    
                    for client in self.endpoints['clients']:
                        client_id = client.get('id', client['name'])
                        
                        # 確保客戶端項目存在
                        if client_id not in self.client_items:
                            self.parent.after(0, lambda cid=client_id, cn=client['name']: 
                                            self.add_client_item(cid, cn))
                            time.sleep(0.1)
                        
                        url = client['url']
                        data = self.fetch_endpoint_status(url)
                        self.status_data['clients'][client_id] = data
                        
                        if data:
                            connected += 1
                        
                        self.update_client_ui(client_id, data)
                    
                    # 更新客戶端計數
                    self.parent.after(0, lambda: self.clients_count_label.configure(
                        text=f"{connected}/{total}"
                    ))
                
                # 模擬傳輸記錄（實際應用中從伺服器獲取）
                import random
                if random.random() > 0.7:
                    trans_types = ["Certificate Request", "Data Transfer", "Heartbeat", "Authentication"]
                    nodes = ["CA", "Server", "Client 1", "Client 2"]
                    
                    from_node = random.choice(nodes)
                    to_node = random.choice([n for n in nodes if n != from_node])
                    trans_type = random.choice(trans_types)
                    status = "success" if random.random() > 0.1 else "failed"
                    
                    self.parent.after(0, lambda: self.add_transmission_record(
                        from_node, to_node, trans_type, status
                    ))
                    
                    self.log(f"{from_node} → {to_node}: {trans_type}")
                
                # 更新最後更新時間
                self.parent.after(0, self.update_last_update_time)
                
            except Exception as e:
                self.log(f"錯誤: {e}")
            
            time.sleep(2)  # 每2秒更新一次
    
    def update_server_ui(self, server_id, data):
        """更新伺服器 UI"""
        def _update():
            if server_id not in self.ui_components:
                return
            
            components = self.ui_components[server_id]
            
            if data:
                # 更新狀態
                components['status_badge'].configure(
                    text="● ACTIVE",
                    text_color="#2ecc71"
                )
                
                # 更新 CPU
                cpu = data.get('cpu', 0)
                components['cpu_bar'].set(cpu / 100)
                components['cpu_value'].configure(text=f"{cpu:.1f}%")
                
                # 更新記憶體
                memory = data.get('memory', 0)
                components['mem_bar'].set(memory / 100)
                components['mem_value'].configure(text=f"{memory:.1f}%")
                
                # 更新統計
                stats = data.get('stats', {})
                requests_count = stats.get('requests', 0)
                
                if server_id == 'ca_server':
                    certs = stats.get('certificates_issued', 0)
                    stats_text = f"憑證請求數\n{certs}"
                else:
                    conns = stats.get('connections', 0)
                    stats_text = f"活躍連線數\n{conns}"
                
                components['stats'].configure(text=stats_text)
            else:
                components['status_badge'].configure(
                    text="● 離線",
                    text_color="#95a5a6"
                )
        
        self.parent.after(0, _update)
    
    def update_client_ui(self, client_id, data):
        """更新客戶端 UI"""
        def _update():
            if client_id not in self.client_items:
                return
            
            item = self.client_items[client_id]
            
            if data:
                item['status_dot'].configure(text_color="#2ecc71")
                latency = data.get('latency', 0)
                item['latency'].configure(text=f"{latency} ms")
            else:
                item['status_dot'].configure(text_color="#95a5a6")
                item['latency'].configure(text="-- ms")
        
        self.parent.after(0, _update)
    
    def update_last_update_time(self):
        """更新最後更新時間"""
        current_time = datetime.now().strftime("%H:%M:%S")
        self.last_update_label.configure(text=current_time)
    
    def log(self, message):
        """添加日誌"""
        def _log():
            timestamp = datetime.now().strftime("%H:%M:%S")
            log_entry = f"[{timestamp}] [INFO] {message}\n"
            self.log_text.insert("end", log_entry)
            self.log_text.see("end")
            
            # 限制日誌行數
            lines = int(self.log_text.index('end-1c').split('.')[0])
            if lines > 100:
                self.log_text.delete("1.0", "2.0")
        
        self.parent.after(0, _log)
    
    def start_monitoring(self):
        """開始監控"""
        if not self.running:
            self.running = True
            self.update_thread = threading.Thread(
                target=self.update_monitoring_data,
                daemon=True
            )
            self.update_thread.start()
            self.log("✅ 監控已啟動")
    
    def stop_monitoring(self):
        """停止監控"""
        self.running = False
        if self.update_thread:
            self.update_thread.join(timeout=2)
        self.log("🛑 監控已停止")


# 測試用主程式
if __name__ == "__main__":
    import customtkinter as ctk
    
    ctk.set_appearance_mode("dark")
    
    root = ctk.CTk()
    root.title("傳輸監控測試")
    root.geometry("1200x800")
    
    endpoints = {
        'ca_server': {
            'url': 'http://localhost:9001',
            'name': 'CA Server'
        },
        'app_server': {
            'url': 'http://localhost:9002',
            'name': 'App Server'
        },
        'clients': [
            {'id': 'client1', 'url': 'http://localhost:9003', 'name': 'Client 1'},
            {'id': 'client2', 'url': 'http://localhost:9004', 'name': 'Client 2'},
            {'id': 'client3', 'url': 'http://localhost:9005', 'name': 'Client 3'},
            {'id': 'client4', 'url': 'http://localhost:9006', 'name': 'Client 4'},
            {'id': 'client5', 'url': 'http://localhost:9007', 'name': 'Client 5'}
        ]
    }
    
    tab = TransmissionMonitorTab(root, {'username': 'test'}, endpoints)
    
    root.mainloop()
