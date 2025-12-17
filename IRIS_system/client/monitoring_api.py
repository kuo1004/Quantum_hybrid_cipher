#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
monitoring_api.py - 監控 API 模組
在現有 GUI 程式中啟動 HTTP Server 來提供監控數據
"""

import json
import threading
import psutil
import time
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse


class MonitoringMetrics:
    """收集系統指標的類別"""
    
    def __init__(self, server_name="Unknown", server_type="unknown"):
        self.server_name = server_name
        self.server_type = server_type  # "ca", "hospital", "client"
        self.start_time = time.time()
        
        # 統計數據
        self.stats = {
            'requests': 0,
            'connections': 0,
            'certificates_issued': 0,
            'images_uploaded': 0,
            'transmissions_sent': 0,
            'transmissions_received': 0,
            'errors': 0
        }
        
        self._lock = threading.Lock()
    
    def increment(self, key, value=1):
        """增加統計數據"""
        with self._lock:
            if key in self.stats:
                self.stats[key] += value
    
    def get_stats(self):
        """獲取統計數據"""
        with self._lock:
            return self.stats.copy()
    
    def get_cpu_usage(self):
        """獲取 CPU 使用率"""
        try:
            return psutil.cpu_percent(interval=0.1)
        except:
            return 0
    
    def get_memory_usage(self):
        """獲取記憶體使用率"""
        try:
            return psutil.virtual_memory().percent
        except:
            return 0
    
    def get_uptime(self):
        """獲取運行時間（秒）"""
        return time.time() - self.start_time
    
    def get_status_data(self):
        """獲取完整狀態數據"""
        stats = self.get_stats()
        
        return {
            'status': 'active',
            'server_name': self.server_name,
            'server_type': self.server_type,
            'cpu': self.get_cpu_usage(),
            'memory': self.get_memory_usage(),
            'uptime': self.get_uptime(),
            'timestamp': datetime.now().isoformat(),
            'stats': stats
        }


class MonitoringRequestHandler(BaseHTTPRequestHandler):
    """處理監控 API 請求"""
    
    def log_message(self, format, *args):
        """靜默日誌輸出"""
        pass
    
    def _send_json_response(self, data, status_code=200):
        """發送 JSON 回應"""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        
        json_data = json.dumps(data, ensure_ascii=False)
        self.wfile.write(json_data.encode('utf-8'))
    
    def do_OPTIONS(self):
        """處理 CORS preflight 請求"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_GET(self):
        """處理 GET 請求"""
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/api/health':
            # 健康檢查
            response = {
                'status': 'ok',
                'timestamp': datetime.now().isoformat(),
                'uptime': self.server.metrics.get_uptime(),
                'latency': 15
            }
            self._send_json_response(response)
        
        elif parsed_path.path == '/api/status':
            # 狀態資訊
            self.server.metrics.increment('requests')
            response = self.server.metrics.get_status_data()
            self._send_json_response(response)
        
        elif parsed_path.path == '/api/metrics':
            # 詳細指標
            stats = self.server.metrics.get_stats()
            
            try:
                memory = psutil.virtual_memory()
                cpu_count = psutil.cpu_count()
            except:
                memory = None
                cpu_count = 0
            
            response = {
                'cpu': {
                    'usage': self.server.metrics.get_cpu_usage(),
                    'cores': cpu_count
                },
                'memory': {
                    'total': memory.total if memory else 0,
                    'available': memory.available if memory else 0,
                    'usagePercent': self.server.metrics.get_memory_usage()
                },
                'stats': stats,
                'uptime': self.server.metrics.get_uptime()
            }
            self._send_json_response(response)
        
        else:
            self._send_json_response({'error': 'Not Found'}, 404)
    
    def do_POST(self):
        """處理 POST 請求"""
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/api/log':
            # 記錄日誌
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            
            try:
                data = json.loads(body)
                level = data.get('level', 'info')
                message = data.get('message', '')
                
                print(f"[{level.upper()}] {message}")
                
                self._send_json_response({
                    'success': True,
                    'timestamp': datetime.now().isoformat()
                })
            except Exception as e:
                self._send_json_response({'error': str(e)}, 400)
        
        else:
            self._send_json_response({'error': 'Not Found'}, 404)


class MonitoringServer:
    """監控 HTTP Server"""
    
    def __init__(self, port, server_name, server_type):
        self.port = port
        self.server_name = server_name
        self.server_type = server_type
        self.metrics = MonitoringMetrics(server_name, server_type)
        self.httpd = None
        self.thread = None
        self.running = False
    
    def start(self):
        """啟動監控服務器"""
        if self.running:
            return
        
        try:
            self.httpd = HTTPServer(('0.0.0.0', self.port), MonitoringRequestHandler)
            self.httpd.metrics = self.metrics
            
            self.running = True
            self.thread = threading.Thread(target=self._run_server, daemon=True)
            self.thread.start()
            
            print(f"📊 監控 API 已啟動: http://localhost:{self.port}")
            print(f"   健康檢查: http://localhost:{self.port}/api/health")
            print(f"   狀態資訊: http://localhost:{self.port}/api/status")
            
        except Exception as e:
            print(f"❌ 監控 API 啟動失敗: {e}")
            self.running = False
    
    def _run_server(self):
        """運行服務器的內部方法"""
        try:
            self.httpd.serve_forever()
        except Exception as e:
            print(f"❌ 監控服務器錯誤: {e}")
    
    def stop(self):
        """停止監控服務器"""
        if self.httpd and self.running:
            self.running = False
            self.httpd.shutdown()
            print("📊 監控 API 已停止")
    
    def get_metrics(self):
        """獲取指標對象"""
        return self.metrics


# 全局監控服務器實例
_monitoring_server = None


def start_monitoring(port, server_name, server_type):
    """啟動監控服務（全局函數）"""
    global _monitoring_server
    
    if _monitoring_server is None:
        _monitoring_server = MonitoringServer(port, server_name, server_type)
        _monitoring_server.start()
    
    return _monitoring_server


def stop_monitoring():
    """停止監控服務（全局函數）"""
    global _monitoring_server
    
    if _monitoring_server:
        _monitoring_server.stop()
        _monitoring_server = None


def get_metrics():
    """獲取監控指標（全局函數）"""
    global _monitoring_server
    
    if _monitoring_server:
        return _monitoring_server.get_metrics()
    return None


# 使用範例
if __name__ == "__main__":
    # 啟動監控
    monitoring = start_monitoring(
        port=9001,
        server_name="Test Server",
        server_type="test"
    )
    
    # 模擬一些活動
    metrics = get_metrics()
    if metrics:
        for i in range(10):
            metrics.increment('requests')
            metrics.increment('connections')
            time.sleep(1)
            
            status = metrics.get_status_data()
            print(f"CPU: {status['cpu']:.1f}% | Memory: {status['memory']:.1f}% | Requests: {status['stats']['requests']}")
    
    print("\n按 Enter 停止...")
    input()
    
    # 停止監控
    stop_monitoring()
