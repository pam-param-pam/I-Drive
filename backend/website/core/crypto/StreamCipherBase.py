import base64
import os
from typing import Optional

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from website.constants import EncryptionMethod


class StreamCipherBase:
    def __init__(self, method: EncryptionMethod, key, iv, start_byte=0):
        self.method = method
        self.key = key

        # IV / nonce base:
        # - AES-CTR: full counter block (16 bytes)
        # - ChaCha20: 12-byte nonce (counter added separately)
        self.iv = iv
        self._start_byte = start_byte

        self._ctx = None

        if self.method == EncryptionMethod.AES_CTR:
            new_iv, counter_offset = self._increment_iv(self._start_byte)
            cipher = Cipher(algorithms.AES(self.key), modes.CTR(new_iv), backend=default_backend())
            self._ctx = self._create_ctx(cipher)
            self._discard_initial_bytes(counter_offset)

        elif self.method == EncryptionMethod.CHA_CHA_20:
            nonce, counter_offset = self._calculate_nonce(self._start_byte)
            cipher = Cipher(algorithms.ChaCha20(key=self.key, nonce=nonce), mode=None, backend=default_backend())
            self._ctx = self._create_ctx(cipher)
            self._discard_initial_bytes(counter_offset)

        elif self.method == EncryptionMethod.Not_Encrypted:
            self._ctx = None

        else:
            raise ValueError(f"Unsupported encryption method: {self.method}")

    def _create_ctx(self, cipher):
        raise NotImplementedError

    def _increment_iv(self, bytes_to_skip):
        if self.method != EncryptionMethod.AES_CTR:
            raise ValueError("Wrong method")

        blocks_to_skip = bytes_to_skip // 16
        counter_offset = bytes_to_skip % 16

        counter_int = int.from_bytes(self.iv)
        new_counter = counter_int + blocks_to_skip

        return new_counter.to_bytes(len(self.iv)), counter_offset

    def _calculate_nonce(self, bytes_to_skip: int):
        if self.method != EncryptionMethod.CHA_CHA_20:
            raise ValueError("Wrong method")

        blocks_to_skip = bytes_to_skip // 64
        counter_offset = bytes_to_skip % 64
        counter_prefix = blocks_to_skip.to_bytes(4, "little")
        return counter_prefix + self.iv, counter_offset

    def _discard_initial_bytes(self, bytes_to_discard):
        if bytes_to_discard > 0:
            self._ctx.update(b"\x00" * bytes_to_discard)

    def finalize(self):
        if self.method == EncryptionMethod.Not_Encrypted:
            return b""
        return self._ctx.finalize()

    @staticmethod
    def generate_iv(method: EncryptionMethod) -> Optional[bytes]:
        if method == EncryptionMethod.AES_CTR:
            iv = os.urandom(16)
        elif method == EncryptionMethod.CHA_CHA_20:
            iv = os.urandom(12)
        elif method == EncryptionMethod.Not_Encrypted:
            return None
        else:
            raise ValueError(f"unable to match encryptionMethod: {method}")

        return iv

    @staticmethod
    def generate_key(method: EncryptionMethod) -> Optional[bytes]:
        if method == EncryptionMethod.Not_Encrypted:
            return None

        key = os.urandom(32)
        return key

    def get_base64_key(self):
        if self.method == EncryptionMethod.Not_Encrypted or self.key is None:
            return None
        return base64.b64encode(self.key).decode()

    def get_base64_iv(self):
        if self.method == EncryptionMethod.Not_Encrypted or self.iv is None:
            return None
        return base64.b64encode(self.iv).decode()
