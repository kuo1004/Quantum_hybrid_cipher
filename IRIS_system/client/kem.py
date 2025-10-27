#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SimpleKEM - ML-KEM-1024 封裝
修正版：正確的資源管理 + 錯誤處理
"""

import oqs


class SimpleKEM:
    """
    簡化的 KEM (Key Encapsulation Mechanism) 封裝
    使用 ML-KEM-1024 (NIST 標準的後量子密碼學算法)
    """
    
    def __init__(self, alg_name="ML-KEM-1024"):
        """
        初始化 KEM
        
        Args:
            alg_name: KEM 演算法名稱，預設為 ML-KEM-1024
        """
        self.alg_name = alg_name
        self.public_key = None
        self.secret_key = None
        
        # 驗證演算法是否可用
        if alg_name not in oqs.get_enabled_kem_mechanisms():
            raise ValueError(f"不支援的 KEM 演算法: {alg_name}")

    def generate_keypair(self):
        """
        生成公私鑰對
        
        Returns:
            bytes: 公鑰
            
        Raises:
            RuntimeError: 如果金鑰生成失敗
        """
        try:
            with oqs.KeyEncapsulation(self.alg_name) as kem:
                self.public_key = kem.generate_keypair()
                self.secret_key = kem.export_secret_key()
            
            return self.public_key
            
        except Exception as e:
            raise RuntimeError(f"金鑰生成失敗: {e}") from e

    def encap_secret(self, receiver_public_key):
        """
        金鑰封裝：用接收方的公鑰封裝一個共享密鑰
        
        Args:
            receiver_public_key (bytes): 接收方的公鑰
            
        Returns:
            tuple: (encapsulated_key, shared_secret)
                - encapsulated_key: 封裝的密鑰 (傳送給接收方)
                - shared_secret: 共享密鑰 (用於加密)
                
        Raises:
            ValueError: 如果公鑰格式錯誤
            RuntimeError: 如果封裝失敗
        """
        if not receiver_public_key:
            raise ValueError("接收方公鑰不能為空")
        
        if not isinstance(receiver_public_key, bytes):
            raise TypeError("接收方公鑰必須是 bytes 類型")
        
        try:
            with oqs.KeyEncapsulation(self.alg_name) as kem_sender:
                encapsulated_key, shared_secret = kem_sender.encap_secret(receiver_public_key)
                return encapsulated_key, shared_secret
                
        except Exception as e:
            raise RuntimeError(f"KEM 封裝失敗: {e}") from e

    def decap_secret(self, encapsulated_key):
        """
        金鑰解封裝：用自己的私鑰解封裝得到共享密鑰
        
        Args:
            encapsulated_key (bytes): 封裝的密鑰
            
        Returns:
            bytes: 共享密鑰
            
        Raises:
            ValueError: 如果私鑰尚未生成或封裝密鑰格式錯誤
            RuntimeError: 如果解封裝失敗
        """
        if self.secret_key is None:
            raise ValueError("私鑰尚未生成，請先調用 generate_keypair()")
        
        if not encapsulated_key:
            raise ValueError("封裝密鑰不能為空")
        
        if not isinstance(encapsulated_key, bytes):
            raise TypeError("封裝密鑰必須是 bytes 類型")
        
        try:
            with oqs.KeyEncapsulation(self.alg_name) as kem_receiver:
                kem_receiver.secret_key = self.secret_key
                shared_secret = kem_receiver.decap_secret(encapsulated_key)
                return shared_secret
                
        except Exception as e:
            raise RuntimeError(f"KEM 解封裝失敗: {e}") from e

    def get_public_key(self):
        """
        獲取公鑰
        
        Returns:
            bytes: 公鑰，如果尚未生成則返回 None
        """
        return self.public_key

    def get_secret_key(self):
        """
        獲取私鑰（危險操作，僅用於序列化/持久化）
        
        Returns:
            bytes: 私鑰，如果尚未生成則返回 None
        """
        return self.secret_key

    def set_secret_key(self, secret_key):
        """
        設定私鑰（用於從序列化資料恢復）
        
        Args:
            secret_key (bytes): 私鑰
            
        Raises:
            TypeError: 如果私鑰不是 bytes 類型
        """
        if not isinstance(secret_key, bytes):
            raise TypeError("私鑰必須是 bytes 類型")
        
        self.secret_key = secret_key


def test_kem_consistency():
    """測試 KEM 一致性：驗證封裝/解封裝後的共享密鑰是否一致"""
    
    print("="*70)
    print("🧪 測試 KEM 一致性")
    print("="*70)
    
    try:
        # 創建發送方和接收方的 KEM
        print("\n📋 步驟 1: 創建 KEM 實例")
        sender_kem = SimpleKEM()
        receiver_kem = SimpleKEM()
        print("✅ KEM 實例創建成功")
        
        # 接收方生成金鑰對
        print("\n📋 步驟 2: 接收方生成金鑰對")
        receiver_pk = receiver_kem.generate_keypair()
        print(f"✅ 接收方公鑰長度: {len(receiver_pk)} bytes")
        print(f"   公鑰開頭: {receiver_pk[:16].hex()}...")
        
        # 發送方用接收方的公鑰封裝
        print("\n📋 步驟 3: 發送方封裝共享密鑰")
        encap_key, sender_secret = sender_kem.encap_secret(receiver_pk)
        print(f"✅ 封裝密鑰長度: {len(encap_key)} bytes")
        print(f"   封裝密鑰開頭: {encap_key[:16].hex()}...")
        print(f"   發送方共享密鑰: {sender_secret.hex()[:32]}...")
        
        # 接收方用自己的私鑰解封裝
        print("\n📋 步驟 4: 接收方解封裝共享密鑰")
        receiver_secret = receiver_kem.decap_secret(encap_key)
        print(f"   接收方共享密鑰: {receiver_secret.hex()[:32]}...")
        
        # 驗證一致性
        print("\n📋 步驟 5: 驗證密鑰一致性")
        if sender_secret == receiver_secret:
            print("✅ 密鑰一致！")
            print(f"   共享密鑰長度: {len(sender_secret)} bytes")
            print(f"   完整密鑰: {sender_secret.hex()}")
        else:
            print("❌ 密鑰不一致！")
            print(f"   發送方: {sender_secret.hex()}")
            print(f"   接收方: {receiver_secret.hex()}")
            raise AssertionError("共享密鑰不一致")
        
        print("\n" + "="*70)
        print("✅ KEM 一致性測試通過")
        print("="*70)
        
    except Exception as e:
        print(f"\n❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        raise




if __name__ == "__main__":
    # 執行測試
    test_kem_consistency()
