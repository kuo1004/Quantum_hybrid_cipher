# 醫療影像三方傳輸系統

## 系統架構

本系統提供兩種運行模式：

### 🔍 監控測試模式
- **文件**: `enhanced_medical_transmission_monitor.py`
- **用途**: 開發測試、演示、監控
- **特點**: GUI介面，手動操作，適合測試和展示

### 🌐 分散式生產模式
- **文件**: `ca_server.py`, `sender_server.py`, `receiver_server.py`  
- **用途**: 實際部署、自動化處理
- **特點**: 獨立服務器，自動監控，異地部署

## 快速開始

### 1. 安裝依賴
```bash
pip install pillow cryptography numpy tkinter watchdog
```

### 2. 啟動系統

#### 方法一：使用啟動腳本
```bash
chmod +x start_system.sh

# 啟動CA服務器
./start_system.sh ca 192.168.1.100 8001

# 啟動發送方（在另一台機器）
./start_system.sh sender 192.168.1.101 8002 192.168.1.100 8001

# 啟動接收方（在第三台機器）
./start_system.sh receiver 192.168.1.102 8003 192.168.1.100 8001
```

#### 方法二：手動啟動
```bash
# CA服務器
python3 ca_server.py 192.168.1.100 8001

# 發送方服務器  
python3 sender_server.py 192.168.1.101 8002 192.168.1.100 8001

# 接收方服務器
python3 receiver_server.py 192.168.1.102 8003 192.168.1.100 8001
```

#### 方法三：啟動監控介面（測試用）
```bash
python3 enhanced_medical_transmission_monitor.py
```

## 使用流程

### 分散式模式（自動化）

1. **啟動CA服務器**
   - 憑證機構開始運行
   - 等待醫療機構註冊

2. **啟動發送方服務器**
   - 自動向CA註冊
   - 開始監控 `./medical_images_input/` 目錄
   - 發現新影像時自動加密處理

3. **啟動接收方服務器**
   - 自動向CA註冊
   - 定期檢查是否有新影像
   - 自動接收、解密並保存到 `./medical_images_received/`

4. **傳輸影像**
   - 只需將醫療影像放入發送方的 `./medical_images_input/` 目錄
   - 系統自動完成加密、傳輸、解密全流程

### 監控模式（測試用）

1. 啟動GUI介面
2. 點擊「初始化系統」
3. 選擇要傳輸的影像
4. 點擊「開始傳輸」
5. 觀察實時監控日誌

## 目錄結構

```
醫療影像傳輸系統/
├── ca_server.py                    # CA服務器
├── sender_server.py                # 發送方服務器  
├── receiver_server.py              # 接收方服務器
├── enhanced_medical_transmission_monitor.py  # 監控介面
├── start_system.sh                 # 啟動腳本
├── medical_images_input/           # 發送方：待傳輸影像目錄
├── medical_images_output/          # 發送方：加密後影像目錄
└── medical_images_received/        # 接收方：接收到的影像目錄
```

## 網路配置

### 預設端口
- **CA服務器**: 8001
- **發送方服務器**: 8002  
- **接收方服務器**: 8003

### 防火牆設定
確保以下端口已開放：
```bash
# Ubuntu/Debian
sudo ufw allow 8001
sudo ufw allow 8002
sudo ufw allow 8003

# CentOS/RHEL
sudo firewall-cmd --add-port=8001/tcp --permanent
sudo firewall-cmd --add-port=8002/tcp --permanent
sudo firewall-cmd --add-port=8003/tcp --permanent
sudo firewall-cmd --reload
```

## 安全特性

- **AES-256-GCM 加密**: 影像數據加密
- **ML-KEM-1024 金鑰封裝**: 量子安全的金鑰交換
- **RSA-2048 數位簽章**: 身份驗證
- **LSB隱寫術**: 隱蔽傳輸
- **憑證機構驗證**: 三方身份認證

## 監控功能

### 實時狀態監控
- 三方實體運行狀態
- 傳輸進度追蹤
- 數據流量統計
- 錯誤狀態提醒

### 日誌系統
- 詳細操作記錄
- 可導出TXT/CSV格式
- 分色顯示不同實體
- 時間戳精確記錄

## 故障排除

### 常見問題

1. **連接CA失敗**
   - 檢查CA服務器是否運行
   - 確認網路連通性
   - 檢查防火牆設定

2. **檔案監控不工作**  
   - 確認目錄權限
   - 檢查watchdog套件是否正確安裝

3. **影像處理錯誤**
   - 檢查影像格式是否支援
   - 確認磁碟空間充足

### 日誌查看
系統會在控制台輸出詳細日誌，包括：
- 🏛️ CA操作日誌
- 📤 發送方處理日誌  
- 📥 接收方處理日誌
- ❌ 錯誤信息

## 效能調整

### 網路設定
```python
# 在各server檔案中調整
chunk_size = 8192      # 網路傳輸塊大小
timeout = 60           # 網路超時時間
```

### 檔案監控
```python
# 在sender_server.py中調整
check_interval = 10    # 檔案檢查間隔（秒）
```

## 技術支援

如有問題，請檢查：
1. Python版本 >= 3.7
2. 所需套件已安裝
3. 網路連接正常
4. 防火牆設定正確
