import base64
import hashlib
import json
import os
from typing import Union, List, Dict

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import modes, algorithms, Cipher


def hash_key(key: str) -> bytes:
    """Derives a fixed-length 32-byte key from any input key."""
    return hashlib.sha256(key.encode()).digest()


def encrypt_message(key: str, data: Union[str, List, Dict]) -> str:
    """Encrypts a message (string, list, or dict) using AES-256-CBC."""
    key_bytes = hash_key(key)
    iv = os.urandom(16)
    cipher = Cipher(algorithms.AES(key_bytes), modes.CBC(iv))
    encryptor = cipher.encryptor()

    # Convert lists/dicts to JSON string
    if isinstance(data, (dict, list)):
        data = json.dumps(data)

    # Pad message to be a multiple of 16 bytes
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(data.encode()) + padder.finalize()

    encrypted = encryptor.update(padded_data) + encryptor.finalize()
    return base64.b64encode(iv + encrypted).decode()
