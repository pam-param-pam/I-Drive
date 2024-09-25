import zlib


class Compressor:
    def __init__(self, file):
        self.file = file

        if file.compression_method == 0:
            self.process = self._process_through
            self.tail = self._no_tail
        elif file.compression_method == 8:  # deflate compression
            self.compr = zlib.compressobj(5, zlib.DEFLATED, -15)
            self.process = self._process_deflate
            self.tail = self._tail_deflate

    # no compression
    def _process_through(self, chunk):
        self.file.original_size += len(chunk)
        self.file.compressed_size += len(chunk)
        self.file.crc = zlib.crc32(chunk, self.file.crc)
        return chunk

    def _no_tail(self):
        return b''

    # deflate compression
    def _process_deflate(self, chunk):
        self.file.original_size += len(chunk)
        self.file.crc = zlib.crc32(chunk, self.file.crc)
        chunk = self.compr.compress(chunk)
        self.file.compressed_size += len(chunk)
        return chunk

    def _tail_deflate(self):
        chunk = self.compr.flush(zlib.Z_FINISH)
        self.file.compressed_size += len(chunk)
        return chunk