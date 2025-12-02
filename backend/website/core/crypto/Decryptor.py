from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from ...constants import EncryptionMethod


class Decryptor:
    def __init__(self, method: EncryptionMethod, key: bytes, iv: bytes = None, start_byte: int = 0):
        self.method = method
        self.start_byte = start_byte
        self.key = key
        self.iv = iv

        if self.method == EncryptionMethod.AES_CTR:
            counter_offset = self._increment_iv(self.start_byte)
            self._cipher = Cipher(algorithms.AES(self.key), modes.CTR(self.iv), backend=default_backend())
            self._decryptor = self._cipher.decryptor()
            self._discard_initial_bytes(counter_offset)

        elif self.method == EncryptionMethod.CHA_CHA_20:
            nonce, counter_offset = self._calculate_nonce(self.start_byte)
            self._cipher = Cipher(algorithms.ChaCha20(key=key, nonce=nonce), mode=None, backend=default_backend())
            self._decryptor = self._cipher.decryptor()
            self._discard_initial_bytes(counter_offset)

    # Function to increment the IV/counter for AES_CTR
    def _increment_iv(self, bytes_to_skip: int) -> int:
        blocks_to_skip = bytes_to_skip // 16
        counter_offset = bytes_to_skip % 16
        counter_int = int.from_bytes(self.iv, byteorder='big')
        counter_int += blocks_to_skip
        new_iv = counter_int.to_bytes(len(self.iv), byteorder='big')
        self.iv = new_iv
        return counter_offset

    # Function to manually increment nonce by a specified number of bytes
    def _calculate_nonce(self, bytes_to_skip: int) -> tuple[bytes, int]:
        blocks_to_skip = bytes_to_skip // 64
        counter_offset = bytes_to_skip % 64
        incremented_counter = blocks_to_skip.to_bytes(4, 'little')
        new_nonce = incremented_counter + self.iv
        return new_nonce, counter_offset

    def decrypt(self, raw_data: bytes) -> bytes:
        if self.method == EncryptionMethod.Not_Encrypted:
            return raw_data
        return self._decryptor.update(raw_data)

    def finalize(self) -> bytes:
        if self.method == EncryptionMethod.Not_Encrypted:
            return b''

        return self._decryptor.finalize()

    # Discard initial bytes to align decryption correctly
    def _discard_initial_bytes(self, bytes_to_discard: int) -> None:
        if bytes_to_discard > 0:
            self._decryptor.update(b'\x00' * bytes_to_discard)
