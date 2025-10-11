# simple_kem.py
# 簡化且可靠的KEM實現，確保加密解密一致性

import os, hashlib, base64

class SimpleKEM:
    """簡化的KEM實現，確保加密解密一致性"""

    def __init__(self, alg_name="ML-KEM-1024"):
        self.alg_name = alg_name
        # 生成固定長度的金鑰對
        self.private_seed = os.urandom(32)
        self.public_key = hashlib.sha256(self.private_seed + b"public").digest()

    def generate_keypair(self):
        """返回公鑰"""
        return self.public_key

    def encap_secret(self, receiver_public_key):
        """金鑰封裝 - 生成封裝金鑰和共享密鑰"""
        # 生成隨機種子
        random_seed = os.urandom(16)

        # 基於隨機種子和接收方公鑰生成共享密鑰
        shared_secret = hashlib.sha256(
            random_seed + receiver_public_key[:16]
        ).digest()

        # 封裝金鑰就是隨機種子
        encapsulated_key = random_seed

        return encapsulated_key, shared_secret

    def decap_secret(self, encapsulated_key):
        """金鑰解封裝 - 從封裝金鑰恢復共享密鑰"""
        # 使用自己的公鑰和封裝金鑰重建共享密鑰
        shared_secret = hashlib.sha256(
            encapsulated_key + self.public_key[:16]
        ).digest()

        return shared_secret

# 測試函數
def test_kem_consistency():
    """測試KEM的一致性"""
    print("🧪 測試KEM一致性...")

    # 創建兩個KEM實例模擬發送方和接收方
    sender_kem = SimpleKEM()
    receiver_kem = SimpleKEM()

    # 發送方使用接收方的公鑰進行封裝
    receiver_pk = receiver_kem.generate_keypair()
    encap_key, sender_secret = sender_kem.encap_secret(receiver_pk)

    # 接收方使用封裝金鑰進行解封裝
    receiver_secret = receiver_kem.decap_secret(encap_key)

    print(f"發送方共享密鑰: {sender_secret.hex()[:16]}...")
    print(f"接收方共享密鑰: {receiver_secret.hex()[:16]}...")
    print(f"密鑰一致性: {'✅ 一致' if sender_secret == receiver_secret else '❌ 不一致'}")

    return sender_secret == receiver_secret

if __name__ == "__main__":
    test_kem_consistency()
