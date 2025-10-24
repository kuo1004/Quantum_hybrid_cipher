

# IRIS Secure Transmission System

IRIS 是一個以醫療影像安全傳輸為核心的系統，整合圖形化介面（GUI）、後端伺服器、CA 憑證管理與資料庫觀測平台。
本系統採用多層加密與公開金鑰基礎建設（PKI）確保資料在醫療系統之間傳輸過程的機密性與完整性 。

***

## 系統架構

### 1. 前端 GUI

- 功能：提供使用者操作與影像選擇介面。
- 應用：符合醫療情境實用、分別有管理者、醫生、護士、醫檢放射師之情境。
- 啟動執行：

```bash
python main.py
```

此指令將開啟前端視覺化操作介面，用於醫療影像上傳與加密傳輸 。

***

### 2. 後端 Server

- 功能：接收前端傳輸資料，進行解密、簽章驗證與入庫。
- 結構：包含多執行緒資料接收模組與 HTTPS 通訊協定層。
- 啟動指令：

```bash
python start_all_server.py
```

該指令會同時啟動主伺服器、傳輸監聽器與驗證模組，支援 TLS 加密連線 。

***

### 3. 傳輸協定與安全加密

- 通訊協定：支援 HTTPS/TLS 1.3，結合憑證驗證與非對稱金鑰保護。
- 加密模式：
    - AES 對稱加密：用於影像資料本體
    - RSA 非對稱加密：用於金鑰交換與簽章驗證
- 簽章演算法：RSA + SHA256
- 憑證驗證：X.509 憑證支援 OCSP 與 CRL 驗證機制 。

***

### 4. CA 憑證管理

- 憑證來源：支援第三代政府憑證中心 (GCA/XCA)
- 憑證用途：
    - Client 憑證：加密與簽章使用
    - Server 憑證：TLS 驗證與金鑰交換
- 憑證匯入流程：

```bash
openssl pkcs12 -export -out iris_cert.p12 -inkey private.key -in iris_cert.crt
```

將私鑰與憑證打包成可用於伺服器端或前端的格式 。

***


### 5. 資料庫介面平台

- 說明：用於檢視傳輸紀錄與影像資料狀態的監控系統 GUI。
- 程式路徑：`test/data_viewer.py`
- 啟動方式：

```bash
python test/data_viewer.py
```

執行後會啟動觀測介面，用於檢視傳輸歷史與資料庫統計狀況 。

***

## 系統需求

| 元件 | 版本 |
| :-- | :-- |
| Python | 3.10+ |
| PostgreSQL | 14+ |
| OpenSSL | 1.1+ |
| 作業系統 | Windows / Linux |

安裝必要套件：

```bash
pip install -r requirements.txt
```


***

## 程式啟動流程

1. 啟動後端伺服器：

```bash
python start_all_server.py
```

2. 開啟前端 GUI：

```bash
python main.py
```

3. 使用資料庫觀測系統：

```bash
python test/data_viewer.py
```
