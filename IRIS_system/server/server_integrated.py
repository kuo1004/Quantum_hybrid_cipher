#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
server_integrated.py - IRIS 醫療影像傳輸系統 Server 端
整合 Receiver, Sender, Database 的完整 API 服務

功能:
1. 接收加密影像 (POST /upload)
2. 處理影像下載請求 (POST /request_image)
3. 列出影像清單 (GET /list_images)
4. 健康檢查 (GET /health)
5. CA 憑證管理
"""

import os
import sys
import time
import json
import base64
import pickle
import requests
from datetime import datetime
from flask import Flask, request, jsonify, send_file
from io import BytesIO
from PIL import Image

# 本地模組
from receiver import Receiver
from sender import Sender
from IRIS_database import (
    connect_db, insert_image_upload, get_image_data, init_database,
    get_user_by_username, log_audit
)
from certificate_authority import CertificateAuthority
from kem import SimpleKEM

# Flask App
app = Flask(__name__)

# 全域變數
receiver = None
sender = None
ca = None
ca_host = None
ca_port = None


def connect_to_remote_ca(host, port):
    """連接到遠端 CA Server"""
    try:
        # 測試連接
        response = requests.get(f"http://{host}:{port}/public_key", timeout=5)
        
        if response.status_code == 200:
            print(f"✅ 成功連接到遠端 CA: {host}:{port}")
            return True
        else:
            print(f"⚠️ CA Server 回應異常: HTTP {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"⚠️ 無法連接到 CA Server ({host}:{port})")
        return False
    except Exception as e:
        print(f"⚠️ 連接 CA 時發生錯誤: {e}")
        return False


def register_with_remote_ca(entity, host, port):
    """向遠端 CA 註冊並獲取憑證"""
    try:
        # 準備註冊資料
        public_key_pem = entity.get_public_key_pem().decode('utf-8')
        kem_public_key_b64 = base64.b64encode(entity.kem_public_key).decode('utf-8')
        
        register_data = {
            "party_id": entity.receiver_id if hasattr(entity, 'receiver_id') else entity.sender_id,
            "public_key_pem": public_key_pem,
            "kem_public_key_b64": kem_public_key_b64
        }
        
        print(f"   註冊資料: {register_data['party_id']}")
        
        # ========== 修正 1: 使用正確的端點 ==========
        # 發送註冊請求（使用正確的端點）
        response = requests.post(
            f"http://{host}:{port}/register",  # ← 修正：使用 /register_certificate
            json=register_data,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        print(f"   CA 回應: HTTP {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            
            # ========== 修正 2: 處理不同的回應格式 ==========
            # 檢查回應格式
            if 'certificate' in result:
                certificate = result['certificate']
            elif 'status' in result and result['status'] == 'success':
                certificate = result
            else:
                certificate = result
            
            print(f"   ✅ 成功向 CA 註冊: {register_data['party_id']}")
            print(f"   📊 憑證類型: {type(certificate)}")
            
            return certificate
        else:
            print(f"   ❌ CA 註冊失敗: HTTP {response.status_code}")
            print(f"   回應: {response.text[:200]}")
            return None
            
    except requests.exceptions.ConnectionError:
        print(f"   ❌ 無法連接到 CA Server ({host}:{port})")
        return None
    except requests.exceptions.Timeout:
        print(f"   ❌ 連接 CA 逾時")
        return None
    except Exception as e:
        print(f"   ❌ 註冊到 CA 時發生錯誤: {e}")
        import traceback
        traceback.print_exc()
        return None


def get_ca_public_key(host, port):
    """從遠端 CA 獲取公鑰"""
    try:
        response = requests.get(f"http://{host}:{port}/public_key", timeout=5)
        
        if response.status_code == 200:
            ca_public_key_pem = response.content
            print(f"✅ 成功獲取 CA 公鑰 ({len(ca_public_key_pem)} bytes)")
            return ca_public_key_pem
        else:
            print(f"❌ 獲取 CA 公鑰失敗: HTTP {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ 獲取 CA 公鑰時發生錯誤: {e}")
        return None


def init_server(server_ca_host, server_ca_port):
    """初始化 Server"""
    global receiver, sender, ca, ca_host, ca_port
    
    print("="*70)
    print("🏥 IRIS 醫療影像傳輸系統 - Server 端")
    print("="*70)
    
    ca_host = server_ca_host
    ca_port = server_ca_port
    
    # 步驟 1: 初始化資料庫
    print("\n📋 步驟 1: 初始化資料庫")
    try:
        init_database()
    except Exception as e:
        print(f"⚠️ 資料庫初始化警告: {e}")
    
    # 步驟 2: 創建 Receiver 和 Sender
    print("\n📋 步驟 2: 創建 Receiver 和 Sender")
    receiver = Receiver("Hospital_Server_Receiver")
    sender = Sender("Hospital_Server_Sender")
    
    # 步驟 3: 連接 CA 或創建本地 CA
    print("\n📋 步驟 3: 連接憑證機構 (CA)")
    
    if connect_to_remote_ca(ca_host, ca_port):
        print(f"✅ 使用遠端 CA: {ca_host}:{ca_port}")
        
        # 獲取 CA 公鑰
        ca_public_key_pem = get_ca_public_key(ca_host, ca_port)
        if not ca_public_key_pem:
            print("❌ 無法獲取 CA 公鑰，Server 初始化失敗")
            sys.exit(1)
        
        # 設定 CA 公鑰
        receiver.ca_public_key_pem = ca_public_key_pem
        sender.ca_public_key_pem = ca_public_key_pem
        
    
        # 向 CA 註冊 Receiver（加強版本）
        print("\n📋 步驟 3.1: 向 CA 註冊 Receiver")
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            print(f"   嘗試 {retry_count + 1}/{max_retries}...")
            receiver.certificate = register_with_remote_ca(receiver, ca_host, ca_port)
            
            if receiver.certificate:
                print(f"   ✅ Receiver 註冊成功")
                print(f"   📊 憑證類型: {type(receiver.certificate)}")
                
                # 驗證憑證內容
                if isinstance(receiver.certificate, dict):
                    if 'signature' in receiver.certificate and receiver.certificate['signature']:
                        print(f"   ✅ 憑證包含 CA 簽章")
                   # else:
                       # print(f"   ⚠️ 憑證缺少簽章")
                break
            else:
                print(f"   ❌ 註冊失敗，{2 if retry_count < max_retries-1 else 0} 秒後重試...")
                retry_count += 1
                if retry_count < max_retries:
                    import time
                    time.sleep(2)
        
        if not receiver.certificate:
            print("\n" + "="*70)
            print("❌ Receiver CA 註冊失敗")
            print("="*70)
            print("可能原因：")
            print("1. CA Server 未正確啟動")
            print("2. CA 註冊 API 有問題")
            print("3. 網路連線問題")
            print("\n請檢查 CA Server 日誌，並確認:")
            print(f"   curl http://{ca_host}:{ca_port}/public_key")
            print("="*70)
            sys.exit(1)
        
        # 向 CA 註冊 Sender
        print("\n📋 步驟 3.2: 向 CA 註冊 Sender")
        retry_count = 0
        
        while retry_count < max_retries:
            print(f"   嘗試 {retry_count + 1}/{max_retries}...")
            sender.certificate = register_with_remote_ca(sender, ca_host, ca_port)
            
            if sender.certificate:
                print(f"   ✅ Sender 註冊成功")
                break
            else:
                print(f"   ❌ 註冊失敗，{2 if retry_count < max_retries-1 else 0} 秒後重試...")
                retry_count += 1
                if retry_count < max_retries:
                    import time
                    time.sleep(2)
        
        if not sender.certificate:
            print("❌ Sender CA 註冊失敗，Server 初始化失敗")
            sys.exit(1)
            
    else:
        print(f"⚠️ 無法連接到遠端 CA，創建本地 CA")
        ca = CertificateAuthority("Local_Medical_CA")
        
        # 本地註冊
        receiver.register_with_ca(ca)
        sender.register_with_ca(ca)
    
    print("\n" + "="*70)
    print("✅ Server 初始化完成")
    print("="*70)
    print(f"📥 Receiver ID: {receiver.receiver_id}")
    print(f"📤 Sender ID: {sender.sender_id}")
    print(f"🏛️ CA: {ca_host}:{ca_port}" if not ca else "🏛️ CA: 本地 CA")
    print("="*70 + "\n")


# ============================================================
# API 端點
# ============================================================

@app.route('/health', methods=['GET'])
def health_check():
    """健康檢查端點"""
    try:
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM image_uploads")
        image_count = cursor.fetchone()[0]
        conn.close()
        
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "receiver_id": receiver.receiver_id if receiver else None,
            "sender_id": sender.sender_id if sender else None,
            "ca_mode": "remote" if not ca else "local",
            "ca_address": f"{ca_host}:{ca_port}" if not ca else "local",
            "database": {
                "connected": True,
                "image_count": image_count
            }
        })
        
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "error": str(e)
        }), 500


@app.route('/upload', methods=['POST'])
def upload_image():
    """接收加密影像封包"""
    try:
        print(f"\n{'='*70}")
        print(f"📥 收到上傳請求 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}")
        
        data = request.get_json()
        
        if not data or 'transmission_package' not in data:
            return jsonify({
                "status": "error",
                "message": "缺少 transmission_package"
            }), 400
        
        transmission_package = data['transmission_package']
        
        print("\n📋 傳輸封包資訊:")
        print(f"   發送方: {transmission_package.get('sender_id', 'Unknown')}")
        print(f"   接收方: {transmission_package.get('receiver_id', 'Unknown')}")
        
        temp_output = f"/tmp/received_image_{int(time.time())}.dat"
        
        print("\n🔓 開始解密...")
        result = receiver.receive_and_decrypt(
            transmission_package,
            output_file_path=temp_output,
            ca_public_key_pem=receiver.ca_public_key_pem
        )
        
        if not result:
            return jsonify({
                "status": "error",
                "message": "解密失敗"
            }), 400
        
        plaintext, app_meta = result
        print(f"✅ 解密成功: {len(plaintext)} bytes")
        
        required_fields = ['patient_id', 'uploader_id', 'filename', 'mime']
        for field in required_fields:
            if field not in app_meta:
                return jsonify({
                    "status": "error",
                    "message": f"缺少必要欄位: {field}"
                }), 400
        
        print("\n💾 寫入資料庫...")
        image_id = insert_image_upload(
            patient_id=app_meta['patient_id'],
            uploader_id=app_meta['uploader_id'],
            filename=app_meta['filename'],
            mime=app_meta['mime'],
            imagedata=plaintext,
            #thumbdata=app_meta.get('thumbdata')
        )
        
        if not image_id:
            return jsonify({
                "status": "error",
                "message": "資料庫寫入失敗"
            }), 500
        
        if os.path.exists(temp_output):
            os.remove(temp_output)
        
        print(f"\n✅ 上傳完成 - Image ID: {image_id}\n")
        
        return jsonify({
            "status": "success",
            "image_id": image_id,
            "message": "影像上傳成功",
            "details": {
                "filename": app_meta['filename'],
                "size": len(plaintext),
                "patient_id": app_meta['patient_id']
            }
        })
        
    except Exception as e:
        print(f"\n❌ 上傳失敗: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/request_image', methods=['POST'])
def request_image():
    """處理影像下載請求"""
    try:
        print(f"\n{'='*70}")
        print(f"📤 收到下載請求 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}")
        
        data = request.get_json()
        
        if not data or 'image_id' not in data or 'requester_certificate' not in data:
            return jsonify({
                "status": "error",
                "message": "缺少必要參數"
            }), 400
        
        image_id = data['image_id']
        requester_certificate = data['requester_certificate']
        
        print(f"\n📋 影像 ID: {image_id}")
        print("\n🔐 驗證請求者憑證...")
        
        if not sender.verify_peer_certificate(requester_certificate, sender.ca_public_key_pem):
            return jsonify({
                "status": "error",
                "message": "憑證驗證失敗"
            }), 403
        
        print("✅ 憑證驗證成功")
        print("\n📂 從資料庫讀取影像...")
        
        imagedata, thumbdata, mime = get_image_data(image_id)
        
        if not imagedata:
            return jsonify({
                "status": "error",
                "message": "找不到影像"
            }), 404
        
        print(f"✅ 讀取成功: {len(imagedata)} bytes")
        
        app_meta = {
            "image_id": image_id,
            "mime": mime,
            "size": len(imagedata),
            "timestamp": time.time()
        }
        
        print("\n✍️ 簽署資料...")
        from signature_utils import sign_bytes
        signature = sign_bytes(sender.private_key, imagedata)
        
        print("\n🔒 加密資料...")
        transmission_package = sender.encrypt_and_prepare_transmission(
            plaintext_bytes=imagedata,
            receiver_certificate=requester_certificate,
            signature=signature,
            app_meta=app_meta
        )
        
        print(f"\n✅ 下載準備完成\n")
        
        return jsonify({
            "status": "success",
            "transmission_package": transmission_package
        })
        
    except Exception as e:
        print(f"\n❌ 下載請求處理失敗: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/list_images', methods=['GET'])
def list_images():
    """
    列出影像清單（修正版）
    """
    try:
        patient_id = request.args.get('patient_id')
        clinical_dept_id = request.args.get('clinical_dept_id')
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))
        
        print(f"📋 列出影像請求: patient_id={patient_id}, clinical_dept_id={clinical_dept_id}")
        
        conn = connect_db()
        cursor = conn.cursor()
        
        # 基本查詢
        query = """
            SELECT 
                i.id, i.filename, i.patient_id,
                i.clinical_dept_id, i.modality_dept_id,
                i.uploader_id, i.file_type, i.mime_type,
                i.file_size, i.upload_time,
                p.name as patient_name,
                u.username as uploader_name,
                cd.name as clinical_dept_name,
                md.name as modality_dept_name
            FROM image_uploads i
            LEFT JOIN patients p ON i.patient_id = p.id
            LEFT JOIN users u ON i.uploader_id = u.id
            LEFT JOIN clinical_departments cd ON i.clinical_dept_id = cd.id
            LEFT JOIN modality_departments md ON i.modality_dept_id = md.id
        """
        
        # 動態添加 WHERE 條件
        conditions = []
        params = []
        
        if patient_id:
            conditions.append("i.patient_id = ?")
            params.append(patient_id)
        
        if clinical_dept_id:
            conditions.append("i.clinical_dept_id = ?")
            params.append(clinical_dept_id)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        # 排序和分頁
        query += " ORDER BY i.upload_time DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        images = []
        for row in rows:
            images.append({
                'id': row[0],
                'filename': row[1],
                'patient_id': row[2],
                'clinical_dept_id': row[3],
                'modality_dept_id': row[4],
                'uploader_id': row[5],
                'file_type': row[6],
                'mime_type': row[7],
                'file_size': row[8],
                'upload_time': row[9],
                'patient_name': row[10],
                'uploader_name': row[11],
                'clinical_dept_name': row[12],
                'modality_dept_name': row[13]
            })
        
        conn.close()
        
        print(f"✅ 成功列出 {len(images)} 張影像")
        
        return jsonify({
            'status': 'success',
            'images': images,
            'total': len(images)
        })
        
    except Exception as e:
        print(f"❌ 列出影像失敗: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/stats', methods=['GET'])
def get_stats():
    """獲取系統統計資訊"""
    try:
        conn = connect_db()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM image_uploads")
        total_images = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT patient_id) FROM image_uploads")
        total_patients = cursor.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            "status": "success",
            "statistics": {
                "total_images": total_images,
                "total_patients": total_patients
            }
        })
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ============================================================
# 憑證管理 API
# ============================================================
@app.route('/get_certificate/<party_id>', methods=['GET'])
def get_certificate(party_id):
    """
    獲取指定成員的憑證（完整版本）
    
    Args:
        party_id: 成員 ID（例如：Hospital_Server_Receiver）
    
    Returns:
        JSON: 憑證資訊
    """
    try:
        print(f"📋 收到憑證請求: {party_id}")
        
        # 選擇正確的物件
        target_obj = None
        if party_id == receiver.receiver_id:
            target_obj = receiver
            print(f"✅ 找到 Receiver 物件")
        elif party_id == sender.sender_id:
            target_obj = sender
            print(f"✅ 找到 Sender 物件")
        else:
            print(f"⚠️ 找不到對應的物件: {party_id}")
            return jsonify({"error": "憑證不存在"}), 404
        
        # Debug: 檢查物件
        print(f"📊 物件類型: {type(target_obj).__name__}")
        
        # ============================================================
        # 1. 獲取 RSA 公鑰
        # ============================================================
        public_key_pem = None
        
        # 嘗試不同的方法獲取公鑰
        if hasattr(target_obj, 'get_public_key_pem') and callable(target_obj.get_public_key_pem):
            # 方法 1: 使用 get_public_key_pem() 方法
            public_key_pem = target_obj.get_public_key_pem()
            print(f"✅ 使用 get_public_key_pem() 方法")
        elif hasattr(target_obj, 'public_key_pem'):
            # 方法 2: 直接取屬性
            public_key_pem = target_obj.public_key_pem
            print(f"✅ 找到 public_key_pem 屬性")
        elif hasattr(target_obj, 'public_key'):
            # 方法 3: 從 public_key 物件序列化
            from cryptography.hazmat.primitives import serialization
            public_key_pem = target_obj.public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            print(f"✅ 從 public_key 屬性產生")
        elif hasattr(target_obj, 'private_key'):
            # 方法 4: 從 private_key 提取公鑰
            from cryptography.hazmat.primitives import serialization
            public_key = target_obj.private_key.public_key()
            public_key_pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            print(f"✅ 從 private_key 產生公鑰")
        else:
            print(f"❌ 找不到公鑰")
            return jsonify({"error": "無法取得公鑰"}), 500
        
        # 確保是 bytes
        if isinstance(public_key_pem, str):
            public_key_pem = public_key_pem.encode('utf-8')
        
        # ============================================================
        # 2. 獲取 KEM 公鑰
        # ============================================================
        kem_public_key = None
        
        if hasattr(target_obj, 'kem_public_key'):
            kem_public_key = target_obj.kem_public_key
            print(f"✅ 找到 kem_public_key")
        elif hasattr(target_obj, 'ml_kem_public_key'):
            kem_public_key = target_obj.ml_kem_public_key
            print(f"✅ 找到 ml_kem_public_key")
        else:
            print(f"⚠️ 找不到 KEM 公鑰")
            kem_public_key = b''
        
        # ============================================================
        # 3. 獲取憑證
        # ============================================================
        certificate_data = None
        
        if hasattr(target_obj, 'certificate') and target_obj.certificate:
            certificate_data = target_obj.certificate
            print(f"✅ 找到憑證資料")
            print(f"📊 憑證類型: {type(certificate_data)}")
            
            # 如果憑證是 bytes，轉為 base64
            if isinstance(certificate_data, bytes):
                certificate_data = base64.b64encode(certificate_data).decode('utf-8')
                print(f"✅ 憑證已轉為 base64")
        else:
            print(f"⚠️ 物件沒有憑證，嘗試生成臨時憑證")
            
            # 生成臨時憑證結構
            certificate_data = {
                "party_id": target_obj.receiver_id if hasattr(target_obj, 'receiver_id') else target_obj.sender_id,
                "public_key_pem": public_key_pem.decode('utf-8'),
                "kem_public_key": base64.b64encode(kem_public_key).decode('utf-8') if kem_public_key else "",
                "issued_at": None,
                "expires_at": None,
                "signature": None,
                "note": "Temporary certificate (not signed by CA)"
            }
            print(f"✅ 已生成臨時憑證")
        
        # ============================================================
        # 4. 建立回應
        # ============================================================
        response = {
            "party_id": target_obj.receiver_id if hasattr(target_obj, 'receiver_id') else target_obj.sender_id,
            "public_key_pem": public_key_pem.decode('utf-8'),
            "kem_public_key_b64": base64.b64encode(kem_public_key).decode('utf-8') if kem_public_key else "",
            "certificate": certificate_data
        }
        
        print(f"✅ 成功建立憑證回應")
        print(f"📊 回應包含 certificate: {certificate_data is not None}")
        
        return jsonify(response)
        
    except Exception as e:
        print(f"❌ 獲取憑證失敗: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "error": "獲取憑證失敗",
            "message": str(e)
        }), 500


@app.route('/public_key', methods=['GET'])
def get_public_key():
    """
    獲取 Server 的公鑰
    
    Returns:
        PEM 格式的公鑰
    """
    try:
        print(f"📋 收到公鑰請求")
        
        # 嘗試不同的方法獲取公鑰
        public_key_pem = None
        
        if hasattr(receiver, 'get_public_key_pem') and callable(receiver.get_public_key_pem):
            public_key_pem = receiver.get_public_key_pem()
        elif hasattr(receiver, 'public_key_pem'):
            public_key_pem = receiver.public_key_pem
        elif hasattr(receiver, 'public_key'):
            from cryptography.hazmat.primitives import serialization
            public_key_pem = receiver.public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
        elif hasattr(receiver, 'private_key'):
            from cryptography.hazmat.primitives import serialization
            public_key = receiver.private_key.public_key()
            public_key_pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
        else:
            raise AttributeError("無法取得公鑰")
        
        # 確保是 bytes
        if isinstance(public_key_pem, str):
            public_key_pem = public_key_pem.encode('utf-8')
        
        print(f"✅ 成功取得公鑰")
        
        return public_key_pem, 200, {
            'Content-Type': 'application/x-pem-file',
            'Content-Disposition': 'inline; filename="public_key.pem"'
        }
        
    except Exception as e:
        print(f"❌ 獲取公鑰失敗: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "error": "獲取公鑰失敗",
            "message": str(e)
        }), 500

'''
@app.route('/get_thumbnail', methods=['POST'])
def get_thumbnail():
    """
    獲取影像縮圖（修正版）
    """
    try:
        data = request.get_json()
        image_id = data.get('image_id')
        
        print(f"📷 獲取縮圖: image_id={image_id}")
        
        conn = connect_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT image_data, mime_type 
            FROM image_uploads              
            WHERE id = ?
        """, (image_id,))
        
        row = cursor.fetchone()
        
        if not row:
            print(f"❌ 找不到影像: {image_id}")
            return jsonify({"error": "Image not found"}), 404
        
        imagedata, mime_type = row
        conn.close()
        
        # 生成縮圖
        from PIL import Image
        from io import BytesIO
        
        # 載入原始影像
        image = Image.open(BytesIO(imagedata))
        
        # 建立縮圖 (80x80)
        image.thumbnail((80, 80), Image.Resampling.LANCZOS)
        
        # 轉換為 JPEG
        output = BytesIO()
        if image.mode in ('RGBA', 'LA', 'P'):
            # 轉換為 RGB
            rgb_image = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'P':
                image = image.convert('RGBA')
            rgb_image.paste(image, mask=image.split()[-1] if image.mode in ('RGBA', 'LA') else None)
            rgb_image.save(output, format='JPEG', quality=85)
        else:
            image.save(output, format='JPEG', quality=85)
        
        output.seek(0)
        
        print(f"✅ 縮圖生成成功: {image_id}")
        
        return send_file(
            output,
            mimetype='image/jpeg',
            as_attachment=False
        )
        
    except Exception as e:
        print(f"❌ 獲取縮圖失敗: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

'''
# ========================================
# 2. 新增 get_image API
# ========================================

@app.route('/get_image', methods=['POST'])
def get_image():
    """
    獲取完整影像
    """
    try:
        data = request.get_json()
        image_id = data.get('image_id')
        
        print(f"📷 獲取完整影像: image_id={image_id}")
        
        conn = connect_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT image_data, mime_type, filename
            FROM image_uploads
            WHERE id = ?
        """, (image_id,))
        
        row = cursor.fetchone()
        
        if not row:
            print(f"❌ 找不到影像: {image_id}")
            return jsonify({"error": "Image not found"}), 404
        
        imagedata, mime_type, filename = row
        conn.close()
        
        print(f"✅ 影像獲取成功: {filename} ({len(imagedata)} bytes)")
        
        from io import BytesIO
        
        return send_file(
            BytesIO(imagedata),
            mimetype=mime_type or 'application/octet-stream',
            as_attachment=False,
            download_name=filename
        )
        
    except Exception as e:
        print(f"❌ 獲取影像失敗: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/get_thumbnail', methods=['POST'])
def get_thumbnail():
    """
    獲取影像縮圖（走加密通道）
    
    Request Body:
        {
            "image_id": int
        }
    
    Returns:
        {
            "status": "success",
            "thumbnail": str (Base64),
            "mime": "image/jpeg"
        }
    """
    try:
        data = request.get_json()
        image_id = data.get('image_id')
        
        if not image_id:
            return jsonify({
                "status": "error",
                "message": "缺少 image_id"
            }), 400
        
        print(f"📷 獲取縮圖: image_id={image_id}")
        
        # 從資料庫獲取縮圖
        conn = connect_db()
        cursor = conn.cursor()
        
        cursor.execute("""
        SELECT image_data, mime_type
        FROM image_uploads
        WHERE id = ?
        """, (image_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row or not row[0]:
            print(f"⚠️ 找不到影像或縮圖: image_id={image_id}")
            return jsonify({
                "status": "error",
                "message": "找不到影像或縮圖"
            }), 404
        
        thumbdata = row[0]
        mime = row[1] or "image/jpeg"
        
        # Base64 編碼
        thumbnail_b64 = base64.b64encode(thumbdata).decode('utf-8')
        
        print(f"✅ 縮圖獲取成功: {len(thumbdata)} bytes")
        
        return jsonify({
            "status": "success",
            "thumbnail": thumbnail_b64,
            "mime": mime
        })
        
    except Exception as e:
        print(f"❌ 獲取縮圖失敗: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
'''
@app.route('/get_image', methods=['POST'])
def get_image():
    """
    獲取完整影像（走加密通道）
    
    Request Body:
        {
            "image_id": int
        }
    
    Returns:
        {
            "status": "success",
            "image_data": str (Base64),
            "mime": str,
            "filename": str
        }
    """
    try:
        data = request.get_json()
        image_id = data.get('image_id')
        
        if not image_id:
            return jsonify({
                "status": "error",
                "message": "缺少 image_id"
            }), 400
        
        print(f"🖼️ 獲取完整影像: image_id={image_id}")
        
        # 從資料庫獲取影像
        conn = connect_db()
        cursor = conn.cursor()
        
        cursor.execute("""
        SELECT image_data, mime_type, filename
        FROM image_uploads
        WHERE id = ?
        """, (image_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row or not row[0]:
            print(f"⚠️ 找不到影像: image_id={image_id}")
            return jsonify({
                "status": "error",
                "message": "找不到影像"
            }), 404
        
        imagedata = row[0]
        mime = row[1] or "image/jpeg"
        filename = row[2] or "unknown.jpg"
        
        # Base64 編碼
        image_b64 = base64.b64encode(imagedata).decode('utf-8')
        
        print(f"✅ 完整影像獲取成功: {filename} ({len(imagedata)} bytes)")
        
        return jsonify({
            "status": "success",
            "image_data": image_b64,
            "mime": mime,
            "filename": filename
        })
        
    except Exception as e:
        print(f"❌ 獲取影像失敗: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
'''
@app.route('/get_patient_images', methods=['GET'])
def get_patient_images():
    """
    獲取病患的所有影像（包含縮圖）
    
    Query Params:
        patient_id: int
        include_thumbnails: bool (default: True)
    
    Returns:
        {
            "status": "success",
            "patient_id": int,
            "images": [
                {
                    "id": int,
                    "filename": str,
                    "mime": str,
                    "upload_time": str,
                    "thumbnail": str (Base64, optional)
                }
            ],
            "count": int
        }
    """
    try:
        patient_id = request.args.get('patient_id', type=int)
        include_thumbnails = request.args.get('include_thumbnails', 'true').lower() == 'true'
        
        if not patient_id:
            return jsonify({
                "status": "error",
                "message": "缺少 patient_id"
            }), 400
        
        print(f"📂 獲取病患影像: patient_id={patient_id}, include_thumbnails={include_thumbnails}")
        
        conn = connect_db()
        cursor = conn.cursor()
        
        # 查詢病患資訊
        cursor.execute("SELECT name, mrn FROM patients WHERE id = ?", (patient_id,))
        patient_row = cursor.fetchone()
        
        if not patient_row:
            conn.close()
            return jsonify({
                "status": "error",
                "message": "病患不存在"
            }), 404
        
        patient_name = patient_row[0]
        patient_mrn = patient_row[1]
        
        # 查詢影像
        if include_thumbnails:
            query = """
            SELECT id, filename, mime_type, upload_time, image_data
            FROM image_uploads
            WHERE patient_id = ?
            ORDER BY upload_time DESC
            """
        else:
            query = """
            SELECT id, filename, mime_type, upload_time
            FROM image_uploads
            WHERE patient_id = ?
            ORDER BY upload_time DESC
            """
        
        cursor.execute(query, (patient_id,))
        rows = cursor.fetchall()
        conn.close()
        
        images = []
        for row in rows:
            image = {
                "id": row[0],
                "filename": row[1],
                "mime": row[2] or "image/jpeg",
                "upload_time": row[3]
            }
            
            # 加入縮圖（如果有）
            if include_thumbnails and len(row) > 4 and row[4]:
                thumbdata = row[4]
                thumbnail_b64 = base64.b64encode(thumbdata).decode('utf-8')
                image["thumbnail"] = thumbnail_b64
            
            images.append(image)
        
        print(f"✅ 找到 {len(images)} 張影像")
        
        return jsonify({
            "status": "success",
            "patient_id": patient_id,
            "patient_name": patient_name,
            "patient_mrn": patient_mrn,
            "images": images,
            "count": len(images)
        })
        
    except Exception as e:
        print(f"❌ 獲取病患影像失敗: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# ========== 輔助函數 ==========

def create_thumbnail(image_bytes, size=(128, 128)):
    """
    創建縮圖
    
    Args:
        image_bytes: 原始影像二進位
        size: 縮圖尺寸
    
    Returns:
        縮圖二進位（JPEG 格式）
    """
    try:
        # 打開影像
        img = Image.open(BytesIO(image_bytes))
        
        # 轉換為 RGB（如果是 RGBA 或其他格式）
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # 創建縮圖
        img.thumbnail(size, Image.Resampling.LANCZOS)
        
        # 儲存為 JPEG
        thumb_io = BytesIO()
        img.save(thumb_io, format='JPEG', quality=85)
        thumb_io.seek(0)
        
        return thumb_io.read()
        
    except Exception as e:
        print(f"⚠️ 創建縮圖失敗: {e}")
        return None

# ============================================================
# Debug 端點
# ============================================================

@app.route('/debug/receiver_info', methods=['GET'])
def debug_receiver_info():
    """Debug: 顯示 Receiver 物件資訊"""
    try:
        info = {
            "receiver_id": receiver.receiver_id if hasattr(receiver, 'receiver_id') else None,
            "type": type(receiver).__name__,
            "has_get_public_key_pem": hasattr(receiver, 'get_public_key_pem'),
            "has_public_key_pem": hasattr(receiver, 'public_key_pem'),
            "has_public_key": hasattr(receiver, 'public_key'),
            "has_private_key": hasattr(receiver, 'private_key'),
            "has_kem_public_key": hasattr(receiver, 'kem_public_key'),
            "has_certificate": hasattr(receiver, 'certificate'),
            "certificate_is_none": receiver.certificate is None if hasattr(receiver, 'certificate') else True,
            "certificate_type": type(receiver.certificate).__name__ if hasattr(receiver, 'certificate') and receiver.certificate else None,
        }
        return jsonify(info)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# 病患管理 API（修正版）
# ============================================================

@app.route('/patients', methods=['GET'])
def list_patients():
    """
    列出病患清單（修正版）
    """
    try:
        keyword = request.args.get('keyword', '').strip()
        
        print(f"📋 收到病患列表請求 (keyword: '{keyword}')")
        
        conn = connect_db()
        cursor = conn.cursor()
        
        if keyword:
            print(f"🔍 搜尋病患: {keyword}")
            cursor.execute("""
                SELECT 
                    p.id, p.name, p.mrn, p.patient_id, p.national_id,
                    p.birthday, p.gender, p.blood_type,
                    p.phone, p.mobile, p.email, p.address,
                    p.emergency_contact, p.emergency_phone,
                    p.insurance_id, p.notes,
                    u.username as doctor_name,
                    cd.name as clinical_dept_name
                FROM patients p
                LEFT JOIN users u ON p.doctor_id = u.id
                LEFT JOIN clinical_departments cd ON u.clinical_dept_id = cd.id
                WHERE p.name LIKE ? OR p.mrn LIKE ? OR p.national_id LIKE ?
                ORDER BY p.id DESC
            """, (f'%{keyword}%', f'%{keyword}%', f'%{keyword}%'))
        else:
            print(f"📋 列出所有病患")
            cursor.execute("""
                SELECT 
                    p.id, p.name, p.mrn, p.patient_id, p.national_id,
                    p.birthday, p.gender, p.blood_type,
                    p.phone, p.mobile, p.email, p.address,
                    p.emergency_contact, p.emergency_phone,
                    p.insurance_id, p.notes
                FROM patients p
                ORDER BY p.id DESC
            """)
        
        rows = cursor.fetchall()
        
        patients = []
        for row in rows:
            patients.append({
                'id': row[0],
                'name': row[1],
                'mrn': row[2],
                'patient_id': row[3],
                'national_id': row[4],
                'birthday': row[5],
                'gender': row[6],
                'blood_type': row[7],
                'phone': row[8],
                'mobile': row[9],
                'email': row[10],
                'address': row[11],
                'emergency_contact': row[12],
                'emergency_phone': row[13],
                'insurance_id': row[14],
                'notes': row[15]
            })
        
        conn.close()
        
        print(f"✅ 成功列出 {len(patients)} 個病患")
        
        return jsonify(patients)
        
    except Exception as e:
        print(f"❌ 列出病患失敗: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/patients/<int:patient_id>', methods=['GET'])
def get_patient(patient_id):
    """
    獲取單一病患詳情
    
    Args:
        patient_id: 病患 ID
    
    Returns:
        JSON: 病患詳細資訊
    """
    try:
        print(f"📋 獲取病患詳情: ID={patient_id}")
        
        conn = connect_db()
        cursor = conn.cursor()
        
        cursor.execute("""
        SELECT id, name, mrn, gender, birthday, blood_type, 
               nationalid, phone, created_at
        FROM patients
        WHERE id = ?
        """, (patient_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            print(f"⚠️ 找不到病患 ID: {patient_id}")
            return jsonify({"error": "病患不存在"}), 404
        
        patient = {
            'id': row[0],
            'name': row[1],
            'mrn': row[2],
            'gender': row[3],
            'birthday': row[4],
            'blood_type': row[5],  # ← 統一使用 blood_type
            'nationalid': row[6],
            'phone': row[7],
            'created_at': row[8]
        }
        
        print(f"✅ 回傳病患: {patient['name']}")
        return jsonify(patient)
        
    except Exception as e:
        print(f"❌ 獲取病患失敗: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "error": "獲取病患失敗",
            "message": str(e)
        }), 500


@app.route('/patients', methods=['POST'])
def create_patient():
    """
    創建新病患
    
    Request Body:
        {
            "name": "姓名",
            "mrn": "病歷號",
            "gender": "性別",
            "birthday": "生日",
            "blood_type": "血型",  ← Client 傳入 blood_type
            "nationalid": "身分證",
            "phone": "電話"
        }
    
    Returns:
        JSON: 創建結果
    """
    try:
        data = request.get_json()
        print(f"📋 收到創建病患請求: {data}")
        
        # 必填欄位
        name = data.get('name', '').strip()
        mrn = data.get('mrn', '').strip()
        
        if not name or not mrn:
            print("❌ 缺少必填欄位")
            return jsonify({
                "status": "error",
                "message": "姓名和 MRN 為必填"
            }), 400
        
        # 可選欄位（注意：blood_type → bloodtype）
        gender = data.get('gender', '').strip() or None
        birthday = data.get('birthday', '').strip() or None
        bloodtype = data.get('blood_type', '').strip() or None  # ← 轉換
        nationalid = data.get('nationalid', '').strip() or None
        phone = data.get('phone', '').strip() or None
        
        conn = connect_db()
        cursor = conn.cursor()
        
        # 檢查 MRN 是否重複
        cursor.execute("SELECT id FROM patients WHERE mrn = ?", (mrn,))
        if cursor.fetchone():
            conn.close()
            print(f"❌ MRN 已存在: {mrn}")
            return jsonify({
                "status": "error",
                "message": f"MRN {mrn} 已存在"
            }), 400
        
        # 插入病患（使用 bloodtype 欄位）
        cursor.execute("""
        INSERT INTO patients (name, mrn, gender, birthday, blood_type, nationalid, phone)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (name, mrn, gender, birthday, bloodtype, nationalid, phone))
        
        patient_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        print(f"✅ 已創建病患: {name} (MRN:{mrn}, ID:{patient_id})")
        
        return jsonify({
            "status": "success",
            "message": "病患創建成功",
            "patient_id": patient_id
        })
        
    except Exception as e:
        print(f"❌ 創建病患失敗: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route('/patients/<int:patient_id>', methods=['PUT'])
def update_patient(patient_id):

    try:
        data = request.get_json()
        print(f"📋 更新病患 ID={patient_id}: {data}")
        
        conn = connect_db()
        cursor = conn.cursor()
        
        # 檢查病患是否存在
        cursor.execute("SELECT id FROM patients WHERE id = ?", (patient_id,))
        if not cursor.fetchone():
            conn.close()
            print(f"⚠️ 找不到病患 ID: {patient_id}")
            return jsonify({"error": "病患不存在"}), 404
        
        # 建立更新語句（注意欄位名稱對應）
        update_fields = []
        update_values = []
        
        # 欄位對應：API 使用 blood_type，資料庫使用 bloodtype
        field_mapping = {
            'name': 'name',
            'mrn': 'mrn',
            'gender': 'gender',
            'birthday': 'birthday',
            'blood_type': 'blood_type',  # ← 關鍵：轉換欄位名稱
            'nationalid': 'nationalid',
            'phone': 'phone'
        }
        
        for api_field, db_field in field_mapping.items():
            if api_field in data:
                update_fields.append(f"{db_field} = ?")
                update_values.append(data[api_field])
        
        if not update_fields:
            conn.close()
            print("⚠️ 沒有要更新的欄位")
            return jsonify({"error": "沒有要更新的欄位"}), 400
        
        # 執行更新
        update_values.append(patient_id)
        sql = f"UPDATE patients SET {', '.join(update_fields)} WHERE id = ?"
        cursor.execute(sql, update_values)
        
        conn.commit()
        conn.close()
        
        print(f"✅ 已更新病患 ID: {patient_id}")
        
        return jsonify({
            "status": "success",
            "message": "病患資訊已更新"
        })
        
    except Exception as e:
        print(f"❌ 更新病患失敗: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/patients/<int:patient_id>', methods=['DELETE'])
def delete_patient(patient_id):
    """
    刪除病患
    
    Args:
        patient_id: 病患 ID
    
    Returns:
        JSON: 刪除結果
    """
    try:
        print(f"📋 刪除病患 ID={patient_id}")
        
        conn = connect_db()
        cursor = conn.cursor()
        
        # 檢查病患是否存在
        cursor.execute("SELECT id FROM patients WHERE id = ?", (patient_id,))
        if not cursor.fetchone():
            conn.close()
            print(f"⚠️ 找不到病患 ID: {patient_id}")
            return jsonify({"error": "病患不存在"}), 404
        
        # 檢查是否有關聯的影像
        cursor.execute("SELECT COUNT(*) FROM image_uploads WHERE patient_id = ?", (patient_id,))
        image_count = cursor.fetchone()[0]
        
        if image_count > 0:
            conn.close()
            print(f"⚠️ 病患有 {image_count} 張影像，無法刪除")
            return jsonify({
                "error": f"無法刪除：該病患有 {image_count} 張影像"
            }), 400
        
        # 刪除病患
        cursor.execute("DELETE FROM patients WHERE id = ?", (patient_id,))
        conn.commit()
        conn.close()
        
        print(f"✅ 已刪除病患 ID: {patient_id}")
        
        return jsonify({
            "status": "success",
            "message": "病患已刪除"
        })
        
    except Exception as e:
        print(f"❌ 刪除病患失敗: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
@app.route('/login', methods=['POST'])
def api_login():
    """
    使用者登入驗證
    
    Request:
        {
            "username": "doctor1",
            "password": "doctor1"
        }
    
    Response (成功 - HTTP 200):
        {
            "status": "success",
            "user": {
                "id": 1,
                "username": "doctor1",
                "full_name": "張心臟",
                "email": "doctor1@hospital.com",
                "role_code": "doctor",
                "role_name": "醫師",
                "clinical_dept_id": 1,
                "clinical_dept_name": "心臟內科",
                "employee_id": "EMP001",
                "phone": "02-1234-5678",
                "is_active": True
            }
        }
    
    Response (失敗 - HTTP 401):
        {
            "status": "error",
            "error_code": "user_not_found" | "wrong_password" | "account_disabled",
            "message": "錯誤訊息"
        }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'status': 'error',
                'error_code': 'invalid_request',
                'message': '請求格式錯誤'
            }), 400
        
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        
        # 驗證輸入
        if not username or not password:
            return jsonify({
                'status': 'error',
                'error_code': 'invalid_input',
                'message': '請輸入帳號和密碼'
            }), 400
        
        print(f"🔐 登入請求: {username}")
        
        # 從資料庫查詢使用者
        user = get_user_by_username(username)
        
        if not user:
            # 記錄失敗的登入嘗試
            log_audit(None, 'login_failed', description=f"帳號不存在: {username}")
            print(f"❌ 登入失敗: 帳號不存在 - {username}")
            
            return jsonify({
                'status': 'error',
                'error_code': 'user_not_found',
                'message': '帳號不存在'
            }), 401
        
        # 驗證密碼（注意：實際應用應使用 bcrypt 等密碼雜湊）
        if user['password'] != password:
            # 記錄失敗的登入嘗試
            log_audit(user['id'], 'login_failed', description=f"密碼錯誤: {username}")
            print(f"❌ 登入失敗: 密碼錯誤 - {username}")
            
            return jsonify({
                'status': 'error',
                'error_code': 'wrong_password',
                'message': '密碼錯誤'
            }), 401
        
        # 檢查帳號是否啟用
        if not user.get('is_active', True):
            # 記錄停用帳號的登入嘗試
            log_audit(user['id'], 'login_failed', description=f"帳號已停用: {username}")
            print(f"❌ 登入失敗: 帳號已停用 - {username}")
            
            return jsonify({
                'status': 'error',
                'error_code': 'account_disabled',
                'message': '帳號已停用'
            }), 401
        
        # 登入成功
        print(f"✅ 登入成功: {username} ({user['role_name']})")
        
        # 記錄成功的登入
        log_audit(user['id'], 'login_success', description=f"登入成功: {username}")
        
        # 準備回傳的使用者資料（不包含密碼）
        user_data = {
            'id': user['id'],
            'username': user['username'],
            'full_name': user.get('full_name', username),
            'email': user.get('email', ''),
            'role_code': user['role_code'],
            'role_name': user['role_name'],
            'clinical_dept_id': user.get('clinical_dept_id'),
            'clinical_dept_name': user.get('clinical_dept_name', ''),
            'employee_id': user.get('employee_id', ''),
            'phone': user.get('phone', ''),
            'is_active': user.get('is_active', True)
        }
        
        return jsonify({
            'status': 'success',
            'user': user_data
        }), 200
        
    except Exception as e:
        print(f"❌ 登入 API 錯誤: {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            'status': 'error',
            'error_code': 'server_error',
            'message': f'伺服器錯誤: {str(e)}'
        }), 500


@app.route('/logout', methods=['POST'])
def api_logout():
    """
    使用者登出
    
    Request:
        {
            "user_id": 1
        }
    
    Response (HTTP 200):
        {
            "status": "success",
            "message": "登出成功"
        }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'status': 'error',
                'message': '請求格式錯誤'
            }), 400
        
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({
                'status': 'error',
                'message': '缺少 user_id'
            }), 400
        
        # 記錄登出事件
        log_audit(user_id, 'logout', description=f"使用者登出: user_id={user_id}")
        
        print(f"✅ 使用者登出: user_id={user_id}")
        
        return jsonify({
            'status': 'success',
            'message': '登出成功'
        }), 200
        
    except Exception as e:
        print(f"❌ 登出 API 錯誤: {e}")
        
        return jsonify({
            'status': 'error',
            'message': f'伺服器錯誤: {str(e)}'
        }), 500


# ============================================================
# 科別管理 API
# ============================================================

@app.route('/departments/clinical', methods=['GET'])
def api_list_clinical_departments():
    """
    列出臨床科別
    
    Response:
        {
            "status": "success",
            "departments": [
                {
                    "id": 1,
                    "code": "CARD",
                    "name": "心臟內科",
                    "description": "心血管疾病診治",
                    "head_doctor": "張心臟醫師",
                    "phone": "02-1234-5678",
                    "location": "3樓A區"
                },
                ...
            ]
        }
    """
    try:
        conn = connect_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, code, name, description, head_doctor, phone, location
            FROM clinical_departments
            ORDER BY code
        """)
        
        departments = []
        for row in cursor.fetchall():
            departments.append({
                'id': row[0],
                'code': row[1],
                'name': row[2],
                'description': row[3],
                'head_doctor': row[4],
                'phone': row[5],
                'location': row[6]
            })
        
        conn.close()
        
        print(f"📋 列出臨床科別: {len(departments)} 筆")
        
        return jsonify({
            'status': 'success',
            'departments': departments
        }), 200
        
    except Exception as e:
        print(f"❌ 列出臨床科別失敗: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/departments/modality', methods=['GET'])
def api_list_modality_departments():
    """
    列出影像檢查科別
    
    Response:
        {
            "status": "success",
            "departments": [
                {
                    "id": 1,
                    "code": "CT",
                    "name": "電腦斷層掃描",
                    "description": "Computed Tomography"
                },
                ...
            ]
        }
    """
    try:
        conn = connect_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, code, name, description
            FROM modality_departments
            ORDER BY code
        """)
        
        departments = []
        for row in cursor.fetchall():
            departments.append({
                'id': row[0],
                'code': row[1],
                'name': row[2],
                'description': row[3]
            })
        
        conn.close()
        
        print(f"📋 列出影像檢查科別: {len(departments)} 筆")
        
        return jsonify({
            'status': 'success',
            'departments': departments
        }), 200
        
    except Exception as e:
        print(f"❌ 列出影像檢查科別失敗: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500   

def main():
    """主程式入口"""
    if len(sys.argv) < 2:
        print("使用方式: python server_integrated.py <port> [ca_host] [ca_port]")
        print("範例: python server_integrated.py 8200 localhost 8001")
        sys.exit(1)
    
    port = int(sys.argv[1])
    server_ca_host = sys.argv[2] if len(sys.argv) > 2 else 'localhost'
    server_ca_port = int(sys.argv[3]) if len(sys.argv) > 3 else 8001
    
    try:
        init_server(server_ca_host, server_ca_port)
    except Exception as e:
        print(f"\n❌ Server 初始化失敗: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print(f"\n🚀 Server 啟動在 port {port}\n")
    
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()