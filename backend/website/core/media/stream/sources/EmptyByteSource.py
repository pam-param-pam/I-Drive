from .ByteSource import ByteSource
from ..ByteRange import ByteRange


class EmptyByteSource(ByteSource):
    def size(self) -> int:
        return 0

    async def read(self, byte_range: ByteRange, chunk_size: int = 128 * 1024):
        yield b""
