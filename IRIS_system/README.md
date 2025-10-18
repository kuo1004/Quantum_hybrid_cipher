
# IRIS 整合性放射影像系統

IRIS 是一個醫療放射影像整合平台，具備高安全性的影像管理與傳輸功能。


1. **DICOM 資料結構**
   - Patient Level: 病人資訊
   - Study Level: 檢查資訊
   - Series Level: 序列資訊
   - Instance Level: 影像實例


2. **支援的 Modality**
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

- `main.py`：啟動使用者介面
- `start_all_server.py`：啟動後端伺服器進行加密安全傳輸
- 登入:
預設帳號:
- 醫師: `doctor1` / `123`
- 放射師: `radiologist1` / `123` (無病人管理權限)
- 護理師: `nurse1` / `123`
- 管理員: `admin` / `123`


系統架構分為前端使用者介面與後端伺服器，確保資料安全與操作便利。
