
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
診斷Sender的LSB嵌入功能
"""

import os
import sys
import pickle
import tempfile
from PIL import Image
import numpy as np

try:
    from server.sender import Sender
    from server.receiver import Receiver
    from certificate_authority import CertificateAuthority
except ImportError as e:
    print(f"❌ 導入失敗: {e}")
    sys.exit(1)

def create_test_image(path, width=512, height=512):
    """創建測試影像"""
    img_data = np.random.randint(0, 256, (height, width, 3), dtype=np.uint8)
    img = Image.fromarray(img_data, 'RGB')
    img.save(path)
    return path

def test_lsb_embedding():
    """測試LSB嵌入功能"""
    print("🧪 開始診斷Sender的LSB嵌入功能\n")
    print("="*60)

    # 初始化組件
    print("1️⃣ 初始化CA、Sender和Receiver...")
    ca = CertificateAuthority("Test_CA")
    sender = Sender("Test_Hospital_A")
    receiver = Receiver("Test_Hospital_B")

    # 向CA註冊
    print("2️⃣ 向CA註冊...")
    sender.register_with_ca(ca)
    receiver.register_with_ca(ca)

    # 創建測試影像
    print("3️⃣ 創建測試影像...")
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
        test_image = f.name
    create_test_image(test_image)
    print(f"   ✅ 測試影像: {test_image}")

    # 加密並準備傳輸包
    print("4️⃣ 加密並準備傳輸包...")
    try:
        transmission_package = sender.encrypt_and_prepare_transmission(
            input_image_path=test_image,
            receiver_certificate=receiver.certificate,
            ca_public_key_pem=ca.get_ca_public_key_pem()
        )
        print("   ✅ 傳輸包創建成功")
    except Exception as e:
        print(f"   ❌ 傳輸包創建失敗: {e}")
        return False

    # 檢查sender是否有LSB方法
    print("5️⃣ 檢查Sender的LSB方法...")
    has_generate = hasattr(sender, 'generate_cover_for_transmission')
    has_embed = hasattr(sender, 'lsb_embed_transmission_package')

    print(f"   generate_cover_for_transmission: {'✅ 存在' if has_generate else '❌ 不存在'}")
    print(f"   lsb_embed_transmission_package: {'✅ 存在' if has_embed else '❌ 不存在'}")

    if not (has_generate and has_embed):
        print("\n❌ Sender缺少LSB隱寫方法！")
        print("💡 這就是為什麼無法提取LSB數據的原因")
        return False

    # 測試生成載體影像
    print("6️⃣ 測試生成載體影像...")
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
        cover_path = f.name

    try:
        sender.generate_cover_for_transmission(cover_path, transmission_package)

        if os.path.exists(cover_path):
            cover_size = os.path.getsize(cover_path)
            print(f"   ✅ 載體影像已生成: {cover_size:,} bytes")
        else:
            print("   ❌ 載體影像未生成")
            return False
    except Exception as e:
        print(f"   ❌ 生成載體失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

    # 測試LSB嵌入
    print("7️⃣ 測試LSB嵌入...")
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
        stego_path = f.name

    try:
        sender.lsb_embed_transmission_package(cover_path, stego_path, transmission_package)

        if os.path.exists(stego_path):
            stego_size = os.path.getsize(stego_path)
            print(f"   ✅ 隱寫影像已生成: {stego_size:,} bytes")
        else:
            print("   ❌ 隱寫影像未生成")
            return False
    except Exception as e:
        print(f"   ❌ LSB嵌入失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

    # 驗證LSB數據
    print("8️⃣ 驗證LSB嵌入的數據...")
    try:
        # 讀取隱寫影像
        img = Image.open(stego_path).convert('RGB')
        arr = np.array(img, dtype=np.uint8)
        flat = arr.reshape(-1)

        # 提取前64個像素的最低位（應該包含長度信息）
        header_bits = flat[:64] & 1

        # 檢查是否全是1（表示沒有寫入數據）
        if np.all(header_bits == 1):
            print("   ❌ LSB數據未正確寫入（全是1）")
            return False

        # 檢查是否全是0（也不正常）
        if np.all(header_bits == 0):
            print("   ❌ LSB數據異常（全是0）")
            return False

        # 提取長度信息
        length_bytes = []
        for i in range(0, 64, 8):
            byte_bits = header_bits[i:i+8]
            byte_value = 0
            for j, bit in enumerate(byte_bits):
                byte_value |= (int(bit) << (7-j))
            length_bytes.append(byte_value)

        payload_length = int.from_bytes(bytes(length_bytes), 'big')

        print(f"   📋 嵌入的傳輸包長度: {payload_length:,} bytes")

        # 檢查長度是否合理
        max_capacity = (len(flat)) // 8 - 8
        if payload_length > max_capacity or payload_length == 0:
            print(f"   ❌ 長度不合理: {payload_length:,} (容量: {max_capacity:,})")
            return False

        print("   ✅ LSB數據寫入成功！長度合理")

    except Exception as e:
        print(f"   ❌ 驗證失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

    # 測試提取
    print("9️⃣ 測試LSB提取...")
    try:
        if hasattr(receiver, 'lsb_extract_transmission_package'):
            extracted_package = receiver.lsb_extract_transmission_package(stego_path)

            if extracted_package:
                print("   ✅ LSB提取成功！")
                print(f"   發送方: {extracted_package.get('sender_id')}")
                print(f"   接收方: {extracted_package.get('receiver_id')}")
                return True
            else:
                print("   ❌ LSB提取失敗（返回None）")
                return False
        else:
            print("   ⚠️ Receiver沒有lsb_extract_transmission_package方法")
            return False

    except Exception as e:
        print(f"   ❌ 提取失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # 清理臨時文件
        for temp_file in [test_image, cover_path, stego_path]:
            try:
                os.unlink(temp_file)
            except:
                pass

    print("="*60)

if __name__ == "__main__":
    success = test_lsb_embedding()

    print("\n" + "="*60)
    if success:
        print("🎉 診斷結果：LSB嵌入功能正常！")
        print("\n💡 建議：")
        print("   • Sender的LSB方法工作正常")
        print("   • 問題可能在Server端的調用邏輯")
        print("   • 檢查sender_server是否真正執行了LSB嵌入")
    else:
        print("❌ 診斷結果：LSB嵌入功能異常！")
        print("\n💡 建議：")
        print("   • 檢查sender.py中的LSB實現")
        print("   • 確認generate_cover_for_transmission正確生成載體")
        print("   • 確認lsb_embed_transmission_package正確嵌入數據")
    print("="*60)

    sys.exit(0 if success else 1)
