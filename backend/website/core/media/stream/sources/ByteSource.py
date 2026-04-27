from abc import ABC, abstractmethod
from typing import AsyncIterator

from ..ByteRange import ByteRange

# TODO allow for this to validate the byte_range before streaming starts

class ByteSource(ABC):
    @abstractmethod
    def size(self) -> int:
        raise NotImplementedError

    @abstractmethod
    def read(self, byte_range: ByteRange, chunk_size: int = 128 * 1024) -> AsyncIterator[bytes]:
        raise NotImplementedError

    def check_byte_range(self, byte_range: ByteRange) -> None:
        if byte_range.end > self.size():
            raise KeyError("End range too big")
