#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
接收端服務：LSB 封包提取 + 憑證驗證 + ML-KEM 解封 + AES-GCM 解密 + RSA-PSS 驗章 + 入庫
"""

import os
import time
import json
import socket
import threading
from datetime import datetime
import uuid
import pickle
import base64

import numpy as np
from PIL import Image

# CA 介面（統一用 get_ca_public_key_pem）
from certificate_authority import CertificateAuthority
# 已包含新版 receive_and_decrypt 的 Receiver
from .receiver import Receiver

# 本地資料庫
from GuiUser.database import connect_db


class FixedLSBReceiverServer:
    def __init__(self, host='127.0.0.1', port=8003, ca_host='127.0.0.1', ca_port=8001):
        self.host = host
        self.port = port
        self.ca_host = ca_host
        self.ca_port = ca_port

        self.receiver: Receiver | None = None
        self.running = False

        self.received_directory = "./medical_images_received"
        os.makedirs(self.received_directory, exist_ok=True)

        # 與 Sender 的互動（若有）
        self.sender_host = '127.0.0.1'
        self.sender_port = 8002

        # 下載記錄
        self.downloaded_files = set()
        self.download_history_file = ".download_history.json"
        self.load_download_history()

        # CA 公鑰
        self.ca_public_key_pem: bytes | None = None

    # ================== 啟動 ==================
    def start_server(self):
        print("🚀 Receiver Server 啟動中...")
        # 初始化 Receiver（會產生 RSA 與 KEM 金鑰）
        self.receiver = Receiver(receiver_id="HospitalReceiver")
        print("✅ Receiver 初始化完成")

        # 取得 CA 公鑰（統一方法名）
        self.register_with_ca()

        # 啟動 socket 監聽與背景抓取（保留）
        threading.Thread(target=self.start_network_service, daemon=True).start()
        threading.Thread(target=self.start_smart_fetch, daemon=True).start()

        print("\n" + "="*70)
        print("📥 Receiver 服務運行中…")
        print(f"💾 接收目錄: {os.path.abspath(self.received_directory)}")
        print("按 Ctrl+C 停止服務")
        print("="*70)

        try:
            self.running = True
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Receiver 服務關閉")
            self.running = False

    def register_with_ca(self):
        try:
            ca = CertificateAuthority("MedicalCA")
            # 統一這個名稱為 get_ca_public_key_pem
            self.ca_public_key_pem = ca.get_ca_public_key_pem()
            self.receiver.ca_public_key = self.ca_public_key_pem
            print("✅ 已取得 CA 公鑰")
        except Exception as e:
            print(f"⚠️ 取得 CA 公鑰失敗：{e}")
            self.ca_public_key_pem = None

    # ================== 與 Sender 互動骨架 ==================
    def start_smart_fetch(self):
        while True:
            try:
                self.check_for_new_images()
            except Exception as e:
                print(f"❌ 檢查新影像出錯: {e}")
            time.sleep(3)

    def check_for_new_images(self):
        # 你原本的掃描/拉取流程放這裡（保留占位）
        pass

    def download_and_process_image(self, filename: str):
        stego_path = filename
        original_filename = os.path.basename(filename)

        transmission_package = self.extract_with_multiple_methods(stego_path, original_filename)
        if not transmission_package:
            print(f"❌ 無法從 {filename} 取得傳輸包")
            return False

        return self.decrypt_transmission_package(transmission_package, original_filename)

    # ================== LSB 提取（標準 + 備援） ==================
    def extract_with_multiple_methods(self, stego_path, original_filename):
        pkg = self.try_standard_lsb_extract(stego_path, original_filename)
        if pkg:
            return pkg
        pkg = self.try_package_file_extract(stego_path, original_filename)
        if pkg:
            return pkg
        pkg = self.try_simple_steganography_check(stego_path, original_filename)
        return pkg

    def try_standard_lsb_extract(self, stego_path, original_filename):
        try:
            img = Image.open(stego_path).convert("RGB")
            arr = np.array(img)
            flat = arr.flatten()

            bpc = 1  # 每像素取幾個 LSB，可依你的設計調整
            header_bits = 64  # 8 bytes header
            header_symbols = self._extract_symbols_from_pixels(flat[: (header_bits // bpc) + 8], bpc)
            header_bytes = self._symbols_to_bytes(header_symbols, bpc)[:8]

            # 大端 → 小端 依序嘗試
            def _read_len(hb, endian):
                return int.from_bytes(hb, endian, signed=False)

            payload_length = _read_len(header_bytes, "big")
            capacity = (len(flat) * bpc) // 8
            if not (0 < payload_length <= capacity):
                payload_length = _read_len(header_bytes, "little")
                if not (0 < payload_length <= capacity):
                    print("❌ LSB 標頭不合理")
                    return None

            total_bits = (8 + payload_length) * 8
            pixels_needed = (total_bits + bpc - 1) // bpc
            if pixels_needed > len(flat):
                print("❌ 容量不足以承載 payload")
                return None

            all_symbols = self._extract_symbols_from_pixels(flat[:pixels_needed], bpc)
            all_bytes = self._symbols_to_bytes(all_symbols, bpc)
            payload_bytes = all_bytes[8 : 8 + payload_length]
            if len(payload_bytes) != payload_length:
                print("❌ 抽取長度不符")
                return None

            try:
                pkg = pickle.loads(payload_bytes)
                print("✅ 成功反序列化傳輸包")
                return pkg
            except Exception:
                try:
                    decoded = base64.b64decode(payload_bytes)
                    pkg = pickle.loads(decoded)
                    print("✅ Base64 解碼後反序列化成功")
                    return pkg
                except Exception as e:
                    print(f"❌ 反序列化失敗: {e}")
                    return None
        except Exception as e:
            print(f"❌ 標準 LSB 提取失敗：{e}")
            return None

    def _extract_symbols_from_pixels(self, pixels, bpc):
        mask = (1 << bpc) - 1
        return pixels & mask

    def _symbols_to_bytes(self, symbols, bpc):
        bits = []
        for s in symbols:
            for i in range(bpc - 1, -1, -1):
                bits.append((s >> i) & 1)
        out = []
        for i in range(0, len(bits), 8):
            if i + 8 <= len(bits):
                byte = 0
                for j, bit in enumerate(bits[i:i+8]):
                    byte |= (bit << (7 - j))
                out.append(byte)
        return bytes(out)

    def try_package_file_extract(self, stego_path, original_filename):
        try:
            base_name = os.path.basename(original_filename).split('.')[0]
            output_dir = "./medical_images_output"
            if not os.path.exists(output_dir):
                return False
            for fn in os.listdir(output_dir):
                if fn.startswith("package_") and fn.endswith(".pkl") and base_name in fn:
                    with open(os.path.join(output_dir, fn), "rb") as f:
                        return pickle.load(f)
            return False
        except Exception as e:
            print(f"❌ 備援包提取失敗：{e}")
            return False

    def try_simple_steganography_check(self, stego_path, original_filename):
        # 可依需求保留或移除，此處略
        return None

    # ================== 解密 + 驗章 + 入庫（關鍵） ==================
    def decrypt_transmission_package(self, transmission_package, original_filename):
        """
        解密傳輸包，驗證簽章，並將成功的結果存入資料庫。
        需要 sender.py 新封包格式：
          - enc_data: {ciphertext_b64, iv_b64, tag_b64, kem_alg, aes_key_encapsulated_b64}
          - signature: {alg, signature_b64}
          - app_meta: {...}
          - sender_cert_b64
        """
        try:
            if not self.receiver:
                print("❌ Receiver 尚未初始化")
                return False
            if not self.ca_public_key_pem:
                print("❌ 尚未取得 CA 公鑰，無法驗憑證")
                return False

            # 解密與驗章 → receiver.receive_and_decrypt 會做完整步驟
            # 同時把解密後的 raw 存一份到 received 目錄（方便除錯）
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            base = os.path.splitext(original_filename)[0]
            out_name = f"decrypted_{ts}_{base}.bin"
            out_path = os.path.join(self.received_directory, out_name)

            result = self.receiver.receive_and_decrypt(
                transmission_package,
                out_path,
                self.ca_public_key_pem
            )
            if not result:
                print("❌ 解密或驗章失敗")
                return False

            plaintext, app_meta = result
            print(f"✅ 解密與驗章成功：{len(plaintext)} bytes")

            if not self._store_in_database(plaintext, app_meta):
                print("❌ 寫入資料庫失敗")
                return False

            print("🎉 完成『接收→驗證→解密→入庫』")
            return True

        except Exception as e:
            print(f"❌ 解密流程出錯：{e}")
            import traceback; traceback.print_exc()
            return False

    def _store_in_database(self, plaintext_data: bytes, app_meta: dict) -> bool:
        """
        將解密後的明文與 meta 存入本地資料庫。
        注意：series_id 先用 1 示範，之後你提供 study/series 對應邏輯我再補。
        """
        try:
            conn = connect_db()
            cursor = conn.cursor()

            patient_id = app_meta.get('patient_id')
            uploader_id = app_meta.get('uploader_id')
            filename = app_meta.get('filename') or 'unknown.bin'
            mime_type = app_meta.get('mime') or 'application/octet-stream'
            file_size = app_meta.get('size_bytes') or len(plaintext_data)

            if not patient_id or not uploader_id:
                print("❌ 缺少 patient_id 或 uploader_id")
                conn.close()
                return False

            series_id = 1
            sop_instance_uid = f"1.2.826.0.1.{uuid.uuid4().int}"

            cursor.execute("""
                INSERT INTO dicom_instances
                (series_id, uploader_id, sop_instance_uid, original_data, mime_type, filename, file_size)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (series_id, uploader_id, sop_instance_uid, plaintext_data, mime_type, filename, file_size))

            conn.commit()
            conn.close()
            print(f"✅ 已將 '{filename}' 存入資料庫")
            return True
        except Exception as e:
            print(f"❌ 資料庫寫入失敗：{e}")
            import traceback; traceback.print_exc()
            return False

    # ================== 網路監聽（保留你的查詢介面） ==================
    def start_network_service(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server_socket.bind((self.host, self.port))
            server_socket.listen(5)
            print(f"📡 監聽: {self.host}:{self.port}")
            while True:
                client_socket, addr = server_socket.accept()
                threading.Thread(target=self.handle_connection, args=(client_socket, addr), daemon=True).start()
        except Exception as e:
            print(f"❌ 網路服務啟動失敗: {e}")
        finally:
            server_socket.close()

    def handle_connection(self, client_socket, address):
        try:
            req = client_socket.recv(2048)
            if not req:
                client_socket.close()
                return
            # 這裡可擴充 get_status / get_image_secure 等動作
            client_socket.send(json.dumps({"status":"running"}).encode("utf-8"))
        except Exception as e:
            print(f"❌ 連線處理錯誤: {e}")
        finally:
            client_socket.close()

    # ================== 下載紀錄 ==================
    def load_download_history(self):
        try:
            if os.path.exists(self.download_history_file):
                with open(self.download_history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.downloaded_files = set(data.get('files', []))
            else:
                self.downloaded_files = set()
        except Exception as e:
            print(f"⚠️ 下載紀錄讀取失敗: {e}")
            self.downloaded_files = set()

    def save_download_history(self):
        try:
            with open(self.download_history_file, 'w', encoding='utf-8') as f:
                json.dump({'files': list(self.downloaded_files)}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ 下載紀錄儲存失敗: {e}")


def main():
    import sys
    host = sys.argv[1] if len(sys.argv) > 1 else '127.0.0.1'
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8003
    ca_host = sys.argv[3] if len(sys.argv) > 3 else '127.0.0.1'
    ca_port = int(sys.argv[4]) if len(sys.argv) > 4 else 8001

    server = FixedLSBReceiverServer(host, port, ca_host, ca_port)
    server.start_server()


if __name__ == "__main__":
    main()