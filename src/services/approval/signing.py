"""
KMS Server Attestation Module (Ed25519 - RFC 8032)
Owner: TechLead (cuongtv_02560)
Spike: Spike 3 (Asymmetric Cryptographic Server Attestation)
Zero-Trust Invariant: Pre-Sales decoupled from KMS; Official Quote signed deterministically.
"""

from __future__ import annotations

import base64
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519
from pydantic import BaseModel

from src.contracts.common import canonical_json_bytes, sha256_hex


class KMSServerSigner:
    """
    KMS Server Signer using Ed25519 asymmetric cryptography.

    Provides deterministic SHA-256 snapshot hashing via RFC 8785 canonical JSON
    and signs snapshot hashes using an Ed25519 private key.

    Key resolution order:
    1. Explicit ``private_key_bytes`` parameter (32 raw bytes).
    2. ``KMS_ED25519_SEED`` environment variable (hex-encoded 32 bytes).
    3. Auto-generate ephemeral key pair (dev/test only — logs warning).
    """

    def __init__(self, private_key_bytes: bytes | None = None) -> None:
        """
        Initialize signer with deterministic key resolution.
        """
        import logging
        import os

        if private_key_bytes:
            self._private_key = ed25519.Ed25519PrivateKey.from_private_bytes(private_key_bytes)
        else:
            seed_hex = os.environ.get("KMS_ED25519_SEED")
            if seed_hex:
                seed_bytes = bytes.fromhex(seed_hex)
                self._private_key = ed25519.Ed25519PrivateKey.from_private_bytes(seed_bytes)
            else:
                logging.getLogger(__name__).warning(
                    "KMS_ED25519_SEED not set — generating ephemeral Ed25519 key pair. "
                    "Signatures will NOT be verifiable across restarts. "
                    "Set KMS_ED25519_SEED (64 hex chars) for production use."
                )
                self._private_key = ed25519.Ed25519PrivateKey.generate()
        self._public_key = self._private_key.public_key()

    def get_public_key_raw_bytes(self) -> bytes:
        """Return the raw 32-byte public key."""
        return self._public_key.public_bytes_raw()

    def get_public_key_base64(self) -> str:
        """Return standard Base64 representation of the public key."""
        return base64.b64encode(self.get_public_key_raw_bytes()).decode("utf-8")

    def calculate_snapshot_hash(self, snapshot_payload: dict[str, Any] | BaseModel) -> str:
        """
        Calculate canonical SHA-256 hash of a snapshot payload.
        Adheres to RFC 8785 Canonical JSON format.
        """
        if isinstance(snapshot_payload, BaseModel):
            payload_dict = snapshot_payload.model_dump(mode="json")
        elif isinstance(snapshot_payload, dict):
            payload_dict = snapshot_payload
        else:
            raise TypeError(f"Unsupported snapshot payload type: {type(snapshot_payload)}")

        canonical_bytes = canonical_json_bytes(payload_dict)
        return sha256_hex(canonical_bytes)

    def sign_snapshot_hash(self, snapshot_hash: str) -> str:
        """
        Sign the hexadecimal snapshot hash string using Ed25519 private key.
        Returns Base64-encoded signature.
        """
        signature_bytes = self._private_key.sign(snapshot_hash.encode("utf-8"))
        return base64.b64encode(signature_bytes).decode("utf-8")

    def verify_signature(
        self,
        snapshot_hash: str,
        signature_base64: str,
        public_key_base64: str | None = None,
    ) -> bool:
        """
        Verify Ed25519 signature against snapshot hash.
        If public_key_base64 is omitted, verifies using this signer's own public key.
        """
        try:
            signature_bytes = base64.b64decode(signature_base64)
            if public_key_base64:
                pub_key_bytes = base64.b64decode(public_key_base64)
                verifier_key = ed25519.Ed25519PublicKey.from_public_bytes(pub_key_bytes)
            else:
                verifier_key = self._public_key

            verifier_key.verify(signature_bytes, snapshot_hash.encode("utf-8"))
            return True
        except (InvalidSignature, ValueError, TypeError):
            return False
