"""Ký số Ed25519 (RFC 8032) qua KMS Server Attestation.

Ràng buộc: private key KHÔNG BAO GIỜ nằm trong app process — app chỉ gửi
payload hash (đã đóng băng ở N-19A) tới KMS để ký. Public key phục vụ kiểm
thực đối soát phát tại `GET /.well-known/jwks.json`.
"""

from src.contracts.common import canonical_json_bytes, sha256_hex


def payload_fingerprint(payload: dict) -> str:
    """Hàm băm chuẩn dùng chung cho N-19A — freeze trước khi gọi KMS."""
    return sha256_hex(canonical_json_bytes(payload))


class Ed25519AttestationService:
    """Ủy quyền ký số lên KMS; không giữ key trong process."""

    async def request_attestation(self, payload_hash: str, manager_otp: str) -> dict:
        raise NotImplementedError("C-05/N-19B: KMS attestation")

    async def verify_signature(self, payload_hash: str, signature: str, public_key_jwk: dict) -> bool:
        raise NotImplementedError("C-05: signature verification")
