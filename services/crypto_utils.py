# services/crypto_utils.py
import base64
import os
from cryptography.fernet import Fernet
from dotenv import load_dotenv
load_dotenv()

# Load key from environment (.env)
IMAP_SECRET_KEY = os.environ.get("IMAP_SECRET_KEY")

if not IMAP_SECRET_KEY:
    raise RuntimeError(
        "❌ Missing IMAP_SECRET_KEY in environment. "
        "Create a .env file with IMAP_SECRET_KEY=<your_key>"
    )

# Create Fernet instance
fernet = Fernet(IMAP_SECRET_KEY.encode())


def encrypt_password(password: str) -> str:
    """
    Encrypt a plaintext IMAP password using Fernet.
    Returns base64 encrypted string.
    """
    if not password:
        return ""
    token = fernet.encrypt(password.encode())
    return base64.urlsafe_b64encode(token).decode()


def decrypt_password(token_b64: str) -> str:
    """
    Decrypt a previously encrypted password.
    """
    if not token_b64:
        return ""

    token = base64.urlsafe_b64decode(token_b64.encode())
    decrypted = fernet.decrypt(token)
    return decrypted.decode()
