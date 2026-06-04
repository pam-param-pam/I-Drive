from website.constants import EncryptionMethod
from website.core.crypto.StreamCipherBase import StreamCipherBase


class Decryptor(StreamCipherBase):
    def _create_ctx(self, cipher):
        return cipher.decryptor()

    def decrypt(self, raw_data):
        if self.method == EncryptionMethod.Not_Encrypted:
            return raw_data
        return self._ctx.update(raw_data)
