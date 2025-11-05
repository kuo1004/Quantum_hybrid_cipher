# -*- coding: utf-8 -*-
"""
database.py - IRIS 智慧影像系統資料庫模組（增強版）

功能特色：
1. 完整的角色權限系統
2. 臨床科別和影像科別分類
3. 影像和影片支援
4. DICOM 標準相容
5. 加密傳輸記錄
6. 審計日誌

資料庫名稱：IRIS_database.db
"""

import os
import sqlite3
from datetime import datetime, date

# 資料庫路徑
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "IRIS_database.db")


def get_db_path():
    """取得資料庫路徑"""
    return DB_PATH


def connect_db():
    """連接到 IRIS 資料庫（啟用外鍵約束）"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_database():
    """初始化 IRIS 資料庫結構和預設資料"""
    conn = connect_db()
    cursor = conn.cursor()
    
    print("🔧 開始初始化 IRIS 資料庫...")

    # ========== 1. 角色權限表 ==========
    print("   建立角色權限表...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            description TEXT,
            can_view_images BOOLEAN DEFAULT 0,
            can_upload_images BOOLEAN DEFAULT 0,
            can_delete_images BOOLEAN DEFAULT 0,
            can_manage_patients BOOLEAN DEFAULT 0,
            can_manage_users BOOLEAN DEFAULT 0,
            can_view_all_departments BOOLEAN DEFAULT 0,
            can_export_data BOOLEAN DEFAULT 0,
            can_view_audit_log BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ========== 2. 臨床科別表 ==========
    print("   建立臨床科別表...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clinical_departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            description TEXT,
            head_doctor TEXT,
            phone TEXT,
            location TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ========== 3. 影像檢查科別表（Modality）==========
    print("   建立影像檢查科別表...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS modality_departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ========== 4. 使用者表 ==========
    print("   建立使用者表...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            full_name TEXT,
            email TEXT,
            phone TEXT,
            role_id INTEGER NOT NULL,
            clinical_dept_id INTEGER,
            employee_id TEXT UNIQUE,
            is_active BOOLEAN DEFAULT 1,
            last_login TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (role_id) REFERENCES roles(id),
            FOREIGN KEY (clinical_dept_id) REFERENCES clinical_departments(id)
        )
    """)

    # ========== 5. 病患表 ==========
    print("   建立病患表...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            patient_id TEXT UNIQUE NOT NULL,
            mrn TEXT UNIQUE NOT NULL,
            national_id TEXT,
            birthday DATE NOT NULL,
            gender TEXT CHECK(gender IN ('M', 'F', 'O')) DEFAULT 'O',
            blood_type TEXT CHECK(blood_type IN ('A', 'B', 'AB', 'O', 'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-')),
            phone TEXT,
            mobile TEXT,
            email TEXT,
            address TEXT,
            emergency_contact TEXT,
            emergency_phone TEXT,
            primary_doctor_id INTEGER,
            clinical_dept_id INTEGER,
            insurance_id TEXT,
            notes TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (primary_doctor_id) REFERENCES users(id),
            FOREIGN KEY (clinical_dept_id) REFERENCES clinical_departments(id)
        )
    """)

    # ========== 6. 影像上傳記錄表 ==========
    print("   建立影像上傳記錄表...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS image_uploads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            uploader_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            original_filename TEXT,
            file_type TEXT CHECK(file_type IN ('image', 'video', 'dicom')) NOT NULL,
            mime_type TEXT,
            file_size INTEGER,
            image_data BLOB NOT NULL,
            thumbnail BLOB,
            modality_dept_id INTEGER,
            clinical_dept_id INTEGER,
            study_description TEXT,
            body_part TEXT,
            is_encrypted BOOLEAN DEFAULT 1,
            encryption_method TEXT DEFAULT 'AES-256-GCM',
            transmission_id TEXT,
            status TEXT CHECK(status IN ('pending', 'uploaded', 'completed', 'failed', 'deleted')) DEFAULT 'completed',
            upload_date DATE DEFAULT (date('now')),
            upload_time TIME DEFAULT (time('now')),
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (patient_id) REFERENCES patients(id),
            FOREIGN KEY (uploader_id) REFERENCES users(id),
            FOREIGN KEY (modality_dept_id) REFERENCES modality_departments(id),
            FOREIGN KEY (clinical_dept_id) REFERENCES clinical_departments(id)
        )
    """)

    # ========== 7. DICOM Studies 表 ==========
    print("   建立 DICOM Studies 表...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dicom_studies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            study_instance_uid TEXT UNIQUE NOT NULL,
            study_date DATE,
            study_time TEXT,
            study_description TEXT,
            accession_number TEXT,
            referring_physician TEXT,
            institution_name TEXT,
            modality_dept_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (patient_id) REFERENCES patients(id),
            FOREIGN KEY (modality_dept_id) REFERENCES modality_departments(id)
        )
    """)

    # ========== 8. DICOM Series 表 ==========
    print("   建立 DICOM Series 表...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dicom_series (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            study_id INTEGER NOT NULL,
            series_instance_uid TEXT UNIQUE NOT NULL,
            modality TEXT,
            body_part TEXT,
            series_number INTEGER,
            series_description TEXT,
            laterality TEXT,
            protocol_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (study_id) REFERENCES dicom_studies(id)
        )
    """)

    # ========== 9. DICOM Instances 表 ==========
    print("   建立 DICOM Instances 表...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dicom_instances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            series_id INTEGER NOT NULL,
            uploader_id INTEGER,
            sop_instance_uid TEXT UNIQUE NOT NULL,
            instance_number INTEGER,
            acquisition_time TEXT,
            original_data BLOB NOT NULL,
            mime_type TEXT DEFAULT 'application/dicom',
            filename TEXT,
            file_size INTEGER,
            patient_name TEXT,
            patient_id_tag TEXT,
            study_date TEXT,
            modality TEXT,
            body_part TEXT,
            rows INTEGER,
            columns INTEGER,
            bits_allocated INTEGER,
            bits_stored INTEGER,
            pixel_spacing TEXT,
            slice_thickness REAL,
            window_center TEXT,
            window_width TEXT,
            thumbnail BLOB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (series_id) REFERENCES dicom_series(id),
            FOREIGN KEY (uploader_id) REFERENCES users(id)
        )
    """)

    # ========== 10. 傳輸日誌表 ==========
    print("   建立傳輸日誌表...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transmission_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transmission_id TEXT UNIQUE NOT NULL,
            sender_id TEXT,
            receiver_id TEXT,
            image_upload_id INTEGER,
            encryption_algorithm TEXT,
            key_exchange_method TEXT,
            signature_verified BOOLEAN,
            transmission_status TEXT CHECK(transmission_status IN ('started', 'encrypted', 'sent', 'received', 'decrypted', 'verified', 'failed')) DEFAULT 'started',
            error_message TEXT,
            transmission_time REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (image_upload_id) REFERENCES image_uploads(id)
        )
    """)

    # ========== 11. 審計日誌表 ==========
    print("   建立審計日誌表...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            resource_type TEXT,
            resource_id INTEGER,
            description TEXT,
            ip_address TEXT,
            user_agent TEXT,
            status TEXT CHECK(status IN ('success', 'failed', 'warning')) DEFAULT 'success',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # ========== 12. 系統設定表 ==========
    print("   建立系統設定表...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            value TEXT,
            description TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()

    # ========== 插入預設資料 ==========
    print("\n📊 插入預設資料...")

    # === 角色權限 ===
    print("   新增角色...")
    roles = [
        ('admin', '系統管理員', '擁有所有權限', 1, 1, 1, 1, 1, 1, 1, 1),
        ('doctor', '醫師', '可查看和上傳影像', 1, 1, 0, 1, 0, 0, 1, 0),
        ('nurse', '護理師', '可查看和上傳影像', 1, 1, 0, 1, 0, 0, 0, 0),
        ('radtech', '放射技師', '可上傳影像', 1, 1, 0, 0, 0, 0, 0, 0),
        ('viewer', '觀察者', '僅可查看影像', 1, 0, 0, 0, 0, 0, 0, 0)
    ]
    
    for code, name, desc, view, upload, delete, patient, user, all_dept, export, audit in roles:
        try:
            cursor.execute("""
                INSERT INTO roles (code, name, description, can_view_images, can_upload_images, 
                                 can_delete_images, can_manage_patients, can_manage_users, 
                                 can_view_all_departments, can_export_data, can_view_audit_log)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (code, name, desc, view, upload, delete, patient, user, all_dept, export, audit))
        except sqlite3.IntegrityError:
            pass

    # === 臨床科別 ===
    print("   新增臨床科別...")
    clinical_depts = [
        ('CARD', '心臟內科', '心血管疾病診治', '張心臟醫師', '02-1234-5678', '3樓A區'),
        ('NEU', '神經內科', '神經系統疾病診治', '李神經醫師', '02-1234-5679', '3樓B區'),
        ('ORTHO', '骨科', '骨骼肌肉系統疾病', '王骨科醫師', '02-1234-5680', '4樓A區'),
        ('GI', '腸胃內科', '消化系統疾病', '陳腸胃醫師', '02-1234-5681', '4樓B區'),
        ('RESP', '胸腔內科', '呼吸系統疾病', '林胸腔醫師', '02-1234-5682', '5樓A區'),
        ('ENDO', '內分泌科', '內分泌代謝疾病', '黃內分泌醫師', '02-1234-5683', '5樓B區'),
        ('ONCO', '腫瘤科', '癌症治療', '周腫瘤醫師', '02-1234-5684', '6樓A區'),
        ('SURG', '外科', '外科手術', '吳外科醫師', '02-1234-5685', '6樓B區'),
    ]
    
    for code, name, desc, head, phone, location in clinical_depts:
        try:
            cursor.execute("""
                INSERT INTO clinical_departments (code, name, description, head_doctor, phone, location)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (code, name, desc, head, phone, location))
        except sqlite3.IntegrityError:
            pass

    # === 影像檢查科別（Modality）===
    print("   新增影像檢查科別...")
    modality_depts = [
        ('CT', '電腦斷層掃描', 'Computed Tomography'),
        ('MR', '磁共振成像', 'Magnetic Resonance Imaging'),
        ('CR', 'X光攝影', 'Computed Radiography'),
        ('DX', '數位X光', 'Digital X-Ray'),
        ('US', '超音波', 'Ultrasound'),
        ('NM', '核醫學', 'Nuclear Medicine'),
        ('PT', '正子斷層', 'Positron Emission Tomography'),
        ('XA', '血管攝影', 'X-Ray Angiography'),
        ('MG', '乳房攝影', 'Mammography'),
        ('RF', '透視檢查', 'Radiofluoroscopy'),
        ('ES', '內視鏡', 'Endoscopy'),
        ('OT', '其他', 'Other'),
    ]
    
    for code, name, desc in modality_depts:
        try:
            cursor.execute("""
                INSERT INTO modality_departments (code, name, description)
                VALUES (?, ?, ?)
            """, (code, name, desc))
        except sqlite3.IntegrityError:
            pass

    # === 使用者（保持原有預設）===
    print("   新增使用者...")
    users = [
        ('admin', 'admin', '系統管理員', 'admin@iris.com', '02-1234-0000', 1, None, 'EMP001'),
        ('doctor1', 'doctor1', '張心臟', 'chang@iris.com', '02-1234-1001', 2, 1, 'DOC001'),
        ('doctor2', 'doctor2', '李神經', 'lee@iris.com', '02-1234-1002', 2, 2, 'DOC002'),
        ('nurse', 'nurse', '王護理師', 'nurse@iris.com', '02-1234-2001', 3, None, 'NUR001'),
        ('radtech', 'radtech', '陳放射師', 'rad@iris.com', '02-1234-3001', 4, None, 'RAD001'),
    ]
    
    for username, password, full_name, email, phone, role_id, dept_id, emp_id in users:
        try:
            cursor.execute("""
                INSERT INTO users (username, password, full_name, email, phone, role_id, 
                                 clinical_dept_id, employee_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (username, password, full_name, email, phone, role_id, dept_id, emp_id))
        except sqlite3.IntegrityError:
            pass

    # === 病患（三個完整資訊的預設病人）===
    print("   新增病患...")
    patients = [
        (
            '王大明',                    # name
            'PAT20240001',              # patient_id
            'MRN20240001',              # mrn
            'A123456789',               # national_id
            '1975-03-15',               # birthday
            'M',                        # gender
            'A+',                       # blood_type
            '02-2345-6789',             # phone
            '0912-345-678',             # mobile
            'wang@email.com',           # email
            '台北市中正區重慶南路一段122號',  # address
            '王小華（配偶）',              # emergency_contact
            '0923-456-789',             # emergency_phone
            2,                          # primary_doctor_id (張心臟醫師)
            1,                          # clinical_dept_id (心臟內科)
            'INS001-2024',              # insurance_id
            '有高血壓病史，定期追蹤'          # notes
        ),
        (
            '李小美',
            'PAT20240002',
            'MRN20240002',
            'B987654321',
            '1982-07-22',
            'F',
            'O-',
            '02-3456-7890',
            '0934-567-890',
            'lee@email.com',
            '新北市板橋區中山路二段234號',
            '李大雄（父親）',
            '0945-678-901',
            3,                          # 李神經醫師
            2,                          # 神經內科
            'INS002-2024',
            '糖尿病患者，需注意血糖控制'
        ),
        (
            '陳建國',
            'PAT20240003',
            'MRN20240003',
            'C246813579',
            '1968-11-30',
            'M',
            'B+',
            '02-4567-8901',
            '0956-789-012',
            'chen@email.com',
            '台北市大安區復興南路一段390號',
            '陳美玲（妻子）',
            '0967-890-123',
            2,                          # 張心臟醫師
            3,                          # 骨科
            'INS003-2024',
            '曾進行膝關節置換手術，定期復健'
        ),
    ]
    
    for patient_data in patients:
        try:
            cursor.execute("""
                INSERT INTO patients (
                    name, patient_id, mrn, national_id, birthday, gender, blood_type,
                    phone, mobile, email, address, emergency_contact, emergency_phone,
                    primary_doctor_id, clinical_dept_id, insurance_id, notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, patient_data)
        except sqlite3.IntegrityError as e:
            print(f"      ⚠️  病患資料已存在: {patient_data[0]}")

    # === 系統設定 ===
    print("   新增系統設定...")
    settings = [
        ('system_name', 'IRIS 智慧影像系統', '系統名稱'),
        ('version', '1.0.0', '系統版本'),
        ('max_upload_size', '524288000', '最大上傳大小（500MB）'),
        ('encryption_enabled', '1', '啟用加密傳輸'),
        ('audit_log_enabled', '1', '啟用審計日誌'),
        ('session_timeout', '3600', 'Session 逾時時間（秒）'),
    ]
    
    for key, value, desc in settings:
        try:
            cursor.execute("""
                INSERT INTO system_settings (key, value, description)
                VALUES (?, ?, ?)
            """, (key, value, desc))
        except sqlite3.IntegrityError:
            pass

    conn.commit()
    conn.close()

    print("\n✅ IRIS 資料庫初始化完成！")
    print(f"   資料庫位置: {DB_PATH}")
    print(f"   資料庫大小: {os.path.getsize(DB_PATH) / 1024:.2f} KB")
    print("\n📋 預設帳號:")
    print("   管理員: admin / admin")
    print("   醫師1: doctor1 / doctor1 (心臟內科)")
    print("   醫師2: doctor2 / doctor2 (神經內科)")
    print("   護理師: nurse / nurse")
    print("   放射技師: radtech / radtech")
    print("\n👥 預設病患:")
    print("   1. 王大明 (MRN20240001) - 心臟內科")
    print("   2. 李小美 (MRN20240002) - 神經內科")
    print("   3. 陳建國 (MRN20240003) - 骨科")


# ========== 資料庫操作函數 ==========

def insert_image_upload(patient_id, uploader_id, imagedata, filename, mime, 
                       modality_dept_id=None, clinical_dept_id=None, 
                       file_type='image', **kwargs):
    """
    插入影像上傳記錄
    
    Args:
        patient_id: 病患 ID
        uploader_id: 上傳者 ID
        imagedata: 影像資料（BLOB）
        filename: 檔案名稱
        mime: MIME 類型
        modality_dept_id: 影像檢查科別 ID
        clinical_dept_id: 臨床科別 ID
        file_type: 檔案類型 ('image', 'video', 'dicom')
        **kwargs: 其他可選參數
    
    Returns:
        int: 新插入記錄的 ID
    """
    conn = connect_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO image_uploads (
                patient_id, uploader_id, filename, original_filename, file_type, mime_type,
                file_size, image_data, thumbnail, modality_dept_id, clinical_dept_id,
                study_description, body_part, is_encrypted, encryption_method,
                transmission_id, status, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            patient_id,
            uploader_id,
            filename,
            kwargs.get('original_filename', filename),
            file_type,
            mime,
            kwargs.get('file_size', len(imagedata)),
            imagedata,
            kwargs.get('thumbnail'),
            modality_dept_id,
            clinical_dept_id,
            kwargs.get('study_description'),
            kwargs.get('body_part'),
            kwargs.get('is_encrypted', 1),
            kwargs.get('encryption_method', 'AES-256-GCM'),
            kwargs.get('transmission_id'),
            kwargs.get('status', 'completed'),
            kwargs.get('notes')
        ))
        
        image_id = cursor.lastrowid
        conn.commit()
        
        # 記錄審計日誌
        log_audit(uploader_id, 'upload_image', 'image_uploads', image_id, 
                 f"上傳影像: {filename}")
        
        return image_id
        
    except Exception as e:
        conn.rollback()
        print(f"❌ 插入影像記錄失敗: {e}")
        raise
    finally:
        conn.close()


def get_image_data(image_id):
    """取得影像資料"""
    conn = connect_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT image_data FROM image_uploads WHERE id = ?", (image_id,))
    row = cursor.fetchone()
    conn.close()
    
    return row['image_data'] if row else None


def list_images(patient_id=None, clinical_dept_id=None, limit=100):
    """
    列出影像清單
    
    Args:
        patient_id: 病患 ID（可選）
        clinical_dept_id: 臨床科別 ID（可選）
        limit: 限制筆數
    
    Returns:
        list: 影像記錄列表
    """
    conn = connect_db()
    cursor = conn.cursor()
    
    query = """
        SELECT 
            iu.*,
            p.name as patient_name,
            p.mrn,
            u.full_name as uploader_name,
            cd.name as clinical_dept_name,
            md.name as modality_dept_name
        FROM image_uploads iu
        LEFT JOIN patients p ON iu.patient_id = p.id
        LEFT JOIN users u ON iu.uploader_id = u.id
        LEFT JOIN clinical_departments cd ON iu.clinical_dept_id = cd.id
        LEFT JOIN modality_departments md ON iu.modality_dept_id = md.id
        WHERE 1=1
    """
    
    params = []
    
    if patient_id:
        query += " AND iu.patient_id = ?"
        params.append(patient_id)
    
    if clinical_dept_id:
        query += " AND iu.clinical_dept_id = ?"
        params.append(clinical_dept_id)
    
    query += " ORDER BY iu.created_at DESC LIMIT ?"
    params.append(limit)
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


def log_audit(user_id, action, resource_type=None, resource_id=None, 
              description=None, status='success'):
    """
    記錄審計日誌
    
    Args:
        user_id: 使用者 ID
        action: 動作
        resource_type: 資源類型
        resource_id: 資源 ID
        description: 描述
        status: 狀態 ('success', 'failed', 'warning')
    """
    conn = connect_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO audit_logs (user_id, action, resource_type, resource_id, 
                                  description, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, action, resource_type, resource_id, description, status))
        
        conn.commit()
    except Exception as e:
        print(f"⚠️ 記錄審計日誌失敗: {e}")
    finally:
        conn.close()


def get_user_by_username(username):
    """根據使用者名稱取得使用者資訊"""
    conn = connect_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT u.*, r.code as role_code, r.name as role_name,
               cd.name as clinical_dept_name
        FROM users u
        LEFT JOIN roles r ON u.role_id = r.id
        LEFT JOIN clinical_departments cd ON u.clinical_dept_id = cd.id
        WHERE u.username = ? AND u.is_active = 1
    """, (username,))
    
    row = cursor.fetchone()
    conn.close()
    
    return dict(row) if row else None


def list_patients(clinical_dept_id=None, is_active=True):
    """
    列出病患清單
    
    Args:
        clinical_dept_id: 臨床科別 ID（可選）
        is_active: 是否啟用
    
    Returns:
        list: 病患記錄列表
    """
    conn = connect_db()
    cursor = conn.cursor()
    
    query = """
        SELECT p.*, cd.name as clinical_dept_name, u.full_name as doctor_name
        FROM patients p
        LEFT JOIN clinical_departments cd ON p.clinical_dept_id = cd.id
        LEFT JOIN users u ON p.primary_doctor_id = u.id
        WHERE p.is_active = ?
    """
    
    params = [1 if is_active else 0]
    
    if clinical_dept_id:
        query += " AND p.clinical_dept_id = ?"
        params.append(clinical_dept_id)
    
    query += " ORDER BY p.created_at DESC"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


# ========== 主程式 ==========
if __name__ == "__main__":
    print("=" * 60)
    print("IRIS 智慧影像系統 - 資料庫初始化程式")
    print("=" * 60)
    print()
    
    # 檢查資料庫是否已存在
    if os.path.exists(DB_PATH):
        response = input(f"⚠️  資料庫 {DB_PATH} 已存在，是否覆蓋？(y/N): ")
        if response.lower() != 'y':
            print("❌ 取消初始化")
            exit(0)
        else:
            os.remove(DB_PATH)
            print("🗑️  已刪除舊資料庫\n")
    
    # 初始化資料庫
    init_database()
    
    print("\n" + "=" * 60)
    print("初始化完成！")
    print("=" * 60)
