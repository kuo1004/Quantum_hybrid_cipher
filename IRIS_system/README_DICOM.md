# IRIS 智慧影像系統 - DICOM 標準版

## 📋 系統概述

本系統符合 DICOM (Digital Imaging and Communications in Medicine) 標準，專為醫療影像管理設計。

## 🏥 DICOM 標準支援

### ✅ 已實作的 DICOM 功能

1. **DICOM 資料結構**
   - Patient Level: 病人資訊
   - Study Level: 檢查資訊
   - Series Level: 序列資訊
   - Instance Level: 影像實例

2. **DICOM Tags 支援**
   - Patient Information: PatientID, PatientName, PatientBirthDate, PatientSex
   - Study Information: StudyInstanceUID, StudyDate, StudyTime, AccessionNumber
   - Series Information: SeriesInstanceUID, Modality, BodyPartExamined
   - Instance Information: SOPInstanceUID, InstanceNumber
   - Image Parameters: Rows, Columns, PixelSpacing, WindowCenter, WindowWidth

3. **支援的 Modality**
   - CT (電腦斷層掃描)
   - MR (磁共振成像)
   - CR (X光片)
   - DX (數位X光)
   - US (超音波)
   - NM (核醫學)
   - PT (正子斷層)
   - XA (血管攝影)
   - MG (乳房攝影)

## 📦 安裝需求

```bash
# 基本套件
pip install opencv-python Pillow customtkinter

# DICOM 支援
pip install pydicom

# 完整安裝
pip install opencv-python Pillow customtkinter pydicom
```

## 👥 角色權限

| 角色 | 標籤頁 | 權限 |
|------|--------|------|
| 醫師 (doctor) | 首頁、上傳影像、影像清單、病人管理 | 上傳、查看病人 |
| 放射師 (radiologist) | 首頁、上傳影像、影像清單 | 上傳、**無法查看病人資料** |
| 護理師 (nurse) | 首頁、病人管理 | 新增病人 |
| 管理員 (admin) | 全部 | 所有權限 |

## 📁 資料庫結構

### 表格說明

1. **patients** - 病人基本資料
   - 包含 DICOM PatientID

2. **dicom_studies** - DICOM 檢查
   - StudyInstanceUID (唯一識別碼)
   - StudyDate, StudyTime
   - AccessionNumber

3. **dicom_series** - DICOM 序列
   - SeriesInstanceUID (唯一識別碼)
   - Modality, BodyPart
   - SeriesNumber

4. **dicom_instances** - DICOM 影像實例
   - SOPInstanceUID (唯一識別碼)
   - 儲存原始 DICOM 檔案
   - DICOM Tags 資訊
   - 影像參數

## 🚀 使用方式

### 1. 啟動系統

```bash
python main.py
```

### 2. 登入

預設帳號:
- 醫師: `doctor1` / `123`
- 放射師: `radiologist1` / `123` (無病人管理權限)
- 護理師: `nurse1` / `123`
- 管理員: `admin` / `123`

### 3. 上傳 DICOM 檔案

1. 選擇病人
2. 上傳 `.dcm` 檔案
3. 系統自動提取 DICOM Tags
4. 建立 Study/Series/Instance 結構

### 4. 檢視 DICOM 影像

- 顯示 DICOM metadata
- 自動套用 Window Level/Width
- 保留原始診斷資訊

## 🔧 技術細節

### DICOM UID 生成

```python
StudyInstanceUID: 1.2.826.0.1.[UUID]
SeriesInstanceUID: 1.2.826.0.1.[UUID]
SOPInstanceUID: 1.2.826.0.1.[UUID]
```

### 檔案儲存

- **DICOM 檔案**: 儲存原始二進位資料 (BLOB)
- **一般影像**: 轉換為 JPEG 儲存
- **影片**: 保持原始格式

### 權限控制

放射師 (radiologist) 特別限制:
- ✅ 可以上傳影像
- ✅ 可以查看影像清單
- ❌ 無法查看病人管理
- ❌ 無法查看病人詳細資料

## 📊 DICOM 合規性

本系統遵循以下 DICOM 標準:
- DICOM PS3.3: Information Object Definitions
- DICOM PS3.5: Data Structures and Encoding
- DICOM PS3.6: Data Dictionary

## ⚠️ 注意事項

1. 本系統為教學/研究用途
2. 生產環境需要額外的安全措施
3. 建議整合 PACS 系統進行完整 DICOM 管理
4. 需要符合當地醫療資料保護法規

## 🔐 資料安全

- 本地 SQLite 資料庫
- 密碼需要加密 (建議使用 bcrypt)
- 傳輸加密 (建議使用 HTTPS)
- 存取日誌記錄

## 📞 技術支援

如有問題請參考:
- DICOM 標準: https://www.dicomstandard.org/
- pydicom 文件: https://pydicom.github.io/
