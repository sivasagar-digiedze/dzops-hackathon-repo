
import base64
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

# ⚠️ Move this to ENV in real usage
SECRET_KEY = b"1234567890123456"  # must be 16 bytes


def encrypt_data(data: str) -> str:
    cipher = AES.new(SECRET_KEY, AES.MODE_ECB)
    encrypted = cipher.encrypt(pad(data.encode(), AES.block_size))
    return base64.b64encode(encrypted).decode()


def decrypt_data(token: str) -> str:
    cipher = AES.new(SECRET_KEY, AES.MODE_ECB)
    decrypted = unpad(cipher.decrypt(base64.b64decode(token)), AES.block_size)
    return decrypted.decode()