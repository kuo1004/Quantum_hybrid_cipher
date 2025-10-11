# certificate_authority.py
# 第三方憑證機構（Certificate Authority, CA）

import os, time, json, base64
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend

class CertificateAuthority:
    """第三方憑證機構，負責身份驗證和憑證管理"""

    def __init__(self, ca_name: str = "Medical_CA"):
        """初始化憑證機構"""
        self.ca_name = ca_name
        self.ca_private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        self.ca_public_key = self.ca_private_key.public_key()

        # 儲存已註冊的參與方
        self.registered_parties = {}
        self.issued_certificates = {}

        print(f"🏛️ 憑證機構 {ca_name} 已初始化")

    def register_party(self, party_id: str, party_public_key_pem: bytes, kem_public_key: bytes = None):
        """註冊參與方並發行憑證"""
        certificate_info = {
            "party_id": party_id,
            "public_key_pem": party_public_key_pem.decode('utf-8'),
            "issued_by": self.ca_name,
            "issue_time": time.time(),
            "valid_until": time.time() + (365 * 24 * 3600)  # 1年有效期
        }

        # 如果提供KEM公鑰，加入憑證
        if kem_public_key is not None:
            certificate_info["kem_public_key"] = base64.b64encode(kem_public_key).decode('utf-8')

        # 使用CA私鑰簽署憑證
        cert_data = json.dumps(certificate_info, sort_keys=True).encode()
        signature = self.ca_private_key.sign(
            cert_data,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )

        certificate = {
            "certificate_info": certificate_info,
            "ca_signature": base64.b64encode(signature).decode('utf-8')
        }

        self.registered_parties[party_id] = certificate
        self.issued_certificates[party_id] = certificate

        print(f"📋 已為 {party_id} 註冊並發行憑證")
        return certificate

    def verify_certificate(self, certificate: dict) -> bool:
        """驗證憑證的有效性"""
        try:
            cert_data = json.dumps(certificate["certificate_info"], sort_keys=True).encode()
            signature = base64.b64decode(certificate["ca_signature"])

            self.ca_public_key.verify(
                signature,
                cert_data,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )

            # 檢查憑證是否過期
            if time.time() > certificate["certificate_info"]["valid_until"]:
                print("⚠️ 憑證已過期")
                return False

            return True
        except Exception as e:
            print(f"❌ 憑證驗證失敗: {e}")
            return False

    def get_ca_public_key_pem(self) -> bytes:
        """獲取CA的公鑰（用於驗證憑證）"""
        return self.ca_public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

    def revoke_certificate(self, party_id: str):
        """撤銷憑證"""
        if party_id in self.registered_parties:
            del self.registered_parties[party_id]
            print(f"🚫 已撤銷 {party_id} 的憑證")
        else:
            print(f"⚠️ 找不到 {party_id} 的憑證")

    def list_registered_parties(self):
        """列出所有已註冊的參與方"""
        print(f"\n📊 {self.ca_name} 已註冊參與方:")
        for party_id, cert in self.registered_parties.items():
            issue_time = cert["certificate_info"]["issue_time"]
            valid_until = cert["certificate_info"]["valid_until"]
            status = "有效" if time.time() < valid_until else "已過期"
            print(f"   - {party_id}: {status}")

if __name__ == "__main__":
    # CA測試
    ca = CertificateAuthority("Test_Medical_CA")
    print("\n✅ 第三方憑證機構模組測試完成")
