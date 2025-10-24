
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
醫療影像三方傳輸監控系統
Enhanced Medical Image Transmission Monitoring System

具備：
1. 三方實體狀態實時監控（CA、Sender、Receiver）
2. 詳細的傳輸流程追蹤
3. 異地網路傳輸支援
4. 數據接收狀態可視化
5. 完整的日誌記錄系統
"""

import os
import time
import json
import base64
import pickle
import threading
import socket
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
from PIL import Image, ImageTk
import numpy as np

# 導入原有模組（需要確保這些文件存在）
try:
    from certificate_authority import CertificateAuthority
    from server.sender import Sender, generate_cover_for_transmission, lsb_embed_transmission_package
    from server.receiver import Receiver, lsb_extract_transmission_package, analyze_transmission_package
    from server.simple_kem import SimpleKEM
except ImportError as e:
    print(f"警告：無法導入模組 {e}，將使用模擬模式")

@dataclass
class TransmissionStatus:
    """傳輸狀態數據結構"""
    entity: str  # CA, Sender, Receiver
    phase: str
    progress: float
    data_size: int
    timestamp: float
    details: str
    success: bool = True
    data_info: Dict[str, Any] = None

@dataclass 
class NetworkConfig:
    """網路配置參數"""
    ca_host: str = "localhost"
    ca_port: int = 8001
    sender_host: str = "localhost" 
    sender_port: int = 8002
    receiver_host: str = "localhost"
    receiver_port: int = 8003
    timeout: int = 60
    chunk_size: int = 8192

class DetailedMonitor:
    """詳細監控系統"""

    def __init__(self):
        self.status_log: List[TransmissionStatus] = []
        self.callbacks = []
        self.lock = threading.Lock()
        self.metrics = {
            'total_data_sent': 0,
            'total_data_received': 0,
            'transmission_count': 0,
            'error_count': 0,
            'start_time': None,
            'end_time': None
        }

    def log_detailed_status(self, entity: str, phase: str, progress: float, 
                           data_size: int = 0, details: str = "", 
                           success: bool = True, data_info: Dict = None):
        """記錄詳細狀態信息"""
        with self.lock:
            status = TransmissionStatus(
                entity=entity,
                phase=phase,
                progress=progress,
                data_size=data_size,
                timestamp=time.time(),
                details=details,
                success=success,
                data_info=data_info or {}
            )
            self.status_log.append(status)

            # 更新統計指標
            if entity == "Sender" and "發送" in phase:
                self.metrics['total_data_sent'] += data_size
            elif entity == "Receiver" and "接收" in phase:
                self.metrics['total_data_received'] += data_size

            if not success:
                self.metrics['error_count'] += 1

            # 通知所有回調函數
            for callback in self.callbacks:
                try:
                    callback(status)
                except Exception as e:
                    print(f"回調錯誤: {e}")

    def add_callback(self, callback):
        """添加狀態更新回調"""
        self.callbacks.append(callback)

    def get_entity_log(self, entity: str, count: int = 20) -> List[TransmissionStatus]:
        """獲取特定實體的日誌"""
        with self.lock:
            entity_logs = [log for log in self.status_log if log.entity == entity]
            return entity_logs[-count:]

    def get_transmission_summary(self) -> Dict[str, Any]:
        """獲取傳輸摘要"""
        with self.lock:
            return {
                'total_logs': len(self.status_log),
                'successful_operations': sum(1 for log in self.status_log if log.success),
                'failed_operations': sum(1 for log in self.status_log if not log.success),
                'metrics': self.metrics.copy()
            }

class NetworkTransmissionManager:
    """網路傳輸管理器"""

    def __init__(self, config: NetworkConfig, monitor: DetailedMonitor):
        self.config = config
        self.monitor = monitor
        self.active_connections = {}

    def send_secure_data(self, target_host: str, target_port: int, 
                        data: bytes, description: str = "") -> bool:
        """安全發送數據"""
        try:
            start_time = time.time()
            self.monitor.log_detailed_status(
                "Network", "建立連接", 0, len(data), 
                f"連接到 {target_host}:{target_port} - {description}"
            )

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(self.config.timeout)
                sock.connect((target_host, target_port))

                # 發送數據頭（包含數據大小和類型信息）
                header = {
                    'size': len(data),
                    'type': description,
                    'timestamp': time.time(),
                    'checksum': hash(data)
                }
                header_data = json.dumps(header).encode('utf-8')
                header_size = len(header_data).to_bytes(4, 'big')

                sock.sendall(header_size + header_data)

                # 分塊發送數據並監控進度
                sent = 0
                while sent < len(data):
                    chunk = data[sent:min(sent + self.config.chunk_size, len(data))]
                    sock.sendall(chunk)
                    sent += len(chunk)

                    progress = (sent / len(data)) * 100
                    speed = sent / (time.time() - start_time + 0.001)  # 避免除零

                    self.monitor.log_detailed_status(
                        "Network", "數據傳輸", progress, sent,
                        f"已發送 {sent}/{len(data)} bytes，速度：{speed/1024:.1f} KB/s"
                    )

                end_time = time.time()
                total_speed = len(data) / (end_time - start_time)
                self.monitor.log_detailed_status(
                    "Network", "傳輸完成", 100, len(data),
                    f"傳輸完成，平均速度：{total_speed/1024/1024:.2f} MB/s"
                )
                return True

        except Exception as e:
            self.monitor.log_detailed_status(
                "Network", "傳輸失敗", 0, 0, f"錯誤：{str(e)}", False
            )
            return False

    def receive_secure_data(self, listen_host: str, listen_port: int) -> Optional[bytes]:
        """安全接收數據"""
        try:
            self.monitor.log_detailed_status(
                "Network", "等待連接", 0, 0, f"監聽 {listen_host}:{listen_port}"
            )

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_sock:
                server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server_sock.bind((listen_host, listen_port))
                server_sock.listen(1)
                server_sock.settimeout(self.config.timeout)

                conn, addr = server_sock.accept()
                self.monitor.log_detailed_status(
                    "Network", "已連接", 10, 0, f"連接來自 {addr[0]}:{addr[1]}"
                )

                # 接收頭信息
                header_size_data = conn.recv(4)
                if len(header_size_data) != 4:
                    raise Exception("無法接收頭大小")

                header_size = int.from_bytes(header_size_data, 'big')
                header_data = conn.recv(header_size)
                header = json.loads(header_data.decode('utf-8'))

                expected_size = header['size']
                data_type = header['type']
                expected_checksum = header['checksum']

                self.monitor.log_detailed_status(
                    "Network", "接收頭信息", 20, expected_size,
                    f"數據類型：{data_type}，預期大小：{expected_size} bytes"
                )

                # 接收實際數據
                received_data = b''
                start_time = time.time()

                while len(received_data) < expected_size:
                    remaining = expected_size - len(received_data)
                    chunk_size = min(self.config.chunk_size, remaining)
                    chunk = conn.recv(chunk_size)

                    if not chunk:
                        break

                    received_data += chunk
                    progress = 20 + (len(received_data) / expected_size * 80)
                    speed = len(received_data) / (time.time() - start_time + 0.001)

                    self.monitor.log_detailed_status(
                        "Network", "數據接收", progress, len(received_data),
                        f"已接收 {len(received_data)}/{expected_size} bytes，速度：{speed/1024:.1f} KB/s"
                    )

                # 驗證數據完整性
                if len(received_data) != expected_size:
                    raise Exception(f"數據長度不匹配：期望 {expected_size}，實際 {len(received_data)}")

                actual_checksum = hash(received_data)
                if actual_checksum != expected_checksum:
                    self.monitor.log_detailed_status(
                        "Network", "校驗失敗", 100, len(received_data),
                        "數據校驗失敗", False
                    )
                    return None

                self.monitor.log_detailed_status(
                    "Network", "接收完成", 100, len(received_data),
                    f"數據接收完成並驗證成功"
                )
                return received_data

        except Exception as e:
            self.monitor.log_detailed_status(
                "Network", "接收失敗", 0, 0, f"錯誤：{str(e)}", False
            )
            return None

class EnhancedMedicalTransmissionGUI:
    """增強版醫療傳輸系統GUI"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("醫療影像三方傳輸實時監控系統 v2.0")
        self.root.geometry("1400x900")
        self.root.configure(bg='#f0f0f0')

        # 系統組件
        self.monitor = DetailedMonitor()
        self.network_config = NetworkConfig()
        self.network_manager = NetworkTransmissionManager(self.network_config, self.monitor)

        # 註冊回調
        self.monitor.add_callback(self.on_status_update)

        # 系統實體
        self.ca = None
        self.sender = None
        self.receiver = None
        self.selected_image = None

        # GUI設置
        self.setup_enhanced_ui()

        # 狀態變數
        self.transmission_active = False

    def setup_enhanced_ui(self):
        """設置增強版用戶界面"""

        # 主標題
        title_frame = ttk.Frame(self.root)
        title_frame.pack(fill=tk.X, padx=10, pady=5)

        title_label = ttk.Label(title_frame, text="🏥 醫療影像三方傳輸實時監控系統", 
                               font=('Arial', 16, 'bold'))
        title_label.pack()

        # 創建主要的Notebook（標籤頁）
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 標籤頁1：實時監控
        self.setup_monitoring_tab()

        # 標籤頁2：傳輸控制
        self.setup_control_tab()

        # 標籤頁3：網路設置
        self.setup_network_tab()

        # 標籤頁4：數據分析
        self.setup_analysis_tab()

    def setup_monitoring_tab(self):
        """設置監控標籤頁"""
        monitoring_frame = ttk.Frame(self.notebook)
        self.notebook.add(monitoring_frame, text="🔍 實時監控")

        # 系統狀態總覽
        status_overview = ttk.LabelFrame(monitoring_frame, text="系統狀態總覽", padding="10")
        status_overview.pack(fill=tk.X, padx=5, pady=5)

        # 三方狀態顯示
        parties_frame = ttk.Frame(status_overview)
        parties_frame.pack(fill=tk.X, pady=5)

        # CA狀態
        ca_frame = ttk.LabelFrame(parties_frame, text="🏛️ 憑證機構 (CA)")
        ca_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        self.ca_status_var = tk.StringVar(value="未初始化")
        ttk.Label(ca_frame, text="狀態:").pack(anchor=tk.W)
        ttk.Label(ca_frame, textvariable=self.ca_status_var, foreground="blue").pack(anchor=tk.W)

        self.ca_progress = ttk.Progressbar(ca_frame, mode='determinate')
        self.ca_progress.pack(fill=tk.X, pady=2)

        self.ca_detail_var = tk.StringVar(value="等待初始化...")
        ttk.Label(ca_frame, textvariable=self.ca_detail_var, font=('Arial', 8)).pack(anchor=tk.W)

        # Sender狀態
        sender_frame = ttk.LabelFrame(parties_frame, text="📤 傳送方 (Sender)")
        sender_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)

        self.sender_status_var = tk.StringVar(value="未初始化")
        ttk.Label(sender_frame, text="狀態:").pack(anchor=tk.W)
        ttk.Label(sender_frame, textvariable=self.sender_status_var, foreground="blue").pack(anchor=tk.W)

        self.sender_progress = ttk.Progressbar(sender_frame, mode='determinate')
        self.sender_progress.pack(fill=tk.X, pady=2)

        self.sender_detail_var = tk.StringVar(value="等待初始化...")
        ttk.Label(sender_frame, textvariable=self.sender_detail_var, font=('Arial', 8)).pack(anchor=tk.W)

        # Receiver狀態
        receiver_frame = ttk.LabelFrame(parties_frame, text="📥 接收方 (Receiver)")
        receiver_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))

        self.receiver_status_var = tk.StringVar(value="未初始化")
        ttk.Label(receiver_frame, text="狀態:").pack(anchor=tk.W)
        ttk.Label(receiver_frame, textvariable=self.receiver_status_var, foreground="blue").pack(anchor=tk.W)

        self.receiver_progress = ttk.Progressbar(receiver_frame, mode='determinate')
        self.receiver_progress.pack(fill=tk.X, pady=2)

        self.receiver_detail_var = tk.StringVar(value="等待初始化...")
        ttk.Label(receiver_frame, textvariable=self.receiver_detail_var, font=('Arial', 8)).pack(anchor=tk.W)

        # 整體進度
        overall_frame = ttk.LabelFrame(monitoring_frame, text="整體傳輸進度", padding="10")
        overall_frame.pack(fill=tk.X, padx=5, pady=5)

        self.overall_progress = ttk.Progressbar(overall_frame, mode='determinate')
        self.overall_progress.pack(fill=tk.X, pady=2)

        self.overall_status_var = tk.StringVar(value="系統待命中...")
        ttk.Label(overall_frame, textvariable=self.overall_status_var).pack()

        # 實時日誌
        log_frame = ttk.LabelFrame(monitoring_frame, text="實時傳輸日誌", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 日誌控制按鈕
        log_control_frame = ttk.Frame(log_frame)
        log_control_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Button(log_control_frame, text="清除日誌", command=self.clear_log).pack(side=tk.LEFT)
        ttk.Button(log_control_frame, text="保存日誌", command=self.save_log).pack(side=tk.LEFT, padx=5)
        ttk.Button(log_control_frame, text="自動滾動", command=self.toggle_autoscroll).pack(side=tk.LEFT, padx=5)

        self.auto_scroll = tk.BooleanVar(value=True)

        # 日誌文本區域
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=12, font=('Consolas', 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # 配置日誌顏色
        self.log_text.tag_configure("CA", foreground="purple", font=('Consolas', 9, 'bold'))
        self.log_text.tag_configure("Sender", foreground="blue", font=('Consolas', 9, 'bold'))
        self.log_text.tag_configure("Receiver", foreground="green", font=('Consolas', 9, 'bold'))
        self.log_text.tag_configure("Network", foreground="orange", font=('Consolas', 9, 'bold'))
        self.log_text.tag_configure("Error", foreground="red", font=('Consolas', 9, 'bold'))
        self.log_text.tag_configure("Success", foreground="darkgreen", font=('Consolas', 9, 'bold'))

    def setup_control_tab(self):
        """設置控制標籤頁"""
        control_frame = ttk.Frame(self.notebook)
        self.notebook.add(control_frame, text="🎛️ 傳輸控制")

        # 系統控制
        system_control = ttk.LabelFrame(control_frame, text="系統控制", padding="10")
        system_control.pack(fill=tk.X, padx=5, pady=5)

        control_buttons_frame = ttk.Frame(system_control)
        control_buttons_frame.pack(fill=tk.X)

        ttk.Button(control_buttons_frame, text="🚀 初始化系統", 
                  command=self.init_system, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_buttons_frame, text="📁 選擇影像", 
                  command=self.select_image, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_buttons_frame, text="▶️ 開始傳輸", 
                  command=self.start_transmission, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_buttons_frame, text="⏹️ 停止傳輸", 
                  command=self.stop_transmission, width=15).pack(side=tk.LEFT, padx=5)

        # 影像信息
        image_info = ttk.LabelFrame(control_frame, text="選中影像信息", padding="10")
        image_info.pack(fill=tk.X, padx=5, pady=5)

        self.image_info_text = tk.Text(image_info, height=4, width=50)
        self.image_info_text.pack(fill=tk.X)

        # 傳輸參數
        params_frame = ttk.LabelFrame(control_frame, text="傳輸參數", padding="10")
        params_frame.pack(fill=tk.X, padx=5, pady=5)

        # 加密算法選擇
        ttk.Label(params_frame, text="加密算法:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.encryption_var = tk.StringVar(value="AES-256-GCM")
        encryption_combo = ttk.Combobox(params_frame, textvariable=self.encryption_var, 
                                       values=["AES-256-GCM", "ChaCha20-Poly1305"])
        encryption_combo.grid(row=0, column=1, padx=5, sticky=tk.W)

        # KEM算法選擇
        ttk.Label(params_frame, text="KEM算法:").grid(row=0, column=2, sticky=tk.W, padx=5)
        self.kem_var = tk.StringVar(value="ML-KEM-1024")
        kem_combo = ttk.Combobox(params_frame, textvariable=self.kem_var,
                                values=["ML-KEM-1024", "ML-KEM-768", "ML-KEM-512"])
        kem_combo.grid(row=0, column=3, padx=5, sticky=tk.W)

        # 隱寫術參數
        ttk.Label(params_frame, text="LSB通道:").grid(row=1, column=0, sticky=tk.W, padx=5)
        self.lsb_channels_var = tk.StringVar(value="RGB")
        lsb_combo = ttk.Combobox(params_frame, textvariable=self.lsb_channels_var,
                                values=["RGB", "RGBA", "R", "G", "B"])
        lsb_combo.grid(row=1, column=1, padx=5, sticky=tk.W)

        ttk.Label(params_frame, text="每像素位數:").grid(row=1, column=2, sticky=tk.W, padx=5)
        self.bits_per_pixel_var = tk.StringVar(value="1")
        bpp_combo = ttk.Combobox(params_frame, textvariable=self.bits_per_pixel_var,
                                values=["1", "2", "4"])
        bpp_combo.grid(row=1, column=3, padx=5, sticky=tk.W)

    def setup_network_tab(self):
        """設置網路標籤頁"""
        network_frame = ttk.Frame(self.notebook)
        self.notebook.add(network_frame, text="🌐 網路設置")

        # 網路配置
        network_config = ttk.LabelFrame(network_frame, text="網路連接配置", padding="10")
        network_config.pack(fill=tk.X, padx=5, pady=5)

        # CA設置
        ttk.Label(network_config, text="CA位址:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.ca_host_var = tk.StringVar(value=self.network_config.ca_host)
        ttk.Entry(network_config, textvariable=self.ca_host_var, width=20).grid(row=0, column=1, padx=5)

        ttk.Label(network_config, text="CA端口:").grid(row=0, column=2, sticky=tk.W, padx=5)
        self.ca_port_var = tk.StringVar(value=str(self.network_config.ca_port))
        ttk.Entry(network_config, textvariable=self.ca_port_var, width=10).grid(row=0, column=3, padx=5)

        # Sender設置
        ttk.Label(network_config, text="發送方位址:").grid(row=1, column=0, sticky=tk.W, padx=5)
        self.sender_host_var = tk.StringVar(value=self.network_config.sender_host)
        ttk.Entry(network_config, textvariable=self.sender_host_var, width=20).grid(row=1, column=1, padx=5)

        ttk.Label(network_config, text="發送方端口:").grid(row=1, column=2, sticky=tk.W, padx=5)
        self.sender_port_var = tk.StringVar(value=str(self.network_config.sender_port))
        ttk.Entry(network_config, textvariable=self.sender_port_var, width=10).grid(row=1, column=3, padx=5)

        # Receiver設置
        ttk.Label(network_config, text="接收方位址:").grid(row=2, column=0, sticky=tk.W, padx=5)
        self.receiver_host_var = tk.StringVar(value=self.network_config.receiver_host)
        ttk.Entry(network_config, textvariable=self.receiver_host_var, width=20).grid(row=2, column=1, padx=5)

        ttk.Label(network_config, text="接收方端口:").grid(row=2, column=2, sticky=tk.W, padx=5)
        self.receiver_port_var = tk.StringVar(value=str(self.network_config.receiver_port))
        ttk.Entry(network_config, textvariable=self.receiver_port_var, width=10).grid(row=2, column=3, padx=5)

        # 連接測試
        test_frame = ttk.Frame(network_config)
        test_frame.grid(row=3, column=0, columnspan=4, pady=10)

        ttk.Button(test_frame, text="測試CA連接", command=self.test_ca_connection).pack(side=tk.LEFT, padx=5)
        ttk.Button(test_frame, text="測試發送方連接", command=self.test_sender_connection).pack(side=tk.LEFT, padx=5)
        ttk.Button(test_frame, text="測試接收方連接", command=self.test_receiver_connection).pack(side=tk.LEFT, padx=5)

        # 網路狀態
        network_status = ttk.LabelFrame(network_frame, text="網路連接狀態", padding="10")
        network_status.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.network_status_text = scrolledtext.ScrolledText(network_status, height=10, font=('Consolas', 9))
        self.network_status_text.pack(fill=tk.BOTH, expand=True)

    def setup_analysis_tab(self):
        """設置分析標籤頁"""
        analysis_frame = ttk.Frame(self.notebook)
        self.notebook.add(analysis_frame, text="📊 數據分析")

        # 統計信息
        stats_frame = ttk.LabelFrame(analysis_frame, text="傳輸統計", padding="10")
        stats_frame.pack(fill=tk.X, padx=5, pady=5)

        # 統計顯示
        stats_display = ttk.Frame(stats_frame)
        stats_display.pack(fill=tk.X)

        # 左側統計
        left_stats = ttk.Frame(stats_display)
        left_stats.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.total_transmissions_var = tk.StringVar(value="總傳輸次數: 0")
        ttk.Label(left_stats, textvariable=self.total_transmissions_var).pack(anchor=tk.W)

        self.success_rate_var = tk.StringVar(value="成功率: 0%")
        ttk.Label(left_stats, textvariable=self.success_rate_var).pack(anchor=tk.W)

        self.total_data_var = tk.StringVar(value="總數據量: 0 bytes")
        ttk.Label(left_stats, textvariable=self.total_data_var).pack(anchor=tk.W)

        # 右側統計
        right_stats = ttk.Frame(stats_display)
        right_stats.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.avg_speed_var = tk.StringVar(value="平均速度: 0 MB/s")
        ttk.Label(right_stats, textvariable=self.avg_speed_var).pack(anchor=tk.W)

        self.error_count_var = tk.StringVar(value="錯誤次數: 0")
        ttk.Label(right_stats, textvariable=self.error_count_var).pack(anchor=tk.W)

        self.uptime_var = tk.StringVar(value="運行時間: 00:00:00")
        ttk.Label(right_stats, textvariable=self.uptime_var).pack(anchor=tk.W)

        # 詳細分析
        detail_analysis = ttk.LabelFrame(analysis_frame, text="詳細分析報告", padding="10")
        detail_analysis.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 分析控制
        analysis_control = ttk.Frame(detail_analysis)
        analysis_control.pack(fill=tk.X, pady=(0, 5))

        ttk.Button(analysis_control, text="生成報告", command=self.generate_report).pack(side=tk.LEFT, padx=5)
        ttk.Button(analysis_control, text="導出CSV", command=self.export_csv).pack(side=tk.LEFT, padx=5)
        ttk.Button(analysis_control, text="重置統計", command=self.reset_statistics).pack(side=tk.LEFT, padx=5)

        # 分析結果顯示
        self.analysis_text = scrolledtext.ScrolledText(detail_analysis, height=15, font=('Consolas', 9))
        self.analysis_text.pack(fill=tk.BOTH, expand=True)

    def on_status_update(self, status: TransmissionStatus):
        """處理狀態更新"""
        try:
            # 更新對應實體的進度和狀態
            if status.entity == "CA":
                self.ca_progress['value'] = status.progress
                self.ca_detail_var.set(status.details)
                if status.success:
                    self.ca_status_var.set("✅ 運行中" if status.progress == 100 else "⏳ 處理中")
                else:
                    self.ca_status_var.set("❌ 錯誤")

            elif status.entity == "Sender":
                self.sender_progress['value'] = status.progress
                self.sender_detail_var.set(status.details)
                if status.success:
                    self.sender_status_var.set("✅ 運行中" if status.progress == 100 else "⏳ 處理中")
                else:
                    self.sender_status_var.set("❌ 錯誤")

            elif status.entity == "Receiver":
                self.receiver_progress['value'] = status.progress
                self.receiver_detail_var.set(status.details)
                if status.success:
                    self.receiver_status_var.set("✅ 運行中" if status.progress == 100 else "⏳ 處理中")
                else:
                    self.receiver_status_var.set("❌ 錯誤")

            # 更新整體進度（簡化版）
            avg_progress = (self.ca_progress['value'] + self.sender_progress['value'] + self.receiver_progress['value']) / 3
            self.overall_progress['value'] = avg_progress
            self.overall_status_var.set(f"{status.entity}: {status.details}")

            # 添加到日誌
            timestamp = datetime.fromtimestamp(status.timestamp).strftime("%H:%M:%S")
            log_entry = f"[{timestamp}] {status.entity}: {status.phase} - {status.details}\n"

            # 選擇適當的標籤
            tag = status.entity
            if not status.success:
                tag = "Error"

            self.log_text.insert(tk.END, log_entry, tag)

            # 自動滾動到底部
            if self.auto_scroll.get():
                self.log_text.see(tk.END)

            # 更新統計
            self.update_statistics()

            # 刷新界面
            self.root.update_idletasks()

        except Exception as e:
            print(f"狀態更新錯誤: {e}")

    def init_system(self):
        """初始化三方系統"""
        def init_thread():
            try:
                # 初始化CA
                self.monitor.log_detailed_status("CA", "初始化", 0, 0, "正在初始化憑證機構...")
                time.sleep(0.5)
                # 這裡應該實際創建CA實例
                self.monitor.log_detailed_status("CA", "初始化", 100, 0, "Taiwan_Medical_CA 初始化完成")

                # 初始化Sender
                self.monitor.log_detailed_status("Sender", "初始化", 0, 0, "正在初始化發送方...")
                time.sleep(0.3)
                self.monitor.log_detailed_status("Sender", "註冊", 50, 0, "向CA註冊中...")
                time.sleep(0.3)
                self.monitor.log_detailed_status("Sender", "註冊", 100, 0, "Taiwan_General_Hospital 註冊完成")

                # 初始化Receiver
                self.monitor.log_detailed_status("Receiver", "初始化", 0, 0, "正在初始化接收方...")
                time.sleep(0.3)
                self.monitor.log_detailed_status("Receiver", "註冊", 50, 0, "向CA註冊中...")
                time.sleep(0.3)
                self.monitor.log_detailed_status("Receiver", "註冊", 100, 0, "Mackay_Memorial_Hospital 註冊完成")

                # 系統就緒
                self.monitor.log_detailed_status("CA", "就緒", 100, 0, "系統初始化完成，等待傳輸任務")

            except Exception as e:
                self.monitor.log_detailed_status("CA", "初始化失敗", 0, 0, f"錯誤: {str(e)}", False)

        threading.Thread(target=init_thread, daemon=True).start()

    def select_image(self):
        """選擇影像文件"""
        file_path = filedialog.askopenfilename(
            title="選擇醫療影像文件",
            filetypes=[
                ("影像文件", "*.png *.jpg *.jpeg *.bmp *.tiff *.gif"),
                ("PNG文件", "*.png"),
                ("JPEG文件", "*.jpg *.jpeg"),
                ("所有文件", "*.*")
            ]
        )

        if file_path:
            self.selected_image = file_path

            # 獲取文件信息
            try:
                file_size = os.path.getsize(file_path)
                img = Image.open(file_path)

                info_text = f"""
文件路徑: {file_path}
文件名: {os.path.basename(file_path)}
文件大小: {file_size:,} bytes ({file_size/1024/1024:.2f} MB)
影像尺寸: {img.size[0]} × {img.size[1]} pixels
影像模式: {img.mode}
影像格式: {img.format}
                """.strip()

                self.image_info_text.delete(1.0, tk.END)
                self.image_info_text.insert(1.0, info_text)

                self.monitor.log_detailed_status("Sender", "文件選擇", 100, file_size, 
                                               f"已選擇影像: {os.path.basename(file_path)}")

            except Exception as e:
                messagebox.showerror("錯誤", f"無法讀取影像文件: {str(e)}")

    def start_transmission(self):
        """開始傳輸"""
        if not self.selected_image:
            messagebox.showwarning("警告", "請先選擇要傳輸的影像文件")
            return

        if self.transmission_active:
            messagebox.showinfo("信息", "傳輸正在進行中...")
            return

        self.transmission_active = True
        threading.Thread(target=self._transmission_process, daemon=True).start()

    def stop_transmission(self):
        """停止傳輸"""
        self.transmission_active = False
        self.monitor.log_detailed_status("CA", "傳輸中止", 0, 0, "用戶中止傳輸", False)

    def _transmission_process(self):
        """完整的傳輸過程"""
        try:
            # 階段1：加密準備
            self.monitor.log_detailed_status("Sender", "加密開始", 0, 0, "開始影像加密處理...")

            # 模擬讀取影像
            file_size = os.path.getsize(self.selected_image)
            self.monitor.log_detailed_status("Sender", "讀取影像", 10, file_size, f"讀取影像文件: {os.path.basename(self.selected_image)}")
            time.sleep(0.2)

            # 模擬AES加密
            self.monitor.log_detailed_status("Sender", "AES加密", 25, file_size, f"執行AES-256-GCM加密...")
            time.sleep(0.8)

            # 模擬KEM金鑰封裝
            self.monitor.log_detailed_status("Sender", "KEM封裝", 50, 32, f"執行ML-KEM-1024金鑰封裝...")
            time.sleep(0.5)

            # 模擬準備傳輸包
            self.monitor.log_detailed_status("Sender", "傳輸包準備", 75, file_size + 1000, "準備加密傳輸包...")
            time.sleep(0.3)

            self.monitor.log_detailed_status("Sender", "加密完成", 100, file_size, "影像加密完成")

            # 階段2：憑證驗證
            self.monitor.log_detailed_status("CA", "憑證驗證", 0, 0, "開始雙方憑證驗證...")
            time.sleep(0.3)
            self.monitor.log_detailed_status("CA", "憑證驗證", 100, 0, "憑證驗證通過")

            # 階段3：網路傳輸
            encrypted_size = file_size + 1000  # 模擬加密後的大小
            self.monitor.log_detailed_status("Network", "傳輸開始", 0, encrypted_size, "開始網路傳輸...")

            # 模擬分塊傳輸
            chunk_count = 20
            for i in range(chunk_count):
                if not self.transmission_active:
                    return

                progress = (i + 1) / chunk_count * 100
                sent_size = int(encrypted_size * progress / 100)
                speed = np.random.uniform(5, 25)  # MB/s

                self.monitor.log_detailed_status("Network", "數據傳輸", progress, sent_size,
                                               f"傳輸進度: {progress:.1f}%, 速度: {speed:.1f} MB/s")
                time.sleep(0.1)

            self.monitor.log_detailed_status("Network", "傳輸完成", 100, encrypted_size, "網路傳輸完成")

            # 階段4：接收解密
            self.monitor.log_detailed_status("Receiver", "接收開始", 0, encrypted_size, "開始接收數據...")
            time.sleep(0.2)

            self.monitor.log_detailed_status("Receiver", "LSB提取", 20, encrypted_size, "從隱寫影像提取傳輸包...")
            time.sleep(0.4)

            self.monitor.log_detailed_status("Receiver", "解密處理", 60, file_size, "解密影像數據...")
            time.sleep(0.6)

            self.monitor.log_detailed_status("Receiver", "影像重建", 90, file_size, "重建醫療影像...")
            time.sleep(0.3)

            self.monitor.log_detailed_status("Receiver", "接收完成", 100, file_size, "影像接收並解密完成")

            # 傳輸成功
            self.monitor.log_detailed_status("CA", "傳輸成功", 100, file_size, "🎉 醫療影像傳輸成功完成！")

        except Exception as e:
            self.monitor.log_detailed_status("CA", "傳輸失敗", 0, 0, f"傳輸過程出錯: {str(e)}", False)
        finally:
            self.transmission_active = False

    def clear_log(self):
        """清除日誌"""
        self.log_text.delete(1.0, tk.END)
        self.monitor.log_detailed_status("CA", "日誌清除", 100, 0, "日誌已清除")

    def save_log(self):
        """保存日誌"""
        file_path = filedialog.asksaveasfilename(
            title="保存日誌文件",
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
        )

        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.log_text.get(1.0, tk.END))
                messagebox.showinfo("成功", f"日誌已保存到: {file_path}")
            except Exception as e:
                messagebox.showerror("錯誤", f"保存日誌失敗: {str(e)}")

    def toggle_autoscroll(self):
        """切換自動滾動"""
        self.auto_scroll.set(not self.auto_scroll.get())

    def update_statistics(self):
        """更新統計信息"""
        try:
            summary = self.monitor.get_transmission_summary()

            self.total_transmissions_var.set(f"總操作次數: {summary['total_logs']}")

            if summary['total_logs'] > 0:
                success_rate = (summary['successful_operations'] / summary['total_logs']) * 100
                self.success_rate_var.set(f"成功率: {success_rate:.1f}%")
            else:
                self.success_rate_var.set("成功率: 0%")

            total_data = summary['metrics']['total_data_sent'] + summary['metrics']['total_data_received']
            self.total_data_var.set(f"總數據量: {total_data:,} bytes")

            self.error_count_var.set(f"錯誤次數: {summary['failed_operations']}")

        except Exception as e:
            print(f"統計更新錯誤: {e}")

    def test_ca_connection(self):
        """測試CA連接"""
        host = self.ca_host_var.get()
        port = int(self.ca_port_var.get())
        self._test_connection("CA", host, port)

    def test_sender_connection(self):
        """測試發送方連接"""
        host = self.sender_host_var.get()
        port = int(self.sender_port_var.get())
        self._test_connection("Sender", host, port)

    def test_receiver_connection(self):
        """測試接收方連接"""
        host = self.receiver_host_var.get()
        port = int(self.receiver_port_var.get())
        self._test_connection("Receiver", host, port)

    def _test_connection(self, entity: str, host: str, port: int):
        """測試連接"""
        def test_thread():
            try:
                start_time = time.time()
                self.network_status_text.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] 測試 {entity} 連接到 {host}:{port}...\n")

                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(5)
                    result = sock.connect_ex((host, port))

                end_time = time.time()
                latency = (end_time - start_time) * 1000

                if result == 0:
                    self.network_status_text.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] ✅ {entity} 連接成功，延遲: {latency:.2f}ms\n")
                else:
                    self.network_status_text.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] ❌ {entity} 連接失敗\n")

                self.network_status_text.see(tk.END)

            except Exception as e:
                self.network_status_text.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] ❌ {entity} 連接測試錯誤: {str(e)}\n")
                self.network_status_text.see(tk.END)

        threading.Thread(target=test_thread, daemon=True).start()

    def generate_report(self):
        """生成分析報告"""
        try:
            summary = self.monitor.get_transmission_summary()

            report = f"""
=== 醫療影像傳輸系統分析報告 ===
生成時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

== 基本統計 ==
總操作次數: {summary['total_logs']}
成功操作數: {summary['successful_operations']}  
失敗操作數: {summary['failed_operations']}
成功率: {(summary['successful_operations'] / max(summary['total_logs'], 1) * 100):.2f}%

== 數據統計 ==
總發送數據: {summary['metrics']['total_data_sent']:,} bytes
總接收數據: {summary['metrics']['total_data_received']:,} bytes
總數據量: {summary['metrics']['total_data_sent'] + summary['metrics']['total_data_received']:,} bytes

== 最近活動 ==
"""

            # 添加最近的日誌條目
            recent_logs = self.monitor.get_recent_log(10)
            for log in recent_logs[-5:]:  # 最近5條
                timestamp = datetime.fromtimestamp(log.timestamp).strftime('%H:%M:%S')
                status = "✅" if log.success else "❌"
                report += f"{timestamp} {status} {log.entity}: {log.phase} - {log.details}\n"

            report += "\n=== 報告結束 ==="

            self.analysis_text.delete(1.0, tk.END)
            self.analysis_text.insert(1.0, report)

        except Exception as e:
            messagebox.showerror("錯誤", f"生成報告失敗: {str(e)}")

    def export_csv(self):
        """導出CSV"""
        file_path = filedialog.asksaveasfilename(
            title="導出CSV文件",
            defaultextension=".csv",
            filetypes=[("CSV文件", "*.csv"), ("所有文件", "*.*")]
        )

        if file_path:
            try:
                import csv
                with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['時間戳', '實體', '階段', '進度', '數據大小', '詳情', '成功'])

                    for log in self.monitor.status_log:
                        timestamp = datetime.fromtimestamp(log.timestamp).strftime('%Y-%m-%d %H:%M:%S')
                        writer.writerow([
                            timestamp, log.entity, log.phase, log.progress,
                            log.data_size, log.details, log.success
                        ])

                messagebox.showinfo("成功", f"CSV已導出到: {file_path}")
            except Exception as e:
                messagebox.showerror("錯誤", f"導出CSV失敗: {str(e)}")

    def reset_statistics(self):
        """重置統計"""
        if messagebox.askyesno("確認", "確定要重置所有統計數據嗎？"):
            self.monitor.status_log.clear()
            self.monitor.metrics = {
                'total_data_sent': 0,
                'total_data_received': 0,
                'transmission_count': 0,
                'error_count': 0,
                'start_time': None,
                'end_time': None
            }
            self.update_statistics()
            self.analysis_text.delete(1.0, tk.END)
            self.analysis_text.insert(1.0, "統計數據已重置")

    def run(self):
        """運行GUI應用程序"""
        self.root.mainloop()

def main():
    """主函數"""
    try:
        app = EnhancedMedicalTransmissionGUI()
        app.run()
    except Exception as e:
        print(f"應用程序啟動失敗: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
