@echo off
setlocal

REM === 設定要安裝 liboqs 的資料夾（可自行修改） ===
set LIBOQS_DIR=%CD%\liboqs

REM === 下載 liboqs-python 原始碼 ===
git clone https://github.com/open-quantum-safe/liboqs-python.git

REM === 編譯設定：建立 Build 資料夾，啟用共享庫與 Windows 符號導出 ===
cmake -S %LIBOQS_DIR% -B %LIBOQS_DIR%\build -DBUILD_SHARED_LIBS=ON -DCMAKE_WINDOWS_EXPORT_ALL_SYMBOLS=TRUE

REM === 使用多核心編譯（根據 CPU 核心數量可自行調整） ===
cmake --build %LIBOQS_DIR%\build --parallel 8

REM === 安裝 liboqs（預設安裝到 C:\Program Files (x86)\liboqs）===
cmake --build %LIBOQS_DIR%\build --target install

REM === 將安裝目錄加入 PATH（讓系統找到 oqs.dll）===
setx PATH "%PATH%;C:\Program Files (x86)\liboqs\bin"

echo.
echo ✅ 安裝完成！請重啟命令提示字元（或重新登入）以套用 PATH 環境變數。
pause
