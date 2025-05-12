from cryptography.fernet import Fernet
import base64
import hashlib

def get_key(password: str = "local--key"):
    key = hashlib.sha256(password.encode()).digest()
    return base64.urlsafe_b64encode(key)

def encrypt_message(message: str) -> str:
    f = Fernet(get_key())
    return f.encrypt(message.encode()).decode()

def decrypt_message(token: str) -> str:
    f = Fernet(get_key())
    return f.decrypt(token.encode()).decode()
