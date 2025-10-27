# -*- coding: utf-8 -*-

"""
database.py - 資料庫連線與初始化模組 (修正版)
"""

import sqlite3
import os
DB_PATH = "medical_system.db"

def connect_db():
    """連接到本地 SQLite 資料庫"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # 啟用外鍵約束
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_database():
    """初始化資料庫結構和預設資料 (修正版)"""
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

    # 建立 patients 表格
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

    # 建立影像上傳表格（修正版 - 移除 NOT NULL 約束以支援部分上傳）
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS imageuploads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER NOT NULL,
        uploader_id INTEGER NOT NULL,
        filename TEXT NOT NULL,
        mime TEXT NOT NULL,
        imagedata BLOB,
        thumbdata BLOB,
        uploaded_at TEXT NOT NULL,
        transmission_status TEXT DEFAULT 'verified',
        FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
        FOREIGN KEY (uploader_id) REFERENCES users(id) ON DELETE CASCADE
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
        FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE
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
        FOREIGN KEY (study_id) REFERENCES dicom_studies(id) ON DELETE CASCADE
    )
    """)

    # 建立 DICOM Instances 表格
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dicom_instances (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        series_id INTEGER NOT NULL,
        sop_instance_uid TEXT UNIQUE NOT NULL,
        instance_number INTEGER,
        uploader_id INTEGER,
        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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
        FOREIGN KEY (series_id) REFERENCES dicom_series(id) ON DELETE CASCADE,
        FOREIGN KEY (uploader_id) REFERENCES users(id) ON DELETE SET NULL
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

    # 插入範例病人
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
        except sqlite3.IntegrityError:
            pass

    conn.commit()
    conn.close()
    print(f"✓ 資料庫初始化完成: {DB_PATH}")


def insert_image_upload(patient_id, uploader_id, filename, mime, imagedata, thumbdata=None):
    """
    插入影像到 imageuploads 表格
    
    Args:
        patient_id: 病人ID
        uploader_id: 上傳者ID
        filename: 檔案名稱
        mime: MIME類型
        imagedata: 影像二進位資料（bytes）
        thumbdata: 縮圖二進位資料（bytes，可選）
    
    Returns:
        插入的影像ID，失敗返回 None
    """
    try:
        conn = connect_db()
        cursor = conn.cursor()
        
        from datetime import datetime
        uploaded_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 使用 sqlite3.Binary() 包裝 BLOB 資料
        cursor.execute("""
        INSERT INTO imageuploads (patient_id, uploader_id, filename, mime, imagedata, thumbdata, uploaded_at, transmission_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            patient_id, 
            uploader_id, 
            filename, 
            mime, 
            sqlite3.Binary(imagedata) if imagedata else None,
            sqlite3.Binary(thumbdata) if thumbdata else None,
            uploaded_at,
            'verified'
        ))
        
        image_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        print(f"✓ 成功插入影像: {filename} (ID: {image_id})")
        return image_id
        
    except sqlite3.Error as e:
        print(f"✗ 插入影像失敗: {e}")
        if conn:
            conn.close()
        return None


def get_image_data(image_id):
    """
    取得指定影像的完整資料
    
    Args:
        image_id: 影像ID
    
    Returns:
        (imagedata, thumbdata, mime) 或 (None, None, None)
    """
    try:
        conn = connect_db()
        cursor = conn.cursor()
        
        cursor.execute("""
        SELECT imagedata, thumbdata, mime 
        FROM imageuploads 
        WHERE id = ?
        """, (image_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            # 轉換 bytes 資料
            imagedata = bytes(row[0]) if row[0] else None
            thumbdata = bytes(row[1]) if row[1] else None
            mime = row[2]
            return imagedata, thumbdata, mime
        
        return None, None, None
        
    except sqlite3.Error as e:
        print(f"✗ 讀取影像失敗: {e}")
        if conn:
            conn.close()
        return None, None, None


def verify_database_integrity():
    """驗證資料庫完整性並顯示統計資訊"""
    try:
        conn = connect_db()
        cursor = conn.cursor()
        
        print("\n=== 資料庫完整性檢查 ===")
        
        # 檢查各表格資料量
        tables = ['users', 'patients', 'imageuploads', 'dicom_studies', 'dicom_series', 'dicom_instances']
        
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"📊 {table}: {count} 筆資料")
        
        # 檢查影像資料完整性
        cursor.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN imagedata IS NOT NULL THEN 1 ELSE 0 END) as has_image,
            SUM(CASE WHEN thumbdata IS NOT NULL THEN 1 ELSE 0 END) as has_thumb,
            SUM(CASE WHEN imagedata IS NULL AND thumbdata IS NULL THEN 1 ELSE 0 END) as empty
        FROM imageuploads
        """)
        
        stats = cursor.fetchone()
        if stats[0] > 0:
            print(f"\n📸 影像統計:")
            print(f"   總數: {stats[0]}")
            print(f"   有完整影像: {stats[1]}")
            print(f"   有縮圖: {stats[2]}")
            print(f"   無資料: {stats[3]}")
        
        # 檢查外鍵完整性
        cursor.execute("PRAGMA foreign_key_check")
        fk_errors = cursor.fetchall()
        
        if fk_errors:
            print(f"\n⚠️  發現 {len(fk_errors)} 個外鍵約束錯誤")
            for error in fk_errors:
                print(f"   {error}")
        else:
            print("\n✓ 外鍵約束檢查通過")
        
        conn.close()
        print("=== 檢查完成 ===\n")
        
    except sqlite3.Error as e:
        print(f"✗ 資料庫檢查失敗: {e}")
        if conn:
            conn.close()

if __name__ == "__main__":
    print("開始建立資料庫...")
    if os.path.exists(DB_PATH):
        print(f"⚠️ 既有資料庫 '{DB_PATH}' 已存在，將直接檢查資料完整性。")
    else:
        init_database()
    verify_database_integrity()