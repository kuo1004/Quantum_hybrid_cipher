# -*- coding: utf-8 -*-
"""
video_player.py - 系統內建媒體播放器模組（改進版）
使用系統預設播放器開啟影片，避免 OpenCV 相依性問題
"""
import os
import tempfile
import subprocess
import platform
import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox
from .config import COLOR, FONT, RADIUS, SolidBtn, OutlineBtn


class VideoPlayer:
    """系統內建媒體播放器（使用系統預設播放器）"""

    def __init__(self, parent, video_blob, filename):
        self.parent = parent
        self.video_blob = video_blob
        self.filename = filename
        self.temp_file = None
        self.is_closing = False

        self.setup_ui()

    def setup_ui(self):
        """設置播放器介面"""
        # 主容器
        main_frame = ctk.CTkFrame(
            self.parent, 
            fg_color=COLOR["surface"], 
            corner_radius=12
        )
        main_frame.pack(fill="both", expand=True, padx=20, pady=10)

        # 標題區域
        title_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        title_frame.pack(fill="x", padx=20, pady=(20, 10))

        ctk.CTkLabel(
            title_frame,
            text="🎬 影片播放器",
            font=FONT.get("h2"),
            text_color=COLOR["ink"]
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_frame,
            text=f"檔案: {self.filename}",
            font=FONT.get("meta"),
            text_color=COLOR["inksubtle"]
        ).pack(anchor="w", pady=(4, 0))

        # 預覽區域（顯示影片圖示）
        preview_frame = ctk.CTkFrame(
            main_frame, 
            fg_color="#1a1a2e",
            corner_radius=8,
            height=300
        )
        preview_frame.pack(fill="both", expand=True, padx=20, pady=(10, 10))
        preview_frame.pack_propagate(False)

        # 影片圖示和說明
        icon_label = ctk.CTkLabel(
            preview_frame,
            text="🎥",
            font=("Arial", 80),
            text_color=COLOR["primary"]
        )
        icon_label.pack(expand=True, pady=(60, 10))

        info_label = ctk.CTkLabel(
            preview_frame,
            text="點擊下方按鈕使用系統播放器開啟影片",
            font=FONT.get("body"),
            text_color=COLOR["inksubtle"]
        )
        info_label.pack(expand=True)

        # 控制區域
        control_frame = ctk.CTkFrame(
            main_frame, 
            fg_color=COLOR["surfacealt"], 
            corner_radius=8
        )
        control_frame.pack(fill="x", padx=20, pady=(0, 20))

        control_inner = ctk.CTkFrame(control_frame, fg_color="transparent")
        control_inner.pack(fill="x", padx=15, pady=15)

        # 播放按鈕
        play_btn = ctk.CTkButton(
            control_inner,
            text="▶️ 使用系統播放器開啟",
            command=self.play_with_system_player,
            width=200,
            height=45,
            corner_radius=RADIUS,
            fg_color=COLOR["primary"],
            hover_color="#0056D2",
            font=FONT.get("body")
        )
    
        play_btn.pack(side="left", padx=(0, 10))
    '''
        # 匯出按鈕
        export_btn = ctk.CTkButton(
            control_inner,
            text="💾 另存新檔",
            command=self.export_video,
            width=150,
            height=45,
            corner_radius=RADIUS,
            fg_color=COLOR["success"],
            hover_color="#0CA368",
            font=FONT.get("body")
        )
   
        export_btn.pack(side="left", padx=(0, 10))
      
        # 說明文字
       # info_frame = ctk.CTkFrame(control_inner, fg_color="transparent")
       # info_frame.pack(side="right", padx=(20, 0))

        system_name = self.get_system_player_name()
        ctk.CTkLabel(
            info_frame,
            text=f"💡 將使用 {system_name} 開啟影片",
            font=FONT.get("meta"),
            text_color=COLOR["inksubtle"]
        ).pack(anchor="e")


        ctk.CTkLabel(
            info_frame,
            text="支援完整播放控制、快轉、音量調整等功能",
            font=FONT.get("meta"),
            text_color=COLOR["muted"]
        ).pack(anchor="e", pady=(2, 0))
  '''
    def get_system_player_name(self):
        """取得系統播放器名稱"""
        system = platform.system()
        if system == "Windows":
            return "Windows Media Player / 電影與電視"
        elif system == "Darwin":  # macOS
            return "QuickTime Player"
        else:  # Linux
            return "系統預設播放器"

    def create_temp_file(self):
        """創建臨時影片檔案"""
        if self.temp_file is None:
            try:
                # 取得副檔名
                _, ext = os.path.splitext(self.filename)
                if not ext:
                    ext = '.mp4'  # 預設副檔名

                # 創建臨時檔案
                self.temp_file = tempfile.NamedTemporaryFile(
                    delete=False, 
                    suffix=ext,
                    prefix='iris_video_'
                )
                self.temp_file.write(self.video_blob)
                self.temp_file.close()

                print(f"✅ 臨時檔案已建立: {self.temp_file.name}")
                return self.temp_file.name

            except Exception as e:
                messagebox.showerror("錯誤", f"無法建立臨時檔案: {e}")
                return None

        return self.temp_file.name

    def play_with_system_player(self):
        """使用系統預設播放器開啟影片"""
        temp_path = self.create_temp_file()
        if not temp_path:
            return

        try:
            system = platform.system()

            if system == "Windows":
                # Windows: 使用 os.startfile
                os.startfile(temp_path)
                messagebox.showinfo(
                    "播放器已啟動",
                    f"已使用系統播放器開啟影片\n\n"
                    f"播放器關閉後，臨時檔案將自動清除"
                )

            elif system == "Darwin":  # macOS
                # macOS: 使用 open 命令
                subprocess.Popen(['open', temp_path])
                messagebox.showinfo(
                    "播放器已啟動",
                    f"已使用 QuickTime Player 開啟影片\n\n"
                    f"播放器關閉後，臨時檔案將自動清除"
                )

            else:  # Linux
                # Linux: 嘗試多個播放器
                players = ['xdg-open', 'vlc', 'mpv', 'totem', 'mplayer']
                
                for player in players:
                    try:
                        subprocess.Popen([player, temp_path])
                        messagebox.showinfo(
                            "播放器已啟動",
                            f"已使用 {player} 開啟影片\n\n"
                            f"播放器關閉後，臨時檔案將自動清除"
                        )
                        return
                    except FileNotFoundError:
                        continue
                
                # 如果所有播放器都失敗
                messagebox.showerror(
                    "錯誤",
                    "找不到可用的媒體播放器\n\n"
                    "請安裝 VLC, MPV 或其他媒體播放器"
                )

        except Exception as e:
            messagebox.showerror("錯誤", f"無法開啟播放器: {e}")
    def cleanup(self):
        """清理資源"""
        self.is_closing = True

        # 刪除臨時檔案
        if self.temp_file and os.path.exists(self.temp_file.name):
            try:
                # 等待一下確保檔案釋放
                import time
                time.sleep(0.3)
                os.unlink(self.temp_file.name)
                print(f"✅ 臨時檔案已刪除: {self.temp_file.name}")
            except Exception as e:
                print(f"⚠️ 刪除臨時檔案失敗: {e}")
'''
    def export_video(self):
        """匯出影片到使用者指定位置"""
        from tkinter import filedialog

        # 取得副檔名
        _, ext = os.path.splitext(self.filename)
        if not ext:
            ext = '.mp4'

        # 選擇儲存位置
        save_path = filedialog.asksaveasfilename(
            title="另存影片檔案",
            defaultextension=ext,
            initialfile=self.filename,
            filetypes=[
                ("影片檔案", f"*{ext}"),
                ("所有檔案", "*.*")
            ]
        )

        if save_path:
            try:
                # 寫入檔案
                with open(save_path, 'wb') as f:
                    f.write(self.video_blob)

                messagebox.showinfo(
                    "匯出成功",
                    f"影片已儲存至:\n{save_path}"
                )

            except Exception as e:
                messagebox.showerror("錯誤", f"匯出失敗: {e}")
'''
   


# ========== 備用方案：簡化的 OpenCV 播放器 ==========
class SimpleVideoPlayer:
    """
    簡化的影片播放器（使用 OpenCV）
    僅在系統播放器無法使用時才使用此備用方案
    """
    
    def __init__(self, parent, video_blob, filename):
        self.parent = parent
        self.video_blob = video_blob
        self.filename = filename
        
        try:
            import cv2
            self.cv2 = cv2
            self.opencv_available = True
        except ImportError:
            self.opencv_available = False
            messagebox.showerror(
                "錯誤",
                "未安裝 OpenCV 套件\n\n"
                "請安裝: pip install opencv-python"
            )
        
        if self.opencv_available:
            self.setup_opencv_player()
    
    def setup_opencv_player(self):
        """設置 OpenCV 播放器（備用方案）"""
        messagebox.showinfo(
            "提示",
            "使用簡化播放器\n\n"
            "建議使用系統內建播放器以獲得更好的體驗"
        )
        
        # 這裡可以實作簡化的 OpenCV 播放邏輯
        # 或直接導向系統播放器
        pass


if __name__ == "__main__":
    print("✅ 影片播放器模組（系統播放器版本）")
    print(f"   作業系統: {platform.system()}")
    print(f"   預設播放器: {VideoPlayer.get_system_player_name(None)}")