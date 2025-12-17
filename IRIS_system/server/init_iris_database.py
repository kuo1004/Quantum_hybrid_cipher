# -*- coding: utf-8 -*-
"""
init_iris_database.py - IRIS 醫療影像系統資料庫初始化腳本

功能：
1. 建立完整的 IRIS_system.db 資料庫
2. 建立所有必要的資料表
3. 插入範例資料（含 3 個病人和完整 DICOM 資料）
4. 可獨立執行

執行方式：
    python init_iris_database.py
"""

import os
import sqlite3
from datetime import datetime, timedelta
import random


class IRISDatabaseInitializer:
    """IRIS 資料庫初始化器"""
    
    def __init__(self, db_path="IRIS_system.db"):
        self.db_path = db_path
        self.conn = None
        self.cursor = None
    
    def connect(self):
        """連接資料庫"""
        if os.path.exists(self.db_path):
            print(f"⚠️  資料庫已存在: {self.db_path}")
            response = input("是否要刪除並重建？ (y/n): ")
            if response.lower() == 'y':
                os.remove(self.db_path)
                print(f"✓ 已刪除舊資料庫")
            else:
                print("❌ 取消初始化")
                return False
        
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.cursor = self.conn.cursor()
        print(f"✓ 已連接到資料庫: {self.db_path}")
        return True
    
    def create_tables(self):
        """建立所有資料表"""
        print("\n📋 建立資料表...")
        
        # 1. Clinical Departments 表（臨床科別）
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS clinical_departments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("  ✓ clinical_departments")
        
        # 2. Modality Departments 表（影像檢查科別）
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS departments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("  ✓ departments (modality)")
        
        # 3. Users 表（使用者）
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                role TEXT DEFAULT 'nurse',
                full_name TEXT,
                email TEXT,
                clinical_dept_id INTEGER,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                FOREIGN KEY (clinical_dept_id) REFERENCES clinical_departments(id)
            )
        """)
        print("  ✓ users")
        
        # 4. Patients 表（病患）
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                patient_id TEXT UNIQUE NOT NULL,
                birthday DATE NOT NULL,
                gender TEXT DEFAULT 'O',
                bloodtype TEXT,
                mrn TEXT UNIQUE,
                nationalid TEXT,
                phone TEXT,
                address TEXT,
                email TEXT,
                emergency_contact TEXT,
                emergency_phone TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("  ✓ patients")
        
        # 5. DICOM Studies 表（檢查）
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS dicom_studies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL,
                study_instance_uid TEXT UNIQUE NOT NULL,
                study_date DATE NOT NULL,
                study_time TEXT,
                study_description TEXT,
                accession_number TEXT UNIQUE,
                referring_physician TEXT,
                institution_name TEXT DEFAULT 'IRIS Medical Center',
                study_status TEXT DEFAULT 'completed',
                clinical_dept_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
                FOREIGN KEY (clinical_dept_id) REFERENCES clinical_departments(id)
            )
        """)
        print("  ✓ dicom_studies")
        
        # 6. DICOM Series 表（序列）
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS dicom_series (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                study_id INTEGER NOT NULL,
                series_instance_uid TEXT UNIQUE NOT NULL,
                modality TEXT NOT NULL,
                body_part TEXT,
                series_number INTEGER,
                series_description TEXT,
                laterality TEXT,
                protocol_name TEXT,
                instance_count INTEGER DEFAULT 0,
                modality_dept_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (study_id) REFERENCES dicom_studies(id) ON DELETE CASCADE,
                FOREIGN KEY (modality_dept_id) REFERENCES departments(id)
            )
        """)
        print("  ✓ dicom_series")
        
        # 7. DICOM Instances 表（影像實例）
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS dicom_instances (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                series_id INTEGER NOT NULL,
                uploader_id INTEGER,
                sop_instance_uid TEXT UNIQUE NOT NULL,
                instance_number INTEGER,
                acquisition_time TEXT,
                acquisition_date DATE,
                
                -- DICOM 檔案資訊
                original_data BLOB NOT NULL,
                mime_type TEXT DEFAULT 'application/dicom',
                filename TEXT NOT NULL,
                file_size INTEGER,
                
                -- 病患資訊（DICOM Tag）
                patient_name TEXT,
                patient_id_tag TEXT,
                patient_birth_date TEXT,
                patient_sex TEXT,
                
                -- 檢查資訊
                study_date TEXT,
                study_description TEXT,
                modality TEXT,
                body_part TEXT,
                
                -- 影像參數
                rows INTEGER,
                columns INTEGER,
                bits_allocated INTEGER,
                bits_stored INTEGER,
                pixel_spacing TEXT,
                slice_thickness REAL,
                slice_location REAL,
                
                -- 顯示參數
                window_center TEXT,
                window_width TEXT,
                rescale_intercept REAL,
                rescale_slope REAL,
                
                -- 設備資訊
                manufacturer TEXT,
                manufacturer_model TEXT,
                station_name TEXT,
                
                -- 縮圖
                thumbnail BLOB,
                
                -- 時間戳記
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY (series_id) REFERENCES dicom_series(id) ON DELETE CASCADE,
                FOREIGN KEY (uploader_id) REFERENCES users(id)
            )
        """)
        print("  ✓ dicom_instances")
        
        # 8. Image Uploads 表（一般影像上傳，非 DICOM）
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS imageuploads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL,
                uploader_id INTEGER,
                imagedata BLOB NOT NULL,
                thumbdata BLOB,
                mime TEXT,
                filename TEXT NOT NULL,
                sizebytes INTEGER,
                description TEXT,
                modality_dept_id INTEGER,
                clinical_dept_id INTEGER,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
                FOREIGN KEY (uploader_id) REFERENCES users(id),
                FOREIGN KEY (modality_dept_id) REFERENCES departments(id),
                FOREIGN KEY (clinical_dept_id) REFERENCES clinical_departments(id)
            )
        """)
        print("  ✓ imageuploads")
        
        # 9. Audit Log 表（操作日誌）
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT NOT NULL,
                table_name TEXT,
                record_id INTEGER,
                old_value TEXT,
                new_value TEXT,
                ip_address TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        print("  ✓ audit_log")
        
        self.conn.commit()
        print("✓ 所有資料表建立完成\n")
    
    def insert_default_data(self):
        """插入預設資料"""
        print("📥 插入預設資料...")
        
        # 1. 臨床科別
        clinical_depts = [
            ("CARD", "心臟內科", "Cardiology"),
            ("NEU", "神經內科", "Neurology"),
            ("ORTHO", "骨科", "Orthopedics"),
            ("RAD", "放射科", "Radiology"),
            ("SURG", "外科", "Surgery"),
            ("GI", "腸胃科", "Gastroenterology"),
            ("ENDO", "內分泌科", "Endocrinology"),
            ("ONCO", "腫瘤科", "Oncology"),
        ]
        
        for code, name, desc in clinical_depts:
            self.cursor.execute(
                "INSERT INTO clinical_departments (code, name, description) VALUES (?, ?, ?)",
                (code, name, desc)
            )
        print("  ✓ 8 個臨床科別")
        
        # 2. Modality 科別
        modality_depts = [
            ("CT", "電腦斷層掃描", "Computed Tomography"),
            ("MR", "磁共振成像", "Magnetic Resonance Imaging"),
            ("CR", "計算機放射成像", "Computed Radiography"),
            ("DX", "數位X光", "Digital Radiography"),
            ("US", "超音波", "Ultrasound"),
            ("NM", "核醫學", "Nuclear Medicine"),
            ("PT", "正子斷層掃描", "Positron Emission Tomography"),
            ("XA", "血管攝影", "X-Ray Angiography"),
            ("MG", "乳房攝影", "Mammography"),
        ]
        
        for code, name, desc in modality_depts:
            self.cursor.execute(
                "INSERT INTO departments (code, name, description) VALUES (?, ?, ?)",
                (code, name, desc)
            )
        print("  ✓ 9 個 Modality 科別")
        
        # 3. 使用者
        users = [
            ("admin", "admin123", "admin", "系統管理員", "admin@iris.hospital", None),
            ("dr_wang", "doctor123", "doctor", "王大明醫師", "wang@iris.hospital", 1),  # 心臟內科
            ("dr_lee", "doctor123", "doctor", "李小華醫師", "lee@iris.hospital", 2),    # 神經內科
            ("dr_chen", "doctor123", "doctor", "陳建國醫師", "chen@iris.hospital", 3),  # 骨科
            ("nurse_liu", "nurse123", "nurse", "劉護理師", "liu@iris.hospital", None),
            ("tech_huang", "tech123", "radtech", "黃放射師", "huang@iris.hospital", 4), # 放射科
        ]
        
        for username, password, role, full_name, email, dept_id in users:
            self.cursor.execute("""
                INSERT INTO users (username, password, role, full_name, email, clinical_dept_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (username, password, role, full_name, email, dept_id))
        print("  ✓ 6 個使用者")
        
        self.conn.commit()
        print("✓ 預設資料插入完成\n")
    
    def insert_sample_patients(self):
        """插入範例病患（3 位）"""
        print("👥 插入範例病患...")
        
        patients = [
            {
                'name': '張三豐',
                'patient_id': 'P2024001',
                'birthday': '1955-03-15',
                'gender': 'M',
                'bloodtype': 'A',
                'mrn': 'MRN2024001',
                'nationalid': 'A123456789',
                'phone': '0912-345-678',
                'address': '台北市信義區信義路五段7號',
                'email': 'chang@example.com',
                'emergency_contact': '張小明（子）',
                'emergency_phone': '0923-456-789',
                'notes': '高血壓病史，定期追蹤'
            },
            {
                'name': '李美玲',
                'patient_id': 'P2024002',
                'birthday': '1968-07-22',
                'gender': 'F',
                'bloodtype': 'O',
                'mrn': 'MRN2024002',
                'nationalid': 'B234567890',
                'phone': '0922-567-890',
                'address': '新北市板橋區文化路一段188號',
                'email': 'lee@example.com',
                'emergency_contact': '李大華（夫）',
                'emergency_phone': '0933-678-901',
                'notes': '糖尿病患者，需控制飲食'
            },
            {
                'name': '王志明',
                'patient_id': 'P2024003',
                'birthday': '1982-11-08',
                'gender': 'M',
                'bloodtype': 'B',
                'mrn': 'MRN2024003',
                'nationalid': 'C345678901',
                'phone': '0933-789-012',
                'address': '桃園市桃園區中正路100號',
                'email': 'wang@example.com',
                'emergency_contact': '王小芳（妻）',
                'emergency_phone': '0944-890-123',
                'notes': '無特殊病史'
            }
        ]
        
        patient_ids = []
        for patient in patients:
            self.cursor.execute("""
                INSERT INTO patients (
                    name, patient_id, birthday, gender, bloodtype, mrn, nationalid,
                    phone, address, email, emergency_contact, emergency_phone, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                patient['name'], patient['patient_id'], patient['birthday'],
                patient['gender'], patient['bloodtype'], patient['mrn'],
                patient['nationalid'], patient['phone'], patient['address'],
                patient['email'], patient['emergency_contact'],
                patient['emergency_phone'], patient['notes']
            ))
            patient_ids.append(self.cursor.lastrowid)
            print(f"  ✓ {patient['name']} (MRN: {patient['mrn']})")
        
        self.conn.commit()
        print("✓ 3 位病患建立完成\n")
        return patient_ids
    
    def insert_dicom_data(self, patient_ids):
        """插入 DICOM 範例資料"""
        print("🏥 插入 DICOM 範例資料...")
        
        # 為每位病患建立檢查資料
        study_scenarios = [
            {
                'patient_idx': 0,
                'patient_name': '張三豐',
                'description': '心臟 CT 檢查',
                'modality': 'CT',
                'body_part': 'CHEST',
                'dept_id': 1,  # CT
                'clinical_dept_id': 1,  # 心臟內科
                'series_count': 2,
                'instances_per_series': 3
            },
            {
                'patient_idx': 1,
                'patient_name': '李美玲',
                'description': '腦部 MRI 檢查',
                'modality': 'MR',
                'body_part': 'BRAIN',
                'dept_id': 2,  # MR
                'clinical_dept_id': 2,  # 神經內科
                'series_count': 2,
                'instances_per_series': 4
            },
            {
                'patient_idx': 2,
                'patient_name': '王志明',
                'description': '膝關節 X 光檢查',
                'modality': 'DX',
                'body_part': 'KNEE',
                'dept_id': 4,  # DX
                'clinical_dept_id': 3,  # 骨科
                'series_count': 1,
                'instances_per_series': 2
            }
        ]
        
        base_date = datetime.now() - timedelta(days=30)
        
        for scenario in study_scenarios:
            patient_id = patient_ids[scenario['patient_idx']]
            study_date = (base_date + timedelta(days=random.randint(0, 30))).strftime('%Y-%m-%d')
            study_time = f"{random.randint(8, 17):02d}:{random.randint(0, 59):02d}:00"
            
            # 生成唯一的 Study Instance UID
            study_uid = f"1.2.840.10008.5.1.4.1.1.1.{random.randint(100000, 999999)}"
            accession_number = f"ACC{datetime.now().strftime('%Y%m%d')}{random.randint(1000, 9999)}"
            
            # 插入 Study
            self.cursor.execute("""
                INSERT INTO dicom_studies (
                    patient_id, study_instance_uid, study_date, study_time,
                    study_description, accession_number, referring_physician,
                    institution_name, clinical_dept_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                patient_id, study_uid, study_date, study_time,
                scenario['description'], accession_number, "Dr. Wang",
                "IRIS Medical Center", scenario['clinical_dept_id']
            ))
            study_id = self.cursor.lastrowid
            
            print(f"  ✓ Study: {scenario['patient_name']} - {scenario['description']}")
            
            # 為每個 Study 建立 Series
            for series_num in range(1, scenario['series_count'] + 1):
                series_uid = f"1.2.840.10008.5.1.4.1.1.2.{random.randint(100000, 999999)}"
                series_desc = f"{scenario['description']} - Series {series_num}"
                
                self.cursor.execute("""
                    INSERT INTO dicom_series (
                        study_id, series_instance_uid, modality, body_part,
                        series_number, series_description, instance_count,
                        modality_dept_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    study_id, series_uid, scenario['modality'], scenario['body_part'],
                    series_num, series_desc, scenario['instances_per_series'],
                    scenario['dept_id']
                ))
                series_id = self.cursor.lastrowid
                
                print(f"    → Series {series_num}: {scenario['modality']} - {scenario['body_part']}")
                
                # 為每個 Series 建立 Instances
                for inst_num in range(1, scenario['instances_per_series'] + 1):
                    sop_uid = f"1.2.840.10008.5.1.4.1.1.3.{random.randint(100000, 999999)}"
                    
                    # 生成模擬的 DICOM 資料（實際應用中這裡會是真實的 DICOM 檔案）
                    fake_dicom_data = self._generate_fake_dicom_data(
                        scenario['patient_name'],
                        scenario['modality'],
                        inst_num
                    )
                    
                    acquisition_time = f"{random.randint(8, 17):02d}:{random.randint(0, 59):02d}:{random.randint(0, 59):02d}"
                    filename = f"{scenario['modality']}_{scenario['body_part']}_{series_num:03d}_{inst_num:04d}.dcm"
                    
                    self.cursor.execute("""
                        INSERT INTO dicom_instances (
                            series_id, uploader_id, sop_instance_uid, instance_number,
                            acquisition_time, acquisition_date, original_data, mime_type,
                            filename, file_size, patient_name, patient_id_tag,
                            study_date, modality, body_part, rows, columns,
                            bits_allocated, bits_stored, pixel_spacing, slice_thickness,
                            window_center, window_width, manufacturer, manufacturer_model
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        series_id, 6,  # uploader_id = tech_huang
                        sop_uid, inst_num, acquisition_time, study_date,
                        fake_dicom_data, 'application/dicom', filename, len(fake_dicom_data),
                        scenario['patient_name'], f"P2024{scenario['patient_idx']+1:03d}",
                        study_date, scenario['modality'], scenario['body_part'],
                        512, 512, 16, 12, "0.5\\0.5", 5.0,
                        "40", "400", "IRIS Medical Imaging", "IRIS-CT-1000"
                    ))
                    
                    print(f"      • Instance {inst_num}: {filename}")
        
        self.conn.commit()
        print("✓ DICOM 資料建立完成\n")
    
    def _generate_fake_dicom_data(self, patient_name, modality, instance_num):
        """生成模擬的 DICOM 資料"""
        # 這裡生成一個簡單的模擬 DICOM 資料
        # 實際應用中應該使用真實的 DICOM 檔案
        fake_data = f"DICM_FAKE_DATA_{patient_name}_{modality}_{instance_num}".encode('utf-8')
        fake_data += b'\x00' * 1024  # 填充到 1KB
        return fake_data
    
    def create_indexes(self):
        """建立索引以提升查詢效能"""
        print("🔍 建立索引...")
        
        indexes = [
            ("idx_patients_mrn", "patients", "mrn"),
            ("idx_patients_patient_id", "patients", "patient_id"),
            ("idx_studies_patient_id", "dicom_studies", "patient_id"),
            ("idx_studies_study_uid", "dicom_studies", "study_instance_uid"),
            ("idx_studies_date", "dicom_studies", "study_date"),
            ("idx_series_study_id", "dicom_series", "study_id"),
            ("idx_series_modality", "dicom_series", "modality"),
            ("idx_instances_series_id", "dicom_instances", "series_id"),
            ("idx_instances_sop_uid", "dicom_instances", "sop_instance_uid"),
            ("idx_uploads_patient_id", "imageuploads", "patient_id"),
            ("idx_audit_user_id", "audit_log", "user_id"),
        ]
        
        for idx_name, table_name, column_name in indexes:
            try:
                self.cursor.execute(f"""
                    CREATE INDEX IF NOT EXISTS {idx_name} 
                    ON {table_name}({column_name})
                """)
                print(f"  ✓ {idx_name}")
            except Exception as e:
                print(f"  ⚠️ {idx_name}: {e}")
        
        self.conn.commit()
        print("✓ 索引建立完成\n")
    
    def show_statistics(self):
        """顯示資料庫統計"""
        print("📊 資料庫統計:")
        
        stats = [
            ("臨床科別", "clinical_departments"),
            ("Modality 科別", "departments"),
            ("使用者", "users"),
            ("病患", "patients"),
            ("DICOM Studies", "dicom_studies"),
            ("DICOM Series", "dicom_series"),
            ("DICOM Instances", "dicom_instances"),
            ("一般影像上傳", "imageuploads"),
        ]
        
        for name, table in stats:
            self.cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = self.cursor.fetchone()[0]
            print(f"  • {name}: {count} 筆")
        
        print()
    
    def close(self):
        """關閉資料庫連接"""
        if self.conn:
            self.conn.close()
            print(f"✓ 資料庫連接已關閉\n")
    
    def initialize(self):
        """執行完整初始化流程"""
        print("=" * 60)
        print("IRIS 醫療影像系統資料庫初始化")
        print("=" * 60)
        print()
        
        if not self.connect():
            return False
        
        try:
            # 1. 建立資料表
            self.create_tables()
            
            # 2. 插入預設資料
            self.insert_default_data()
            
            # 3. 插入範例病患
            patient_ids = self.insert_sample_patients()
            
            # 4. 插入 DICOM 資料
            self.insert_dicom_data(patient_ids)
            
            # 5. 建立索引
            self.create_indexes()
            
            # 6. 顯示統計
            self.show_statistics()
            
            print("=" * 60)
            print("✅ 資料庫初始化完成！")
            print("=" * 60)
            print(f"\n資料庫檔案: {os.path.abspath(self.db_path)}")
            print(f"檔案大小: {os.path.getsize(self.db_path) / 1024:.2f} KB")
            print()
            print("預設登入帳號:")
            print("  管理員: admin / admin123")
            print("  醫師: dr_wang / doctor123")
            print("  護理師: nurse_liu / nurse123")
            print("  放射師: tech_huang / tech123")
            print()
            
            return True
            
        except Exception as e:
            print(f"\n❌ 初始化過程發生錯誤: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        finally:
            self.close()


def main():
    """主程式"""
    initializer = IRISDatabaseInitializer("IRIS_system.db")
    success = initializer.initialize()
    
    if success:
        print("🎉 您現在可以將 IRIS_system.db 整合到您的系統中使用")
        print()
        return 0
    else:
        print("❌ 初始化失敗，請檢查錯誤訊息")
        return 1


if __name__ == "__main__":
    exit(main())
