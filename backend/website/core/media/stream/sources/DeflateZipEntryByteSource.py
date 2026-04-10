from .ByteSource import ByteSource
from .FragmentByteSource import FragmentedDiscordByteSource
from ..ByteRange import ByteRange

import zlib


class DeflateZipEntryByteSource(ByteSource):
    def __init__(self, file_obj, fragments, offset: int, compression_method: int, compressed_size: int, uncompressed_size: int):
        self.file_obj = file_obj
        self.offset = offset
        self.compression_method = compression_method
        self.compressed_size = compressed_size
        self.uncompressed_size = uncompressed_size

        self._source = FragmentedDiscordByteSource(file_obj, fragments)

    def size(self) -> int:
        # logical size = decompressed size
        return self.uncompressed_size

    async def read(self, byte_range: ByteRange, chunk_size: int = 128 * 1024):
        """
        Supports logical seeking by replaying the stream and skipping output.
        Decompresses only for method 8 (deflate). Otherwise returns raw bytes.
        """

        physical_range = ByteRange(
            start=self.offset,
            end=self._source.size() - 1,
            total=self._source.size()
        )

        upstream = self._source.read(physical_range, chunk_size)

        is_deflate = (self.compression_method == 8)
        decompressor = zlib.decompressobj(-zlib.MAX_WBITS) if is_deflate else None

        buffer = b""
        header_parsed = False

        compressed_consumed = 0
        output_pos = 0

        target_start = byte_range.start
        target_end = byte_range.end

        async for chunk in upstream:
            if not chunk:
                continue

            buffer += chunk

            # ---- parse ZIP local header ----
            if not header_parsed:
                if len(buffer) < 30:
                    continue

                if buffer[0:4] != b"PK\x03\x04":
                    raise ValueError("Invalid ZIP header")

                filename_len = int.from_bytes(buffer[26:28], "little")
                extra_len = int.from_bytes(buffer[28:30], "little")
                header_size = 30 + filename_len + extra_len

                if len(buffer) < header_size:
                    continue

                buffer = buffer[header_size:]
                header_parsed = True

            # ---- consume compressed payload ----
            remaining = self.compressed_size - compressed_consumed
            if remaining <= 0:
                break

            chunk_to_feed = buffer[:remaining]
            buffer = buffer[len(chunk_to_feed):]

            compressed_consumed += len(chunk_to_feed)

            if not chunk_to_feed:
                continue

            # ---- transform (decompress or passthrough) ----
            if is_deflate:
                out = decompressor.decompress(chunk_to_feed)
            else:
                out = chunk_to_feed

            if not out:
                continue

            # ---- apply logical range ----
            out_start = output_pos
            out_end = output_pos + len(out) - 1

            if out_end < target_start:
                output_pos += len(out)
                continue

            if out_start > target_end:
                break

            slice_start = max(0, target_start - out_start)
            slice_end = min(len(out), target_end - out_start + 1)

            yield out[slice_start:slice_end]

            output_pos += len(out)

            if output_pos > target_end:
                break

        # ---- flush only for deflate ----
        if is_deflate:
            tail = decompressor.flush()
            if tail:
                out_start = output_pos
                out_end = output_pos + len(tail) - 1

                if not (out_end < target_start or out_start > target_end):
                    slice_start = max(0, target_start - out_start)
                    slice_end = min(len(tail), target_end - out_start + 1)
                    yield tail[slice_start:slice_end]