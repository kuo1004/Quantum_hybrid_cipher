# -*- coding: utf-8 -*-
"""
thumbnail_utils.py - 縮圖生成工具（支援影像和影片）
"""
import os
import tempfile
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont


def is_video_file(filename):
    """判斷是否為影片檔案"""
    video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', 
                       '.mpeg', '.mpg', '.m4v', '.3gp']
    ext = os.path.splitext(filename)[1].lower()
    return ext in video_extensions


def is_image_file(filename):
    """判斷是否為影像檔案"""
    image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.dcm']
    ext = os.path.splitext(filename)[1].lower()
    return ext in image_extensions


def create_video_thumbnail(width=200, height=150, filename="video.mp4"):
    """
    創建影片縮圖（使用圖示）
    
    Args:
        width: 縮圖寬度
        height: 縮圖高度
        filename: 影片檔名（用於顯示副檔名）
    
    Returns:
        PIL.Image: 縮圖影像
    """
    # 創建漸層背景
    img = Image.new('RGB', (width, height), color=(30, 30, 45))
    draw = ImageDraw.Draw(img)
    
    # 繪製邊框
    draw.rectangle([(0, 0), (width-1, height-1)], outline=(100, 120, 180), width=2)
    
    # 繪製內部裝飾框
    margin = 15
    draw.rectangle(
        [(margin, margin), (width-margin-1, height-margin-1)], 
        outline=(70, 90, 150), 
        width=1
    )
    
    # 取得副檔名
    ext = os.path.splitext(filename)[1].upper().replace('.', '')
    
    # 繪製影片圖示（播放按鈕）
    center_x, center_y = width // 2, height // 2
    
    # 繪製圓形背景
    circle_radius = 30
    draw.ellipse(
        [center_x - circle_radius, center_y - circle_radius - 10,
         center_x + circle_radius, center_y + circle_radius - 10],
        fill=(70, 90, 255),
        outline=(100, 120, 255),
        width=2
    )
    
    # 繪製播放三角形
    triangle_size = 15
    triangle = [
        (center_x - triangle_size//2 + 3, center_y - triangle_size - 10),
        (center_x - triangle_size//2 + 3, center_y + triangle_size - 10),
        (center_x + triangle_size + 3, center_y - 10)
    ]
    draw.polygon(triangle, fill=(255, 255, 255))
    
    # 繪製文字
    try:
        # 嘗試使用較好的字體
        font_large = ImageFont.truetype("arial.ttf", 16)
        font_small = ImageFont.truetype("arial.ttf", 12)
    except:
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()
    
    # 顯示 "VIDEO" 文字
    video_text = "VIDEO"
    bbox = draw.textbbox((0, 0), video_text, font=font_large)
    text_width = bbox[2] - bbox[0]
    draw.text(
        (center_x - text_width // 2, center_y + circle_radius + 5),
        video_text,
        fill=(180, 200, 255),
        font=font_large
    )
    
    # 顯示副檔名
    if ext:
        bbox = draw.textbbox((0, 0), ext, font=font_small)
        text_width = bbox[2] - bbox[0]
        draw.text(
            (center_x - text_width // 2, height - 25),
            ext,
            fill=(150, 170, 220),
            font=font_small
        )
    
    return img


def create_image_thumbnail(image_data, width=200, height=150):
    """
    創建影像縮圖
    
    Args:
        image_data: 影像二進位資料
        width: 縮圖寬度
        height: 縮圖高度
    
    Returns:
        PIL.Image: 縮圖影像
    """
    try:
        img = Image.open(BytesIO(image_data))
        img.thumbnail((width, height), Image.Resampling.LANCZOS)
        
        # 創建白色背景
        background = Image.new('RGB', (width, height), (240, 240, 240))
        
        # 計算居中位置
        img_width, img_height = img.size
        x = (width - img_width) // 2
        y = (height - img_height) // 2
        
        # 貼上縮圖
        if img.mode == 'RGBA':
            background.paste(img, (x, y), img)
        else:
            background.paste(img, (x, y))
        
        return background
        
    except Exception as e:
        print(f"⚠️ 影像縮圖生成失敗: {e}")
        return create_error_thumbnail(width, height, "IMAGE ERROR")


def create_error_thumbnail(width=200, height=150, error_text="ERROR"):
    """
    創建錯誤縮圖
    
    Args:
        width: 縮圖寬度
        height: 縮圖高度
        error_text: 錯誤訊息
    
    Returns:
        PIL.Image: 錯誤縮圖
    """
    img = Image.new('RGB', (width, height), color=(60, 40, 40))
    draw = ImageDraw.Draw(img)
    
    # 繪製邊框
    draw.rectangle([(0, 0), (width-1, height-1)], outline=(180, 100, 100), width=2)
    
    # 繪製 X 標記
    center_x, center_y = width // 2, height // 2
    size = 30
    draw.line(
        [(center_x - size, center_y - size), (center_x + size, center_y + size)],
        fill=(255, 100, 100),
        width=4
    )
    draw.line(
        [(center_x - size, center_y + size), (center_x + size, center_y - size)],
        fill=(255, 100, 100),
        width=4
    )
    
    # 繪製文字
    try:
        font = ImageFont.truetype("arial.ttf", 12)
    except:
        font = ImageFont.load_default()
    
    bbox = draw.textbbox((0, 0), error_text, font=font)
    text_width = bbox[2] - bbox[0]
    draw.text(
        (center_x - text_width // 2, center_y + size + 10),
        error_text,
        fill=(255, 150, 150),
        font=font
    )
    
    return img


def create_thumbnail(image_data, filename, width=200, height=150):
    """
    根據檔案類型創建對應的縮圖
    
    Args:
        image_data: 檔案二進位資料
        filename: 檔案名稱
        width: 縮圖寬度
        height: 縮圖高度
    
    Returns:
        PIL.Image: 縮圖影像
    """
    try:
        if is_video_file(filename):
            # 影片檔案：使用圖示縮圖
            return create_video_thumbnail(width, height, filename)
        elif is_image_file(filename):
            # 影像檔案：生成真實縮圖
            return create_image_thumbnail(image_data, width, height)
        else:
            # 未知檔案類型
            return create_error_thumbnail(width, height, "UNKNOWN")
    
    except Exception as e:
        print(f"⚠️ 縮圖生成失敗: {e}")
        return create_error_thumbnail(width, height, "ERROR")


def extract_video_frame(video_data, filename, width=200, height=150):
    """
    從影片中提取第一幀作為縮圖（需要 OpenCV）
    
    Args:
        video_data: 影片二進位資料
        filename: 檔案名稱
        width: 縮圖寬度
        height: 縮圖高度
    
    Returns:
        PIL.Image: 縮圖影像，失敗則返回圖示縮圖
    """
    try:
        import cv2
        import numpy as np
        
        # 將影片資料寫入臨時檔案
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as tmp:
            tmp.write(video_data)
            tmp_path = tmp.name
        
        # 使用 OpenCV 讀取第一幀
        cap = cv2.VideoCapture(tmp_path)
        ret, frame = cap.read()
        cap.release()
        
        # 刪除臨時檔案
        try:
            os.unlink(tmp_path)
        except:
            pass
        
        if ret:
            # 轉換 BGR 到 RGB
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame)
            
            # 縮放到指定大小
            img.thumbnail((width, height), Image.Resampling.LANCZOS)
            
            # 創建背景並居中
            background = Image.new('RGB', (width, height), (30, 30, 45))
            img_width, img_height = img.size
            x = (width - img_width) // 2
            y = (height - img_height) // 2
            background.paste(img, (x, y))
            
            # 加上播放圖示
            draw = ImageDraw.Draw(background)
            circle_radius = 20
            center_x, center_y = width // 2, height // 2
            
            # 半透明圓形背景
            draw.ellipse(
                [center_x - circle_radius, center_y - circle_radius,
                 center_x + circle_radius, center_y + circle_radius],
                fill=(70, 90, 255, 200),
                outline=(100, 120, 255)
            )
            
            # 播放三角形
            triangle_size = 10
            triangle = [
                (center_x - triangle_size//2 + 2, center_y - triangle_size),
                (center_x - triangle_size//2 + 2, center_y + triangle_size),
                (center_x + triangle_size + 2, center_y)
            ]
            draw.polygon(triangle, fill=(255, 255, 255))
            
            return background
        else:
            raise Exception("無法讀取影片幀")
    
    except ImportError:
        # OpenCV 未安裝，使用圖示縮圖
        print("⚠️ OpenCV 未安裝，使用圖示縮圖")
        return create_video_thumbnail(width, height, filename)
    
    except Exception as e:
        print(f"⚠️ 影片幀提取失敗: {e}")
        return create_video_thumbnail(width, height, filename)


if __name__ == "__main__":
    # 測試縮圖生成
    print("🧪 測試縮圖生成工具...")
    
    # 測試影片縮圖
    video_thumb = create_video_thumbnail(filename="test.mp4")
    video_thumb.save("test_video_thumbnail.png")
    print("✅ 影片縮圖已生成: test_video_thumbnail.png")
    
    # 測試錯誤縮圖
    error_thumb = create_error_thumbnail()
    error_thumb.save("test_error_thumbnail.png")
    print("✅ 錯誤縮圖已生成: test_error_thumbnail.png")
    
    print("\n✅ 縮圖工具測試完成")
