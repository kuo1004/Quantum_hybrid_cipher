#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ca_server.py - 憑證機構服務器（穩定版）
修正連線重置問題
"""

import os
import time
import json
import socket
import threading
from datetime import datetime
from certificate_authority import CertificateAuthority
import base64
import re


class DistributedCAServer:
    def __init__(self, host='localhost', port=8001):
        self.host = host
        self.port = port
        self.ca = CertificateAuthority("Taiwan_Medical_CA")
        self.running = False
        self.clients = []

    def start_server(self):
        """啟動CA服務器"""
        self.running = True
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.settimeout(1.0)  # 設置 timeout 讓 accept() 不會永久阻塞

        try:
            server_socket.bind((self.host, self.port))
            server_socket.listen(5)
            print(f"🏛️ CA服務器啟動: {self.host}:{self.port}")
            print(f"等待醫療機構連接...")
            print(f"💡 按 Ctrl+C 可結束程式\n")

            while self.running:
                try:
                    client_socket, address = server_socket.accept()
                    print(f"📋 新連接來自: {address}")

                    # 為每個客戶端創建處理線程
                    client_thread = threading.Thread(
                        target=self.handle_client, 
                        args=(client_socket, address)
                    )
                    client_thread.daemon = True
                    client_thread.start()

                except socket.timeout:
                    # timeout 是正常的，繼續循環檢查 self.running
                    continue
                except Exception as e:
                    if self.running:
                        print(f"❌ 接受連接錯誤: {e}")

        except Exception as e:
            print(f"❌ 服務器啟動失敗: {e}")
        finally:
            server_socket.close()
            print("✅ 服務器 socket 已關閉")

    def handle_client(self, client_socket, address):
        """處理 HTTP 請求，並根據 URL 進行路由"""
        try:
            # ⭐ 修正：增加接收緩衝區大小
            request_data = b""
            client_socket.settimeout(5.0)  # 設定超時
            
            # 接收完整請求
            while True:
                try:
                    chunk = client_socket.recv(8192)  # 增加緩衝區
                    if not chunk:
                        break
                    request_data += chunk
                    
                    # 檢查是否接收完整
                    if b'\r\n\r\n' in request_data:
                        # 如果是 POST，檢查 Content-Length
                        if request_data.startswith(b'POST'):
                            headers_end = request_data.find(b'\r\n\r\n')
                            headers = request_data[:headers_end].decode('utf-8', errors='ignore')
                            
                            # 查找 Content-Length
                            content_length = 0
                            for line in headers.split('\r\n'):
                                if line.lower().startswith('content-length:'):
                                    content_length = int(line.split(':')[1].strip())
                                    break
                            
                            # 檢查是否接收完整 body
                            body_start = headers_end + 4
                            body_received = len(request_data) - body_start
                            
                            if body_received >= content_length:
                                break
                        else:
                            break
                            
                except socket.timeout:
                    break
            
            if not request_data:
                return
            
            # 解碼請求
            request_text = request_data.decode('utf-8', errors='ignore')
            request_line = request_text.splitlines()[0] if request_text else ""
            print(f"📨 收到請求: {request_line}")
            
            # 路由處理
            if re.match(r'^GET /public_key HTTP/1\.[01]', request_line):
                self.handle_get_public_key(client_socket)
            
            elif (match := re.match(r'^GET /get_certificate/(\S+) HTTP/1\.[01]', request_line)):
                party_id = match.group(1)
                self.handle_get_certificate(client_socket, party_id)

            elif re.match(r'^POST /register HTTP/1\.[01]', request_line):
                self.handle_register(client_socket, request_text)

            else:
                print(f"❓ 無法識別的請求: {request_line}")
                self.send_response(client_socket, 400, b"Bad Request")

        except Exception as e:
            print(f"❌ 處理客戶端 {address} 錯誤: {e}")
            import traceback
            traceback.print_exc()
        finally:
            try:
                client_socket.close()
            except:
                pass

    def send_response(self, client_socket, status_code, body, content_type=b"text/plain"):
        """發送 HTTP 回應的輔助方法"""
        try:
            status_messages = {
                200: b"OK",
                400: b"Bad Request",
                404: b"Not Found",
                500: b"Internal Server Error"
            }
            
            status_message = status_messages.get(status_code, b"Unknown")
            
            if isinstance(body, str):
                body = body.encode('utf-8')
            
            headers = [
                f"HTTP/1.1 {status_code} {status_message.decode()}".encode('utf-8'),
                b"Content-Type: " + content_type,
                f"Content-Length: {len(body)}".encode('utf-8'),
                b"Connection: close",
                b"Server: IRIS-CA/1.0"
            ]
            
            response = b"\r\n".join(headers) + b"\r\n\r\n" + body
            client_socket.sendall(response)
            
        except Exception as e:
            print(f"❌ 發送回應錯誤: {e}")

    def handle_get_public_key(self, client_socket):
        """回傳 CA 的 PEM 格式公鑰"""
        print("✅ 處理請求: GET /public_key")
        
        try:
            public_key_pem = self.ca.get_ca_public_key_pem()
            self.send_response(client_socket, 200, public_key_pem, b"application/x-pem-file")
            print(f"✅ 已回傳公鑰 ({len(public_key_pem)} bytes)")
            
        except Exception as e:
            print(f"❌ 處理 /public_key 錯誤: {e}")
            self.send_response(client_socket, 500, b"Internal Server Error")

    def handle_get_certificate(self, client_socket, party_id):
        """回傳指定成員的 JSON 格式憑證"""
        print(f"✅ 處理請求: GET /get_certificate/{party_id}")
        
        try:
            if party_id in self.ca.issued_certificates:
                cert_data = self.ca.issued_certificates[party_id]
                response_body = json.dumps(cert_data).encode('utf-8')
                self.send_response(client_socket, 200, response_body, b"application/json")
                print(f"✅ 已回傳 {party_id} 的憑證")
            else:
                print(f"⚠️ 找不到 {party_id} 的憑證")
                self.send_response(client_socket, 404, b"Certificate not found")
            
        except Exception as e:
            print(f"❌ 處理 /get_certificate 錯誤: {e}")
            import traceback
            traceback.print_exc()
            self.send_response(client_socket, 500, b"Internal Server Error")

    def handle_register(self, client_socket, request_data):
        """處理註冊新成員的 POST 請求"""
        print("✅ 處理請求: POST /register")
        
        try:
            # 分離 HTTP 標頭和 Body
            try:
                headers, body = request_data.split('\r\n\r\n', 1)
            except ValueError:
                print("❌ 註冊請求缺少 Body")
                self.send_response(client_socket, 400, b"Missing request body")
                return

            # 解析 JSON Body
            try:
                data = json.loads(body)
            except json.JSONDecodeError as e:
                print(f"❌ JSON 解析錯誤: {e}")
                print(f"Body 前 200 字元: {body[:200]}")
                self.send_response(client_socket, 400, f"Invalid JSON: {str(e)}".encode())
                return
            
            # 提取註冊資料
            try:
                party_id = data['party_id']
                public_key_pem = data['public_key_pem'].encode('utf-8')
                kem_public_key = base64.b64decode(data['kem_public_key_b64'])
            except KeyError as e:
                print(f"❌ 缺少必要欄位: {e}")
                self.send_response(client_socket, 400, f"Missing field: {str(e)}".encode())
                return

            # 註冊並頒發憑證
            print(f"🔄 正在為 {party_id} 註冊並發行憑證...")
            certificate = self.ca.register_party(party_id, public_key_pem, kem_public_key)
            
            if certificate:
                print(f"✅ 已為 {party_id} 註冊並發行憑證")
                response_body = json.dumps(certificate).encode('utf-8')
                self.send_response(client_socket, 200, response_body, b"application/json")
            else:
                print(f"❌ 註冊 {party_id} 失敗")
                self.send_response(client_socket, 400, b"Registration failed")

        except Exception as e:
            print(f"❌ 處理註冊時發生錯誤: {e}")
            import traceback
            traceback.print_exc()
            self.send_response(client_socket, 500, f"Error: {str(e)}".encode())


def main():
    import sys

    # 解析命令列參數
    if len(sys.argv) == 2:
        host = 'localhost'
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"❌ 錯誤: Port 必須是數字，得到: {sys.argv[1]}")
            print("用法: python ca_server.py [port]")
            return
            
    elif len(sys.argv) >= 3:
        host = sys.argv[1]
        try:
            port = int(sys.argv[2])
        except ValueError:
            print(f"❌ 錯誤: Port 必須是數字，得到: {sys.argv[2]}")
            return
    else:
        host = 'localhost'
        port = 8001

    print("="*60)
    print("🏛️  台灣醫療憑證機構 (CA Server) - 穩定版")
    print("="*60)
    print(f"監聽位址: {host}:{port}")
    print(f"啟動時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    ca_server = DistributedCAServer(host, port)

    try:
        ca_server.start_server()
    except KeyboardInterrupt:
        print("\n" + "="*60)
        print("🛑 收到中斷信號 (Ctrl+C)，正在關閉服務器...")
        print("="*60)
        ca_server.running = False
        time.sleep(0.5)  # 給予一點時間讓線程完成
        print("✅ CA服務器已安全關閉")
        print("="*60)


if __name__ == "__main__":
    main()