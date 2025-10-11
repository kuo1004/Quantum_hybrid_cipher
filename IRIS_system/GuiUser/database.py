# -*- coding: utf-8 -*-
"""
database.py - 資料庫連線與初始化模組 (DICOM 標準版)
"""
import sqlite3

DB_PATH = "medical_system.db"

def connect_db():
    """連接到本地 SQLite 資料庫"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """初始化資料庫結構和預設資料 (DICOM 標準)"""
    conn = connect_db()
    cursor = conn.cursor()

    # 建立 users 表格
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'nurse',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 建立 patients 表格 (加入 DICOM Patient ID)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            patient_id TEXT UNIQUE,
            birthday DATE NOT NULL,
            bloodtype TEXT,
            mrn TEXT,
            nationalid TEXT,
            gender TEXT DEFAULT 'O',
            phone TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 建立 DICOM Studies 表格
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (patient_id) REFERENCES patients(id)
        )
    """)

    # 建立 DICOM Series 表格
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dicom_series (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            study_id INTEGER NOT NULL,
            series_instance_uid TEXT UNIQUE NOT NULL,
            series_number INTEGER,
            modality TEXT,
            series_description TEXT,
            body_part TEXT,
            protocol_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (study_id) REFERENCES dicom_studies(id)
        )
    """)

    # 建立 DICOM Instances 表格 (影像/影片)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dicom_instances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            series_id INTEGER NOT NULL,
            sop_instance_uid TEXT UNIQUE NOT NULL,
            instance_number INTEGER,
            uploader_id INTEGER,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            -- 原始檔案資料
            original_data BLOB NOT NULL,
            mime_type TEXT DEFAULT 'application/dicom',
            filename TEXT,
            file_size INTEGER,

            -- DICOM Tags
            patient_name TEXT,
            patient_id_tag TEXT,
            study_date TEXT,
            modality TEXT,
            body_part TEXT,

            -- 影像參數 (針對 DICOM 影像)
            rows INTEGER,
            columns INTEGER,
            bits_allocated INTEGER,
            bits_stored INTEGER,
            pixel_spacing TEXT,
            slice_thickness REAL,
            window_center TEXT,
            window_width TEXT,

            -- 縮圖 (快速顯示用)
            thumbnail BLOB,

            FOREIGN KEY (series_id) REFERENCES dicom_series(id),
            FOREIGN KEY (uploader_id) REFERENCES users(id)
        )
    """)

    # 插入預設使用者
    default_users = [
        ('admin', '123', 'admin'),
        ('doctor1', '123', 'doctor'),
        ('radiologist1', '123', 'radiologist'),
        ('nurse1', '123', 'nurse')
    ]

    for username, password, role in default_users:
        try:
            cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                          (username, password, role))
        except sqlite3.IntegrityError:
            pass

    # 插入範例病人 (加入 DICOM Patient ID)
    sample_patients = [
        ('王小明', 'PAT001', '1990-01-01', 'O', 'MRN001', 'A123456789', 'M', '0912-345-678'),
        ('李小華', 'PAT002', '1992-02-02', 'A', 'MRN002', 'B987654321', 'F', '0923-456-789')
    ]

    for name, pat_id, birthday, bloodtype, mrn, nid, gender, phone in sample_patients:
        try:
            cursor.execute("""
                INSERT INTO patients (name, patient_id, birthday, bloodtype, mrn, nationalid, gender, phone)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, pat_id, birthday, bloodtype, mrn, nid, gender, phone))
        except:
            pass

    conn.commit()
    conn.close()
    print(f"✓ DICOM 標準資料庫初始化完成: {DB_PATH}")