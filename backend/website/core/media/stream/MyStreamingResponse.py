import re

from django.http import StreamingHttpResponse

from .ByteRange import ByteRange
from .sources.ByteSource import ByteSource
from ...errors import RangeNotSatisfiable


class MyStreamingResponse(StreamingHttpResponse):
    def __init__(self, request, byte_source: ByteSource, content_type: str, content_disposition: str, etag: str | None = None, cache_control: str | None = None, accept_ranges: bool = True,
                 chunk_size: int = 128 * 1024):
        self.request = request
        self.byte_source = byte_source
        self.total_size = byte_source.size()
        self.chunk_size = chunk_size

        byte_range, is_partial = self._resolve_range()
        try:
            self.byte_source.check_byte_range(byte_range)
        except ValueError as exc:
            raise RangeNotSatisfiable(str(exc)) from exc

        # --- init parent ---
        super().__init__(
            streaming_content=self.byte_source.read(byte_range, chunk_size=self.chunk_size),
            content_type=content_type,
            status=206 if is_partial else 200,
        )

        # --- headers ---
        self["Content-Disposition"] = content_disposition
        self["Content-Length"] = str(byte_range.length)

        if accept_ranges:
            self["Accept-Ranges"] = "bytes"

        if is_partial:
            self["Content-Range"] = f"bytes {byte_range.start}-{byte_range.end}/{self.total_size}"

        if etag is not None:
            self["ETag"] = etag

        if cache_control is not None:
            self["Cache-Control"] = cache_control

    # =========================================================
    # Range handling (internal)
    # =========================================================

    def _resolve_range(self):
        range_header = self.request.headers.get("Range")

        # Empty resource: no range possible
        if self.total_size == 0:
            return ByteRange(start=0, end=0, total=self.total_size), False

        if not range_header:
            return ByteRange(start=0, end=self.total_size - 1, total=self.total_size), False

        start, end, suffix = self._parse_range_header(range_header)

        try:
            byte_range = self._normalize_range(start, end, suffix)
        except ValueError as exc:
            raise RangeNotSatisfiable(str(exc)) from exc

        return byte_range, True

    def _parse_range_header(self, header: str):
        match = re.match(r"^bytes=(\d*)-(\d*)$", header.strip())
        if not match:
            raise RangeNotSatisfiable("Invalid Range header")

        start_raw, end_raw = match.groups()

        # bytes=-500
        if start_raw == "" and end_raw != "":
            return None, None, int(end_raw)

        # bytes=100-
        if start_raw != "" and end_raw == "":
            return int(start_raw), None, None

        # bytes=100-200
        if start_raw != "" and end_raw != "":
            start = int(start_raw)
            end = int(end_raw)

            if end < start:
                raise RangeNotSatisfiable("Invalid range")

            return start, end, None

        raise RangeNotSatisfiable("Invalid Range header")

    def _normalize_range(self, start, end, suffix):
        total = self.total_size

        if total == 0:
            raise ValueError("Empty resource")

        # suffix range: bytes=-500
        if suffix is not None:
            if suffix <= 0:
                raise ValueError("Invalid suffix")

            if suffix >= total:
                return ByteRange(0, total - 1, total)

            return ByteRange(total - suffix, total - 1, total)

        # normal ranges
        if start is None:
            start = 0

        if start >= total:
            raise ValueError("Range start exceeds size")

        if end is None or end >= total:
            end = total - 1

        return ByteRange(start, end, total)
