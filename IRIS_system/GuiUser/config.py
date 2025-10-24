# -*- coding: utf-8 -*-
"""
config.py - 系統配置與介面樣式 (DICOM 標準版)
"""
import customtkinter as ctk

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

COLOR = {
    "bg": "#F7F8FA",
    "surface": "#FFFFFF",
    "surfacealt": "#F1F4F9",
    "ink": "#0F172A",
    "inksubtle": "#49546A",
    "primary": "#2B7FFF",
    "primaryhover": "#1E66E7",
    "success": "#0FB879",
    "danger": "#E5484D",
    "muted": "#9AA6B2",
    "divider": "#E6EAF0",
    "chip": "#E9F1FF",
}

RADIUS = 8
GAP = 16
PAD = 20

FONT = {}

def init_fonts():
    """初始化字體"""
    global FONT
    try:
        FONT.update({
            "logo": ctk.CTkFont(family="SF Pro Display", size=22, weight="bold"),
            "h1": ctk.CTkFont(family="SF Pro Display", size=24, weight="bold"),
            "h2": ctk.CTkFont(family="SF Pro Display", size=18, weight="bold"),
            "h3": ctk.CTkFont(family="SF Pro Text", size=16, weight="bold"),
            "body": ctk.CTkFont(family="SF Pro Text", size=14),
            "meta": ctk.CTkFont(family="SF Pro Text", size=12),
        })
    except Exception:
        FONT.update({
            "logo": ctk.CTkFont(family="Helvetica Neue", size=22, weight="bold"),
            "h1": ctk.CTkFont(family="Helvetica Neue", size=24, weight="bold"),
            "h2": ctk.CTkFont(family="Helvetica Neue", size=18, weight="bold"),
            "h3": ctk.CTkFont(family="Helvetica Neue", size=16, weight="bold"),
            "body": ctk.CTkFont(family="Helvetica Neue", size=14),
            "meta": ctk.CTkFont(family="Helvetica Neue", size=12),
        })

def Card(parent, **kw):
    return ctk.CTkFrame(parent, corner_radius=RADIUS, fg_color=COLOR["surface"], **kw)

def Subtle(parent, **kw):
    return ctk.CTkFrame(parent, corner_radius=RADIUS, fg_color=COLOR["surfacealt"], **kw)

def SolidBtn(parent, text, cmd, w=120, h=40):
    return ctk.CTkButton(
        parent, text=text, command=cmd, width=w, height=h,
        corner_radius=RADIUS, fg_color=COLOR["primary"],
        hover_color=COLOR["primaryhover"], text_color="white", font=FONT.get("body")
    )

def OutlineBtn(parent, text, cmd, w=120, h=40):
    return ctk.CTkButton(
        parent, text=text, command=cmd, width=w, height=h,
        corner_radius=RADIUS, fg_color=COLOR["surface"],
        hover_color="#F5F7FB", border_color=COLOR["divider"], border_width=1,
        text_color=COLOR["ink"], font=FONT.get("body")
    )

# 角色權限配置 (修正放射師權限)
ROLE_UI = {
    "doctor": {
        "tabs": ["首頁", "上傳影像", "影像清單", "病人管理"],
        "can": {"upload": True, "createpatient": False, "viewpatient": True}
    },
    "radiologist": {
        "tabs": ["首頁", "上傳影像", "影像清單"],  # 移除病人管理
        "can": {"upload": True, "createpatient": False, "viewpatient": False}  # 無法查看病人
    },
    "nurse": {
        "tabs": ["首頁", "病人管理"],
        "can": {"upload": False, "createpatient": True, "viewpatient": True}
    },
    "admin": {
        "tabs": ["首頁", "上傳影像", "影像清單", "病人管理"],
        "can": {"upload": True, "createpatient": True, "viewpatient": True}
    }
}

ROLE_ZH = {
    "doctor": "醫師",
    "radiologist": "放射師",
    "nurse": "護理師",
    "admin": "管理員"
}

def tabs_for_role(role: str):
    """取得角色對應的標籤頁"""
    return ROLE_UI.get(role, ROLE_UI["nurse"])["tabs"]

def can(role: str, perm: str) -> bool:
    """檢查角色權限"""
    if role == "admin":
        return True
    return ROLE_UI.get(role, ROLE_UI["nurse"])["can"].get(perm, False)

# DICOM 相關常數
IMAGEEXTS = (".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".dcm")
VIDEOEXTS = (".mp4", ".mov", ".avi", ".mkv", ".wmv")

# DICOM Modality 類型
MODALITIES = {
    "CT": "電腦斷層掃描 (CT)",
    "MR": "磁共振成像 (MRI)",
    "CR": "X光片 (CR)",
    "DX": "數位X光 (DX)",
    "US": "超音波 (US)",
    "NM": "核醫學 (NM)",
    "PT": "正子斷層 (PET)",
    "XA": "血管攝影 (XA)",
    "RF": "透視攝影 (RF)",
    "MG": "乳房攝影 (MG)",
    "OTHER": "其他"
}

# DICOM Body Part
BODY_PARTS = [
    "頭部 (Head)",
    "頸部 (Neck)", 
    "胸部 (Chest)",
    "腹部 (Abdomen)",
    "骨盆 (Pelvis)",
    "脊椎 (Spine)",
    "上肢 (Upper Limb)",
    "下肢 (Lower Limb)",
    "心臟 (Heart)",
    "全身 (Whole Body)"
]