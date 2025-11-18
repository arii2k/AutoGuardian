# services/encryption_utils.py — AES-256-GCM helpers for local privacy
import os
import json
from typing import Any
from base64 import urlsafe_b64decode, urlsafe_b64encode

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    CRYPTO_OK = True
except Exception:
    CRYPTO_OK = False

def _get_raw_key() -> bytes | None:
    """
    Use a 32-byte base64url key from env AG_ENCRYPTION_KEY.
    Generate with: python -c "import os,base64;print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
    """
    val = os.environ.get("AG_ENCRYPTION_KEY", "").strip()
    if not val:
        return None
    try:
        raw = urlsafe_b64decode(val)
        return raw if len(raw) == 32 else None
    except Exception:
        return None

def encrypt_json_file(path: str) -> bool:
    """Encrypt file in place. Returns True if encrypted, False if skipped."""
    if not CRYPTO_OK:
        return False
    key = _get_raw_key()
    if not key or not os.path.exists(path):
        return False
    try:
        data = open(path, "rb").read()
        aes = AESGCM(key)
        nonce = os.urandom(12)
        ct = aes.encrypt(nonce, data, None)
        open(path + ".enc", "wb").write(nonce + ct)
        os.replace(path + ".enc", path)
        return True
    except Exception:
        return False

def decrypt_json_file(path: str) -> bytes | None:
    """Return decrypted bytes (does not overwrite file)."""
    if not CRYPTO_OK:
        return None
    key = _get_raw_key()
    if not key or not os.path.exists(path):
        return None
    try:
        raw = open(path, "rb").read()
        nonce, ct = raw[:12], raw[12:]
        aes = AESGCM(key)
        return aes.decrypt(nonce, ct, None)
    except Exception:
        return None
