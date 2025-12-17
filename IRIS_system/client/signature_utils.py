# -*- coding: utf-8 -*-
"""
signature_utils.py - 數位簽章工具模組 (Client 端版本)
提供 RSA-PSS 簽章與驗證功能
"""

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding


def sign_bytes(private_key, data: bytes) -> bytes:
    """
    使用私鑰對資料進行 RSA-PSS 簽章
    
    Args:
        private_key: RSA 私鑰物件
        data: 要簽章的資料 (bytes)
    
    Returns:
        bytes: 數位簽章
    """
    try:
        signature = private_key.sign(
            data,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return signature
    except Exception as e:
        print(f"❌ 簽章失敗: {e}")
        raise


def verify_signature(public_key, data: bytes, signature: bytes) -> bool:
    """
    使用公鑰驗證 RSA-PSS 簽章
    
    Args:
        public_key: RSA 公鑰物件
        data: 原始資料 (bytes)
        signature: 數位簽章 (bytes)
    
    Returns:
        bool: 驗證成功返回 True，失敗返回 False
    """
    try:
        public_key.verify(
            signature,
            data,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return True
    except Exception as e:
        print(f"⚠️ 簽章驗證失敗: {e}")
        return False


def sign_data_with_hash(private_key, data: bytes, hash_algorithm=hashes.SHA256()) -> bytes:
    """
    使用指定的雜湊演算法對資料進行簽章
    
    Args:
        private_key: RSA 私鑰物件
        data: 要簽章的資料 (bytes)
        hash_algorithm: 雜湊演算法 (預設 SHA256)
    
    Returns:
        bytes: 數位簽章
    """
    try:
        signature = private_key.sign(
            data,
            padding.PSS(
                mgf=padding.MGF1(hash_algorithm),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hash_algorithm
        )
        return signature
    except Exception as e:
        print(f"❌ 簽章失敗: {e}")
        raise


def verify_signature_with_hash(public_key, data: bytes, signature: bytes, 
                               hash_algorithm=hashes.SHA256()) -> bool:
    """
    使用指定的雜湊演算法驗證簽章
    
    Args:
        public_key: RSA 公鑰物件
        data: 原始資料 (bytes)
        signature: 數位簽章 (bytes)
        hash_algorithm: 雜湊演算法 (預設 SHA256)
    
    Returns:
        bool: 驗證成功返回 True，失敗返回 False
    """
    try:
        public_key.verify(
            signature,
            data,
            padding.PSS(
                mgf=padding.MGF1(hash_algorithm),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hash_algorithm
        )
        return True
    except Exception as e:
        print(f"⚠️ 簽章驗證失敗: {e}")
        return False


if __name__ == "__main__":
    # 簡單測試
    from cryptography.hazmat.primitives.asymmetric import rsa
    
    print("🧪 測試數位簽章模組...")
    
    # 生成測試金鑰對
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048
    )
    public_key = private_key.public_key()
    
    # 測試資料
    test_data = b"IRIS Medical Image System - Digital Signature Test"
    
    # 簽章
    print("📝 進行簽章...")
    signature = sign_bytes(private_key, test_data)
    print(f"✅ 簽章完成: {len(signature)} bytes")
    
    # 驗證
    print("🔍 驗證簽章...")
    is_valid = verify_signature(public_key, test_data, signature)
    
    if is_valid:
        print("✅ 簽章驗證成功！")
    else:
        print("❌ 簽章驗證失敗！")
    
    # 測試錯誤資料
    print("\n🧪 測試錯誤資料...")
    wrong_data = b"Wrong data"
    is_valid = verify_signature(public_key, wrong_data, signature)
    
    if not is_valid:
        print("✅ 正確拒絕錯誤資料")
    else:
        print("❌ 應該拒絕錯誤資料")
    
    print("\n✅ 數位簽章模組測試完成")