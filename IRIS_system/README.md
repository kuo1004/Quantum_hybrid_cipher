# IRIS 醫療影像系統 - 更新說明

## 📋 版本資訊

**更新日期**: 2025-11-05  
**更新類型**: 支線功能更新  


---

## 🎯 本次更新概述

本次更新為系統支線功能的重大改版，包含介面優化、資料庫架構調整、醫生分科管理等核心功能的新增與改進。

---

## ✨ 主要更新內容

### 1. 🎨 介面更改

#### 使用者介面優化
- 重新設計病患管理介面，提升操作流暢度
- 改進影像查看功能的使用者體驗
- 優化影像上傳流程的視覺回饋
- 調整縮圖顯示方式，支援更好的預覽效果






### 2. 👨‍⚕️ 新增醫生分科功能

#### 臨床科別管理
- 支援多科別分類系統
- 科別與醫生帳號關聯
- 科別權限管理
- 跨科別協作支援

#### 影像科別管理
- 影像檢查類型分類 (X-Ray、CT、MRI、超音波等)
- 科別專屬影像管理
- 科別間影像共享機制



### 前置需求
- Python 3.8+
- SQLite 3
- 相關 Python 套件 (詳見 requirements.txt)


### 3. 啟動步驟


    ```
    # 終端機 1: CA Server
    cd CA/
    python ca_server.py 8001

    # 終端機 2: Hospital Server  
    cd server/
    #python server_integrated.py 8200 localhost 8001
    python server_integrated.py 8200 (ip adress) 8001

    # 終端機 3: GUI Client
    cd client/
    python main.py
    (需自行到程式碼更改ip adress連線位址，若是皆由本地開啟 則不需更改)

    ```