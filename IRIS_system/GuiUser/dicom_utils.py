# -*- coding: utf-8 -*-
"""
dicom_utils.py - DICOM 檔案處理工具
"""
import io
import uuid
from datetime import datetime
from PIL import Image

# 檢查是否安裝 pydicom
try:
    import pydicom
    from pydicom.dataset import Dataset, FileDataset
    PYDICOM_AVAILABLE = True
except ImportError:
    PYDICOM_AVAILABLE = False
    print("⚠️ 警告: pydicom 未安裝，DICOM 功能將受限")
    print("   安裝指令: pip install pydicom")

def is_dicom_file(file_path_or_bytes):
    """檢查是否為 DICOM 檔案"""
    if not PYDICOM_AVAILABLE:
        # 如果沒有 pydicom，只能用副檔名判斷
        if isinstance(file_path_or_bytes, str):
            return file_path_or_bytes.lower().endswith('.dcm')
        return False

    try:
        if isinstance(file_path_or_bytes, bytes):
            pydicom.dcmread(io.BytesIO(file_path_or_bytes), stop_before_pixels=True)
        else:
            pydicom.dcmread(file_path_or_bytes, stop_before_pixels=True)
        return True
    except:
        return False

def extract_dicom_metadata(file_path_or_bytes):
    """提取 DICOM metadata"""
    if not PYDICOM_AVAILABLE:
        return {
            "error": "pydicom 未安裝",
            "patient_name": "Unknown",
            "patient_id": f"PAT{uuid.uuid4().hex[:8].upper()}",
            "study_instance_uid": f"1.2.826.0.1.{uuid.uuid4().int}",
            "series_instance_uid": f"1.2.826.0.1.{uuid.uuid4().int}",
            "sop_instance_uid": f"1.2.826.0.1.{uuid.uuid4().int}",
            "modality": "OT",
            "study_date": datetime.now().strftime("%Y%m%d"),
        }

    try:
        if isinstance(file_path_or_bytes, bytes):
            ds = pydicom.dcmread(io.BytesIO(file_path_or_bytes))
        else:
            ds = pydicom.dcmread(file_path_or_bytes)

        metadata = {
            # Patient Information
            "patient_name": str(ds.get("PatientName", "Unknown")),
            "patient_id": str(ds.get("PatientID", f"PAT{uuid.uuid4().hex[:8].upper()}")),
            "patient_birth_date": str(ds.get("PatientBirthDate", "")),
            "patient_sex": str(ds.get("PatientSex", "O")),

            # Study Information
            "study_instance_uid": str(ds.get("StudyInstanceUID", f"1.2.826.0.1.{uuid.uuid4().int}")),
            "study_date": str(ds.get("StudyDate", datetime.now().strftime("%Y%m%d"))),
            "study_time": str(ds.get("StudyTime", "")),
            "study_description": str(ds.get("StudyDescription", "")),
            "accession_number": str(ds.get("AccessionNumber", "")),
            "referring_physician": str(ds.get("ReferringPhysicianName", "")),

            # Series Information
            "series_instance_uid": str(ds.get("SeriesInstanceUID", f"1.2.826.0.1.{uuid.uuid4().int}")),
            "series_number": int(ds.get("SeriesNumber", 1)),
            "modality": str(ds.get("Modality", "OT")),
            "series_description": str(ds.get("SeriesDescription", "")),
            "body_part": str(ds.get("BodyPartExamined", "")),
            "protocol_name": str(ds.get("ProtocolName", "")),

            # Instance Information
            "sop_instance_uid": str(ds.get("SOPInstanceUID", f"1.2.826.0.1.{uuid.uuid4().int}")),
            "instance_number": int(ds.get("InstanceNumber", 1)),

            # Institution Information
            "institution_name": str(ds.get("InstitutionName", "")),

            # Image Parameters
            "rows": int(ds.get("Rows", 0)) if "Rows" in ds else None,
            "columns": int(ds.get("Columns", 0)) if "Columns" in ds else None,
            "bits_allocated": int(ds.get("BitsAllocated", 0)) if "BitsAllocated" in ds else None,
            "bits_stored": int(ds.get("BitsStored", 0)) if "BitsStored" in ds else None,
            "pixel_spacing": str(ds.get("PixelSpacing", "")) if "PixelSpacing" in ds else "",
            "slice_thickness": float(ds.get("SliceThickness", 0)) if "SliceThickness" in ds else None,
            "window_center": str(ds.get("WindowCenter", "")) if "WindowCenter" in ds else "",
            "window_width": str(ds.get("WindowWidth", "")) if "WindowWidth" in ds else "",
        }

        return metadata

    except Exception as e:
        print(f"提取 DICOM metadata 錯誤: {e}")
        return {
            "error": str(e),
            "patient_name": "Unknown",
            "patient_id": f"PAT{uuid.uuid4().hex[:8].upper()}",
            "study_instance_uid": f"1.2.826.0.1.{uuid.uuid4().int}",
            "series_instance_uid": f"1.2.826.0.1.{uuid.uuid4().int}",
            "sop_instance_uid": f"1.2.826.0.1.{uuid.uuid4().int}",
            "modality": "OT",
        }

def dicom_to_image(file_path_or_bytes):
    """將 DICOM 轉換為 PIL Image（用於顯示）"""
    if not PYDICOM_AVAILABLE:
        return None

    try:
        if isinstance(file_path_or_bytes, bytes):
            ds = pydicom.dcmread(io.BytesIO(file_path_or_bytes))
        else:
            ds = pydicom.dcmread(file_path_or_bytes)

        # 獲取像素陣列
        pixel_array = ds.pixel_array

        # 正規化到 0-255
        pixel_array = pixel_array - pixel_array.min()
        pixel_array = pixel_array / pixel_array.max() * 255.0
        pixel_array = pixel_array.astype('uint8')

        # 轉換為 PIL Image
        image = Image.fromarray(pixel_array)

        # 如果是灰階影像，轉換為 RGB
        if image.mode != 'RGB':
            image = image.convert('RGB')

        return image

    except Exception as e:
        print(f"DICOM 轉 Image 錯誤: {e}")
        return None

def create_dicom_thumbnail(file_bytes, size=(240, 240)):
    """為 DICOM 檔案建立縮圖"""
    image = dicom_to_image(file_bytes)

    if image:
        image.thumbnail(size)
        buf = io.BytesIO()
        image.save(buf, format='JPEG', quality=85)
        return buf.getvalue()

    return None

def generate_uid():
    """生成 DICOM UID"""
    # 使用 UUID 生成唯一的 UID
    # 格式: 1.2.826.0.1.[UUID的整數表示]
    return f"1.2.826.0.1.{uuid.uuid4().int}"
