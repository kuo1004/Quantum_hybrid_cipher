# -*- coding: utf-8 -*-
"""
video_player.py - OpenCV 影片播放器模組（安全版）
"""
import os
import tempfile
import threading
import time
import tkinter as tk
import customtkinter as ctk
import cv2
from PIL import Image, ImageTk
from .config import COLOR, FONT, RADIUS, SolidBtn

class VideoPlayer:
    """OpenCV 影片播放器（執行緒安全版）"""

    def __init__(self, parent, video_blob, filename):
        self.parent = parent
        self.video_blob = video_blob
        self.filename = filename
        self.is_playing = False
        self.is_paused = False
        self.is_closing = False  # 新增：關閉標記
        self.current_frame = 0
        self.total_frames = 0
        self.fps = 30
        self.video_cap = None
        self.temp_file = None
        self.play_thread = None  # 新增：追蹤播放執行緒

        self.setup_ui()
        self.load_video()

    def setup_ui(self):
        """設置播放器介面"""
        # 影片顯示區域
        self.video_frame = ctk.CTkFrame(self.parent, fg_color="#000000", corner_radius=12)
        self.video_frame.pack(fill="both", expand=True, padx=20, pady=(10, 10))

        self.video_label = tk.Label(self.video_frame, bg="#000000")
        self.video_label.pack(expand=True)

        # 控制區域
        control_frame = ctk.CTkFrame(self.parent, fg_color=COLOR["surfacealt"], corner_radius=8)
        control_frame.pack(fill="x", padx=20, pady=(0, 10))

        control_inner = ctk.CTkFrame(control_frame, fg_color="transparent")
        control_inner.pack(fill="x", padx=15, pady=10)

        # 播放/暫停按鈕
        self.play_pause_btn = ctk.CTkButton(
            control_inner,
            text="▶️ 播放",
            command=self.toggle_play_pause,
            width=100,
            height=40,
            corner_radius=RADIUS,
            fg_color=COLOR["success"],
            hover_color="#0CA368",
            font=FONT.get("body")
        )
        self.play_pause_btn.pack(side="left", padx=(0, 10))

        # 停止按鈕
        stop_btn = ctk.CTkButton(
            control_inner,
            text="⏹️ 停止",
            command=self.stop_video,
            width=100,
            height=40,
            corner_radius=RADIUS,
            fg_color=COLOR["danger"],
            hover_color="#D43F44",
            font=FONT.get("body")
        )
        stop_btn.pack(side="left", padx=(0, 20))

        # 進度條
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_slider = ctk.CTkSlider(
            control_inner,
            from_=0,
            to=100,
            variable=self.progress_var,
            command=self.seek_video,
            width=400,
            height=20
        )
        self.progress_slider.pack(side="left", fill="x", expand=True, padx=(0, 15))

        # 時間顯示
        self.time_label = ctk.CTkLabel(
            control_inner,
            text="00:00 / 00:00",
            font=FONT.get("meta"),
            text_color=COLOR["inksubtle"]
        )
        self.time_label.pack(side="left")

    def load_video(self):
        """載入影片"""
        try:
            # 將 BLOB 寫入臨時檔案
            self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(self.filename)[1])
            self.temp_file.write(self.video_blob)
            self.temp_file.close()

            # 使用 OpenCV 開啟影片
            self.video_cap = cv2.VideoCapture(self.temp_file.name)

            if not self.video_cap.isOpened():
                raise Exception("無法開啟影片檔案")

            self.total_frames = int(self.video_cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self.fps = self.video_cap.get(cv2.CAP_PROP_FPS) or 30

            # 顯示第一幀
            self.show_frame(0)

        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("錯誤", f"無法載入影片: {e}")

    def show_frame(self, frame_num):
        """顯示指定幀"""
        # 檢查是否正在關閉
        if self.is_closing or not self.video_cap:
            return

        try:
            self.video_cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
            ret, frame = self.video_cap.read()

            if ret and not self.is_closing:
                # 轉換 BGR 到 RGB
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # 調整大小
                h, w = frame.shape[:2]
                max_w, max_h = 900, 500
                scale = min(max_w / w, max_h / h)
                new_w, new_h = int(w * scale), int(h * scale)
                frame = cv2.resize(frame, (new_w, new_h))

                # 轉換為 PIL Image
                img = Image.fromarray(frame)
                photo = ImageTk.PhotoImage(img)

                # 更新標籤（檢查是否還存在）
                if self.video_label.winfo_exists():
                    self.video_label.configure(image=photo)
                    self.video_label.image = photo

                self.current_frame = frame_num
                self.update_progress()
        except Exception as e:
            if not self.is_closing:
                print(f"顯示幀錯誤: {e}")

    def toggle_play_pause(self):
        """播放/暫停切換"""
        if self.is_closing:
            return

        if not self.is_playing:
            self.is_playing = True
            self.is_paused = False
            self.play_pause_btn.configure(text="⏸️ 暫停")
            # 啟動新的播放執行緒
            self.play_thread = threading.Thread(target=self.play_video, daemon=True)
            self.play_thread.start()
        else:
            self.is_paused = not self.is_paused
            if self.is_paused:
                self.play_pause_btn.configure(text="▶️ 繼續")
            else:
                self.play_pause_btn.configure(text="⏸️ 暫停")

    def play_video(self):
        """播放影片"""
        while self.is_playing and self.current_frame < self.total_frames and not self.is_closing:
            if not self.is_paused:
                self.show_frame(self.current_frame)
                self.current_frame += 1
                time.sleep(1.0 / self.fps)
            else:
                time.sleep(0.1)

        if self.current_frame >= self.total_frames and not self.is_closing:
            self.stop_video()

    def stop_video(self):
        """停止播放"""
        if self.is_closing:
            return

        self.is_playing = False
        self.is_paused = False
        self.current_frame = 0
        self.show_frame(0)

        if self.play_pause_btn.winfo_exists():
            self.play_pause_btn.configure(text="▶️ 播放")

    def seek_video(self, value):
        """拖動進度條"""
        if self.is_closing or self.total_frames <= 0:
            return

        frame_num = int((float(value) / 100) * self.total_frames)
        self.current_frame = frame_num
        self.show_frame(frame_num)

    def update_progress(self):
        """更新進度顯示"""
        if self.is_closing or self.total_frames <= 0:
            return

        try:
            progress = (self.current_frame / self.total_frames) * 100
            self.progress_var.set(progress)

            current_sec = int(self.current_frame / self.fps)
            total_sec = int(self.total_frames / self.fps)

            current_time = f"{current_sec // 60:02d}:{current_sec % 60:02d}"
            total_time = f"{total_sec // 60:02d}:{total_sec % 60:02d}"

            if self.time_label.winfo_exists():
                self.time_label.configure(text=f"{current_time} / {total_time}")
        except Exception as e:
            if not self.is_closing:
                print(f"更新進度錯誤: {e}")

    def cleanup(self):
        """清理資源（執行緒安全版）"""
        # 設置關閉標記
        self.is_closing = True

        # 停止播放
        self.is_playing = False
        self.is_paused = False

        # 等待播放執行緒結束（最多等待 1 秒）
        if self.play_thread and self.play_thread.is_alive():
            self.play_thread.join(timeout=1.0)

        # 釋放 VideoCapture
        if self.video_cap:
            try:
                self.video_cap.release()
                self.video_cap = None
            except Exception as e:
                print(f"釋放 video_cap 錯誤: {e}")

        # 刪除臨時檔案
        if self.temp_file and os.path.exists(self.temp_file.name):
            try:
                # 等待一下確保檔案釋放
                time.sleep(0.2)
                os.unlink(self.temp_file.name)
            except Exception as e:
                print(f"刪除臨時檔案錯誤: {e}")