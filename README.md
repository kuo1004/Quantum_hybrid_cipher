# Quantum_hybrid_cipher
#  liboqs-python 環境建置教學 (Windows)

> 本指南說明如何在 **Windows** 環境下安裝與設定 [liboqs-python](https://github.com/open-quantum-safe/liboqs-python)，  
> 以進行後量子加密（Post-Quantum Cryptography, PQC）相關開發。

---

##  一、利用腳本執行檔載入套件

你可以建立一個批次檔 `install_liboqs.bat`，將以下內容貼上並執行，  
或直接在 **cmd** 終端機逐行輸入。

```bash
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

```



## 二、環境變數設定

首先確認系統環境變數 PATH 中是否已加入 liboqs 執行檔路徑：

```
C:\Program Files (x86)\liboqs\bin
```

您可以透過以下方式檢查：

1. 開啟「系統內容」→「進階」→「環境變數」
2. 在系統變數中找到 `Path` 並檢查是否包含上述路徑

## 三、虛擬環境建立與安裝

### 建立虛擬環境

使用 Anaconda 建立新的虛擬環境並開啟終端機：

```bash
conda create -n your_env_name python=3.x
conda activate your_env_name
```


### 安裝 liboqs-python

進入目標資料夾並執行安裝：

```bash
cd liboqs-python
pip install .
```


## 四、環境測試

### 執行測試檔

進入 liboqs-python 資料夾並執行範例程式：

```bash
cd liboqs-python
python examples/kem.py
```


## 常見問題解決

### ModuleNotFoundError: No module named 'oqs'

如果出現此錯誤訊息，可以使用以下兩種方法解決：

#### 方法一：設定 PYTHONPATH（暫時性解決方案）

```bash
set PYTHONPATH=%PYTHONPATH%;D:\graduation_project\liboqs-python
```

> ⚠️ **注意**：這只是暫時性的解決方案，每次開啟新的終端機都需要重新設定。

#### 方法二：在程式中加入路徑（程式碼層面解決）

在您的 Python 程式檔案開頭加入以下程式碼：

```python
import sys
sys.path.append("D:\\graduation_project\\liboqs-python")
# 注意：oqs 模組必須在路徑設定之後才能匯入
import oqs
```


### 建議的長期解決方案

為了避免每次都需要手動設定路徑，建議使用以下方法之一：

1. **使用 pip 的開發模式安裝**：

```bash
pip install -e .
```

2. **將 liboqs-python 路徑加入到系統環境變數 PYTHONPATH 中**

這樣設定後，您就可以在任何地方直接使用 `import oqs` 而不會遇到匯入錯誤的問題。

