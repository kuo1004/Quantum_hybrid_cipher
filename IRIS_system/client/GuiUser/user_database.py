# -*- coding: utf-8 -*-
"""
user_database.py - 本地使用者資料庫（可選資料庫位置版本）

⚠️ 注意：此資料庫僅存放使用者帳號密碼，不存放醫療資料
所有醫療影像、病患等資料由 Hospital Server 管理
"""

import sqlite3
import os
from pathlib import Path


# ============================================================
# 配置區：選擇資料庫位置
# ============================================================

# 選項 A: 使用使用者目錄（預設，推薦）
USE_USER_HOME = True

# 選項 B: 使用專案目錄（如果改為 False）
PROJECT_DIR = Path(__file__).parent.parent  # client/ 目錄


def get_user_db_path():
    """獲取使用者資料庫路徑"""
    if USE_USER_HOME:
        # 方案 A: 使用者目錄（預設）
        # Windows: C:\Users\使用者名稱\.iris_client\users.db
        # macOS: /Users/使用者名稱/.iris_client/users.db
        # Linux: /home/使用者名稱/.iris_client/users.db
        user_dir = Path.home() / ".iris_client"
        user_dir.mkdir(exist_ok=True)
        return str(user_dir / "users.db")
    else:
        # 方案 B: 專案目錄
        # 例如: D:\graduation_project\github\test\client\users.db
        db_dir = PROJECT_DIR
        db_dir.mkdir(exist_ok=True)
        return str(db_dir / "users.db")


def init_user_database():
    """初始化使用者資料庫"""
    db_path = get_user_db_path()
    
    # 檢查是否已存在
    db_exists = os.path.exists(db_path)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 創建使用者表
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL,
        full_name TEXT,
        email TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # 如果是新資料庫，插入預設使用者
    if not db_exists:
        print("ℹ️  創建新的使用者資料庫")
        
        default_users = [
            ("admin", "123", "admin", "系統管理員", "admin@hospital.tw"),
            ("doctor1", "123", "doctor", "張醫師", "doctor1@hospital.tw"),
            ("radiologist1", "123", "radiologist", "李放射師", "radio1@hospital.tw"),
            ("nurse1", "123", "nurse", "陳護理師", "nurse1@hospital.tw"),
        ]
        
        cursor.executemany("""
        INSERT INTO users (username, password, role, full_name, email)
        VALUES (?, ?, ?, ?, ?)
        """, default_users)
        
        print(f"✅ 已創建 {len(default_users)} 個預設使用者")
        print(f"   資料庫位置: {db_path}")
    
    conn.commit()
    conn.close()
    
    return db_path


def verify_user(username, password):
    """
    驗證使用者
    
    Args:
        username: 使用者名稱
        password: 密碼
        
    Returns:
        dict: 使用者資訊，失敗返回 None
    """
    db_path = get_user_db_path()
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
        SELECT id, username, role, full_name, email
        FROM users
        WHERE UPPER(username) = UPPER(?) AND password = ?
        """, (username, password))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "id": row[0],
                "username": row[1],
                "role": row[2],
                "full_name": row[3],
                "email": row[4]
            }
        
        return None
        
    except Exception as e:
        print(f"❌ 驗證使用者失敗: {e}")
        return None


def add_user(username, password, role, full_name=None, email=None):
    """
    新增使用者
    
    Args:
        username: 使用者名稱
        password: 密碼
        role: 角色 (admin/doctor/radiologist/nurse)
        full_name: 全名（可選）
        email: Email（可選）
        
    Returns:
        bool: 成功返回 True，失敗返回 False
    """
    db_path = get_user_db_path()
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
        INSERT INTO users (username, password, role, full_name, email)
        VALUES (?, ?, ?, ?, ?)
        """, (username, password, role, full_name, email))
        
        conn.commit()
        conn.close()
        
        print(f"✅ 已新增使用者: {username} ({role})")
        return True
        
    except sqlite3.IntegrityError:
        print(f"❌ 使用者名稱已存在: {username}")
        return False
    except Exception as e:
        print(f"❌ 新增使用者失敗: {e}")
        return False


def list_users():
    """列出所有使用者"""
    db_path = get_user_db_path()
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
        SELECT id, username, role, full_name, email, created_at
        FROM users
        ORDER BY id
        """)
        
        rows = cursor.fetchall()
        conn.close()
        
        users = []
        for row in rows:
            users.append({
                "id": row[0],
                "username": row[1],
                "role": row[2],
                "full_name": row[3],
                "email": row[4],
                "created_at": row[5]
            })
        
        return users
        
    except Exception as e:
        print(f"❌ 列出使用者失敗: {e}")
        return []


def change_password(username, old_password, new_password):
    """
    變更密碼
    
    Args:
        username: 使用者名稱
        old_password: 舊密碼
        new_password: 新密碼
        
    Returns:
        bool: 成功返回 True，失敗返回 False
    """
    db_path = get_user_db_path()
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 先驗證舊密碼
        cursor.execute("""
        SELECT id FROM users
        WHERE UPPER(username) = UPPER(?) AND password = ?
        """, (username, old_password))
        
        if not cursor.fetchone():
            print(f"❌ 舊密碼錯誤")
            conn.close()
            return False
        
        # 更新密碼
        cursor.execute("""
        UPDATE users
        SET password = ?
        WHERE UPPER(username) = UPPER(?)
        """, (new_password, username))
        
        conn.commit()
        conn.close()
        
        print(f"✅ 密碼已更新: {username}")
        return True
        
    except Exception as e:
        print(f"❌ 變更密碼失敗: {e}")
        return False


if __name__ == "__main__":
    # 測試
    print("="*60)
    print("🔐 使用者資料庫測試")
    print("="*60)
    
    # 顯示配置
    if USE_USER_HOME:
        print("\n📍 使用配置: 使用者目錄（預設）")
    else:
        print("\n📍 使用配置: 專案目錄")
    
    # 初始化
    db_path = init_user_database()
    print(f"\n資料庫位置: {db_path}\n")
    
    # 列出所有使用者
    print("📋 所有使用者:")
    users = list_users()
    if users:
        for user in users:
            print(f"  - {user['username']} ({user['role']}) - {user['full_name']}")
    else:
        print("  （無使用者）")
    
    # 測試驗證
    print("\n🔑 驗證測試:")
    
    # 正確的帳號密碼
    user = verify_user("admin", "123")
    if user:
        print(f"  ✅ 驗證成功: {user['username']} ({user['role']})")
    else:
        print(f"  ❌ 驗證失敗")
    
