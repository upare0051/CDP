"""Security utilities for credential encryption."""

import base64
import hashlib
from cryptography.fernet import Fernet
from typing import Optional

from .config import get_settings


def _get_fernet() -> Fernet:
    """Get Fernet instance from encryption key."""
    settings = get_settings()
    # Derive a proper 32-byte key from the encryption key
    key = hashlib.sha256(settings.encryption_key.encode()).digest()
    key_b64 = base64.urlsafe_b64encode(key)
    return Fernet(key_b64)


def encrypt_credential(plaintext: str) -> str:
    """Encrypt a credential for storage."""
    if not plaintext:
        return ""
    fernet = _get_fernet()
    encrypted = fernet.encrypt(plaintext.encode())
    return encrypted.decode()


def decrypt_credential(ciphertext: str) -> str:
    """Decrypt a stored credential."""
    if not ciphertext:
        return ""
    fernet = _get_fernet()
    decrypted = fernet.decrypt(ciphertext.encode())
    return decrypted.decode()


def mask_credential(credential: str, visible_chars: int = 4) -> str:
    """Mask a credential for display (show only last N chars)."""
    if not credential or len(credential) <= visible_chars:
        return "****"
    return "*" * (len(credential) - visible_chars) + credential[-visible_chars:]
