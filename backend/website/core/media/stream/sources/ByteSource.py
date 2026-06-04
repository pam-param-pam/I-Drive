from abc import ABC, abstractmethod
from typing import AsyncIterator

from website.core.errors import RangeNotSatisfiable
from website.core.media.stream.ByteRange import ByteRange


class ByteSource(ABC):
    @abstractmethod
    def size(self) -> int:
        raise NotImplementedError

    @abstractmethod
    async def read(self, byte_range: ByteRange, chunk_size: int) -> AsyncIterator[bytes]:
        raise NotImplementedError

    def check_byte_range(self, byte_range: ByteRange) -> None:
        size = self.size()
        if byte_range.end > size:
            raise RangeNotSatisfiable("Range end beyond file size")
