# -*- coding: utf-8 -*-
"""
config.py - 系統配置與介面樣式 (後端整合版)
更新：使用正式醫療系統標準字體
"""
import customtkinter as ctk
import platform

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

# ============================================================
# 後端 API 配置
# ============================================================
API_CONFIG = {
    "SERVER_HOST": "localhost",
    "SERVER_PORT": 8200,
    "CA_HOST": "localhost",
    "CA_PORT": 8001,
    "TIMEOUT": 30,  # 請求超時時間（秒）
}

def get_api_url(endpoint):
    """獲取 API 完整 URL"""
    base_url = f"http://{API_CONFIG['SERVER_HOST']}:{API_CONFIG['SERVER_PORT']}"
    return f"{base_url}{endpoint}"

def get_ca_url(endpoint):
    """獲取 CA API 完整 URL"""
    base_url = f"http://{API_CONFIG['CA_HOST']}:{API_CONFIG['CA_PORT']}"
    return f"{base_url}{endpoint}"

# ============================================================
# UI 樣式配置
# ============================================================
COLOR = {
    "bg": "#F7F8FA",
    "surface": "#FFFFFF",
    "surfacealt": "#F1F4F9",
    "ink": "#0F172A",
    "inksubtle": "#49546A",
    "primary": "#2B7FFF",
    "primaryhover": "#1E66E7",
    "success": "#0FB879",
    "warning": "#F59E0B",
    "danger": "#E5484D",
    "muted": "#9AA6B2",
    "divider": "#E6EAF0",
    "chip": "#E9F1FF",
}

RADIUS = 8
GAP = 16
PAD = 20

FONT = {}

def get_system_font():
    """
    根據作業系統取得最適合的正式字體
    
    字體選擇原則：
    - Windows: Segoe UI (Microsoft 官方 UI 字體) / Microsoft JhengHei (正黑體)
    - macOS: SF Pro (Apple 系統字體) / PingFang TC (蘋方)
    - Linux: Noto Sans CJK TC / Ubuntu / DejaVu Sans
    
    這些都是各平台上用於正式應用程式的標準字體
    """
    system = platform.system()
    
    if system == "Windows":
        # Windows 正式系統字體
        # Segoe UI: Windows Vista 以來的標準 UI 字體
        # Microsoft JhengHei: 微軟正黑體，繁體中文標準字體
        return {
            "primary": "Microsoft JhengHei UI",  # 微軟正黑體 UI 版
            "fallback": "Segoe UI",              # 英文備用
            "mono": "Consolas"                   # 等寬字體
        }
    elif system == "Darwin":  # macOS
        # macOS 正式系統字體
        # SF Pro: Apple 官方系統字體
        # PingFang TC: 蘋方繁體，macOS 預設中文字體
        return {
            "primary": "PingFang TC",            # 蘋方繁體
            "fallback": "SF Pro Display",        # 英文備用
            "mono": "SF Mono"                    # 等寬字體
        }
    else:  # Linux
        # Linux 正式系統字體
        # Noto Sans CJK TC: Google 開源字體，支援繁體中文
        return {
            "primary": "Noto Sans CJK TC",       # Google Noto 繁體
            "fallback": "Ubuntu",                # Ubuntu 預設
            "mono": "Ubuntu Mono"                # 等寬字體
        }


def init_fonts():
    """
    初始化正式系統字體
    
    字體大小規範（依照 UI/UX 設計標準）：
    - Logo/標題: 22-24px (醒目但不過大)
    - H1 大標題: 24px
    - H2 中標題: 18px  
    - H3 小標題: 16px
    - Body 內文: 14px (最佳閱讀大小)
    - Meta 說明: 12px (次要資訊)
    """
    global FONT
    
    system_fonts = get_system_font()
    primary_font = system_fonts["primary"]
    fallback_font = system_fonts["fallback"]
    
    try:
        # 嘗試使用主要字體（中文字體）
        FONT.update({
            "logo": ctk.CTkFont(family=primary_font, size=22, weight="bold"),
            "h1": ctk.CTkFont(family=primary_font, size=24, weight="bold"),
            "h2": ctk.CTkFont(family=primary_font, size=18, weight="bold"),
            "h3": ctk.CTkFont(family=primary_font, size=16, weight="bold"),
            "body": ctk.CTkFont(family=primary_font, size=14),
            "meta": ctk.CTkFont(family=primary_font, size=12),
            "mono": ctk.CTkFont(family=system_fonts["mono"], size=13),  # 等寬字體用於顯示代碼/ID
        })
        print(f"✅ 使用字體: {primary_font}")
        
    except Exception as e1:
        try:
            # 備用方案：使用英文系統字體
            FONT.update({
                "logo": ctk.CTkFont(family=fallback_font, size=22, weight="bold"),
                "h1": ctk.CTkFont(family=fallback_font, size=24, weight="bold"),
                "h2": ctk.CTkFont(family=fallback_font, size=18, weight="bold"),
                "h3": ctk.CTkFont(family=fallback_font, size=16, weight="bold"),
                "body": ctk.CTkFont(family=fallback_font, size=14),
                "meta": ctk.CTkFont(family=fallback_font, size=12),
                "mono": ctk.CTkFont(family="Courier New", size=13),
            })
            print(f"⚠️ 使用備用字體: {fallback_font}")
            
        except Exception as e2:
            # 最終備用方案：使用通用字體
            FONT.update({
                "logo": ctk.CTkFont(size=22, weight="bold"),
                "h1": ctk.CTkFont(size=24, weight="bold"),
                "h2": ctk.CTkFont(size=18, weight="bold"),
                "h3": ctk.CTkFont(size=16, weight="bold"),
                "body": ctk.CTkFont(size=14),
                "meta": ctk.CTkFont(size=12),
                "mono": ctk.CTkFont(size=13),
            })
            print(f"⚠️ 使用預設字體")


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

# 角色權限配置
ROLE_UI = {
    "admin": {
        "tabs": ["首頁", "上傳影像", "影像清單", "病人管理", "傳輸狀態"],
        "can": {"upload": True, "createpatient": True, "viewpatient": True}
    },
    "doctor": {
        "tabs": ["首頁", "上傳影像", "影像清單", "病人管理"],
        "can": {"upload": True, "createpatient": False, "viewpatient": True}
    },
    "nurse": {
        "tabs": ["首頁", "病人管理"],
        "can": {"upload": False, "createpatient": True, "viewpatient": True}
    },
    "radtech": {
        "tabs": ["首頁", "上傳影像", "影像清單"],
        "can": {"upload": True, "createpatient": False, "viewpatient": True}
    },
    "viewer": {
        "tabs": ["首頁", "影像清單"],
        "can": {"upload": False, "createpatient": False, "viewpatient": True}
    }
}

ROLE_ZH = {
    "admin": "系統管理員",
    "doctor": "醫師",
    "nurse": "護理師",
    "radtech": "放射技師",
    "viewer": "觀察者"
}

def tabs_for_role(role: str):
    """取得角色對應的標籤頁"""
    return ROLE_UI.get(role, ROLE_UI["nurse"])["tabs"]

def can(role: str, perm: str) -> bool:
    """檢查角色權限"""
    if role == "admin":
        return True
    return ROLE_UI.get(role, ROLE_UI["nurse"])["can"].get(perm, False)

# 檔案類型
IMAGEEXTS = (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff")
VIDEOEXTS = (".mp4", ".avi", ".mov", ".mkv", ".wmv")

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