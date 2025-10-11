
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分散式憑證機構服務器 (CA Server)
可獨立運行，監聽網路連接
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

        try:
            server_socket.bind((self.host, self.port))
            server_socket.listen(5)
            print(f"🏛️ CA服務器啟動: {self.host}:{self.port}")
            print(f"等待醫療機構連接...")

            while self.running:
                try:
                    client_socket, address = server_socket.accept()
                    print(f"📋 新連接來自: {address}")

                    # 為每個客戶端創建處理線程
                    client_thread = threading.Thread(
                        target=self.handle_client, 
                        args=(client_socket, address)
                    )
                    client_thread.start()

                except Exception as e:
                    if self.running:
                        print(f"❌ 接受連接錯誤: {e}")

        except Exception as e:
            print(f"❌ 服務器啟動失敗: {e}")
        finally:
            server_socket.close()

    def handle_client(self, client_socket, address):
        """
        *** 核心修正點：處理 HTTP 請求，並根據 URL 進行路由 ***
        """
        try:
            request_data = client_socket.recv(4096).decode('utf-8', errors='ignore')
            if not request_data:
                return

            request_line = request_data.splitlines()[0]
            
            # 路由 1: 處理 GET /public_key
            if re.match(r'^GET /public_key HTTP/1\.[01]', request_line):
                self.handle_get_public_key(client_socket)
            
            # 路由 2: 處理 GET /get_certificate/<party_id>
            elif (match := re.match(r'^GET /get_certificate/(\S+) HTTP/1\.[01]', request_line)):
                party_id = match.group(1)
                self.handle_get_certificate(client_socket, party_id)

            # 路由 3: 處理 POST /register
            elif re.match(r'^POST /register HTTP/1\.[01]', request_line):
                self.handle_register(client_socket, request_data)

            else:
                print(f"❓ 無法識別的請求: {request_line}")
                client_socket.sendall(b"HTTP/1.1 400 Bad Request\r\n\r\n")

        except Exception as e:
            print(f"❌ 處理客戶端 {address} 錯誤: {e}")
        finally:
            print(f"📋 客戶端 {address} 斷開連接")
            client_socket.close()

    def handle_get_public_key(self, client_socket):
        """回傳 CA 的 PEM 格式公鑰"""
        print("處理請求: GET /public_key")
        public_key_pem = self.ca.get_ca_public_key_pem()
        headers = [
            b"HTTP/1.1 200 OK",
            b"Content-Type: application/x-pem-file",
            f"Content-Length: {len(public_key_pem)}".encode('utf-8'), # 將 str 編碼成 bytes
            b"Connection: close"
        ]
        
        # 組合回應
        response = b"\r\n".join(headers) + b"\r\n\r\n" + public_key_pem
        client_socket.sendall(response)

    def handle_get_certificate(self, client_socket, party_id):
        """回傳指定成員的 JSON 格式憑證"""
        print(f"處理請求: GET /get_certificate/{party_id}")
        if party_id in self.ca.issued_certificates:
            cert_data = self.ca.issued_certificates[party_id]
            response_body = json.dumps(cert_data).encode('utf-8')
            headers = [
                b"HTTP/1.1 200 OK",
                b"Content-Type: application/json",
                f"Content-Length: {len(response_body)}".encode('utf-8'),
                b"Connection: close"
            ]
            response = b"\r\n".join(headers) + b"\r\n\r\n" + response_body
        else:
            response = b"HTTP/1.1 404 Not Found\r\nConnection: close\r\n\r\n"
        client_socket.sendall(response)

        # 在 ca_server.py 的 DistributedCAServer class 中
    # --- 用下面這段程式碼，完整替換掉你現有的 handle_register 函數 ---

    def handle_register(self, client_socket, request_data):
        """處理註冊新成員的 POST 請求"""
        print("處理請求: POST /register")
        try:
            # *** 核心修正點：從原始請求數據中分離出 Body ***
            # HTTP 標頭和 Body 之間由一個空行 (\r\n\r\n) 分隔
            try:
                headers, body = request_data.split('\r\n\r\n', 1)
            except ValueError:
                # 如果請求中沒有 Body，會觸發此錯誤
                print("❌ 註冊請求缺少 Body。")
                client_socket.sendall(b"HTTP/1.1 400 Bad Request\r\n\r\n")
                return

            # 現在可以安全地解析 Body
            data = json.loads(body)
            
            party_id = data['party_id']
            public_key_pem = data['public_key_pem'].encode('utf-8')
            kem_public_key = base64.b64decode(data['kem_public_key_b64'])

            certificate = self.ca.register_party(party_id, public_key_pem, kem_public_key)
            
            if certificate:
                print(f"✅ 已為 {party_id} 註冊並發行憑證")
                response_body = json.dumps(certificate).encode('utf-8')
                
                # 組合一個標準的 HTTP 200 OK 回應
                headers = [
                    b"HTTP/1.1 200 OK",
                    b"Content-Type: application/json",
                    f"Content-Length: {len(response_body)}".encode('utf-8'),
                    b"Connection: close"
                ]
                response = b"\r\n".join(headers) + b"\r\n\r\n" + response_body
            else:
                response = b"HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\n"
            
            client_socket.sendall(response)

        except (json.JSONDecodeError, KeyError) as e:
            print(f"❌ 註冊請求 Body 格式錯誤或缺少欄位: {e}")
            client_socket.sendall(b"HTTP/1.1 400 Bad Request\r\n\r\n")
        except Exception as e:
            print(f"❌ 處理註冊時發生未知錯誤: {e}")
            client_socket.sendall(b"HTTP/1.1 500 Internal Server Error\r\n\r\n")



    def process_request(self, request, address):
        """處理具體請求"""
        try:
            action = request.get('action')

            if action == 'register':
                # 註冊醫療機構
                party_id = request.get('party_id')
                public_key_pem = request.get('public_key_pem').encode('utf-8')

                certificate = self.ca.register_party(party_id, public_key_pem)

                print(f"✅ 註冊成功: {party_id} from {address}")

                return {
                    'status': 'success',
                    'certificate': certificate,
                    'message': f'機構 {party_id} 註冊成功'
                }

            elif action == 'verify':
                # 驗證憑證
                party_id = request.get('party_id')
                certificate = request.get('certificate')

                is_valid = self.ca.verify_certificate(party_id, certificate)

                return {
                    'status': 'success',
                    'valid': is_valid,
                    'message': '憑證驗證完成'
                }

            elif action == 'list_parties':
                # 列出已註冊機構
                parties = list(self.ca.registered_parties.keys())
                return {
                    'status': 'success',
                    'parties': parties,
                    'count': len(parties)
                }

            else:
                return {
                    'status': 'error',
                    'message': f'未知操作: {action}'
                }

        except Exception as e:
            return {
                'status': 'error',
                'message': f'處理請求錯誤: {str(e)}'
            }

def main():
    import sys

    host = sys.argv[1] if len(sys.argv) > 1 else 'localhost'
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8001

    ca_server = DistributedCAServer(host, port)

    try:
        ca_server.start_server()
    except KeyboardInterrupt:
        print("\n🛑 CA服務器關閉")
        ca_server.running = False

    def handle_get_certificate(self, client_socket, party_id):
        """處理獲取憑證的請求"""
        if party_id in self.ca.issued_certificates:
            cert_data = self.ca.issued_certificates[party_id]
            response_body = json.dumps(cert_data).encode('utf-8')

            response = (
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: application/json\r\n"
                b"Content-Length: " + str(len(response_body)).encode('ascii') + b"\r\n"
                b"Connection: close\r\n\r\n"
            ) + response_body
        else:
            response = b"HTTP/1.1 404 Not Found\r\nConnection: close\r\n\r\n"

        client_socket.sendall(response)

    # 並且需要修改 handle_client 方法來解析這種 GET 請求
    # 將現有的 handle_client 方法整個替換成：
    def handle_client(self, client_socket):
        request_data = client_socket.recv(1024).decode('utf-8')
        print(f"CA 收到請求:\\n{request_data.splitlines()[0]}")

        # 解析 HTTP GET 請求
        match = re.match(r'GET /get_certificate/(\\S+) HTTP/1.1', request_data)
        if match:
            party_id = match.group(1)
            self.handle_get_certificate(client_socket, party_id)
        elif 'GET /public_key' in request_data:
            self.handle_get_public_key(client_socket)
        elif 'POST /register' in request_data:
            self.handle_register(client_socket, request_data)
        else:
            response = b"HTTP/1.1 400 Bad Request\\r\\nConnection: close\\r\\n\\r\\n"
            client_socket.sendall(response)
        
        client_socket.close()



if __name__ == "__main__":
    main()
