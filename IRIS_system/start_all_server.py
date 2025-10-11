# start_all_servers.py (修正版)
import threading
import time
import sys
import os

# --- 關鍵：導入每個伺服器的主函式 ---
# 這種導入方式可以讓我們像在命令列執行一樣呼叫它們
try:
    # 假設你的 ca_server.py 中 if __name__ == "__main__" 內呼叫了 main()
    from server.ca_server import main as ca_main
    # 假設你的 sender_server.py 中 if __name__ == "__main__" 內呼叫了 main()
    from server.sender_server import main as sender_main
    # 假設你的 receiver_server.py 中 if __name__ == "__main__" 內呼叫了 main()
    from server.receiver_server import main as receiver_main
except ImportError as e:
    print(f"❌ 模組導入失敗: {e}")
    print("👉 請確認：")
    print("   1. ca_server.py, sender_server.py, receiver_server.py 都在同一個目錄下。")
    print("   2. 這三個檔案的 if __name__ == '__main__' 區塊中，最後都有一個 main() 函數被呼叫。")
    sys.exit(1)


# --- 服務啟動函式 ---

def run_ca_server():
    """以獨立執行緒啟動 CA 服務"""
    try:
        print("\n" + "="*25 + " 正在啟動 CA 服務 " + "="*25)
        # 模擬命令列執行 `python ca_server.py`
        ca_main()
        print("✅ CA 服務已啟動")
    except Exception as e:
        print(f"❌ CA 服務啟動失敗: {e}")
        import traceback
        traceback.print_exc()

def run_receiver_server():
    """以獨立執行緒啟動 Receiver Server 服務"""
    try:
        # 等待 1 秒，確保 CA 服務已監聽埠號
        time.sleep(1)
        print("\n" + "="*20 + " 正在啟動 Receiver Server " + "="*20)
        # 模擬命令列執行 `python receiver_server.py`
        receiver_main()
        print("✅ Receiver Server 已啟動")
    except Exception as e:
        print(f"❌ Receiver Server 啟動失敗: {e}")
        import traceback
        traceback.print_exc()

def run_sender_server():
    """以獨立執行緒啟動 Sender Server 服務"""
    try:
        # 等待 3 秒，確保 CA 和 Receiver 都已啟動並完成註冊
        time.sleep(3)
        print("\n" + "="*20 + " 正在啟動 Sender Server " + "="*20)
        # 模擬命令列執行 `python sender_server.py`
        sender_main()
        print("✅ Sender Server 已啟動")
    except Exception as e:
        print(f"❌ Sender Server 啟動失敗: {e}")
        import traceback
        traceback.print_exc()


# --- 主程式 ---
if __name__ == "__main__":
    # 建立服務執行緒
    ca_thread = threading.Thread(target=run_ca_server, daemon=True)
    receiver_thread = threading.Thread(target=run_receiver_server, daemon=True)
    sender_thread = threading.Thread(target=run_sender_server, daemon=True)

    # 依次啟動
    ca_thread.start()
    receiver_thread.start()
    sender_thread.start()

    # 主執行緒等待，直到使用者中斷
    try:
        print("\n\n" + "*"*80)
        print("🚀 所有後台服務已在背景啟動！現在你可以運行主程式 main.py。")
        print("   - CA Server      (憑證中心)")
        print("   - Sender Server  (監控 input 資料夾，執行加密與傳輸)")
        print("   - Receiver Server(接收、解密、驗證並寫入資料庫)")
        print("\n👉 請保持此視窗開啟，按 Ctrl+C 可一次性關閉所有服務。")
        print("*"*80)

        # 保持主執行緒存活，以便接收 Ctrl+C
        while ca_thread.is_alive() and receiver_thread.is_alive() and sender_thread.is_alive():
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n\n🛑 收到關閉信號，正在停止所有服務...")
        # 因為是 daemon thread，主程式結束它們也會跟著結束
        print("👋 所有服務已停止。")
        sys.exit(0)
    except Exception as e:
        print(f"主啟動器發生錯誤: {e}")

