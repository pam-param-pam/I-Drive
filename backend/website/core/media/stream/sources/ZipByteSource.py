from typing import Iterable, Optional

import aiohttp
from asgiref.sync import sync_to_async
from zipFly import GenFile, ZipFly
from zipFly.EmptyFolder import EmptyFolder

from website.constants import EncryptionMethod, MAX_FILES_IN_ZIP
from website.core.crypto.Decryptor import Decryptor
from website.core.errors import BadRequestError
from website.core.media.stream.ByteRange import ByteRange
from website.core.media.stream.sources.ByteSource import ByteSource
from website.discord.Discord import discord
from website.models import Fragment
from website.tasks.helper import auto_prefetch


class ZipByteSource(ByteSource):
    def __init__(self, dict_files: Iterable[dict], owner, num_bots: int, decrypted: bool, size_file_limit: int = MAX_FILES_IN_ZIP):
        self.owner = owner
        self.num_bots = num_bots
        self.decrypted = decrypted
        self.size_file_limit = size_file_limit

        self.entries = self._build_entries(dict_files)
        self._size = self._calculate_size()

    def _build_entries(self, dict_files: Iterable[dict]) -> list[dict]:
        entries = []
        file_count = 0

        for entry in dict_files:
            entries.append(entry)
            file_count += 1

            if file_count > self.size_file_limit:
                raise BadRequestError(f"ZIP contains more than {self.size_file_limit} files")

        return entries

    # -----------------------------------------------------

    @staticmethod
    def _fetch_fragments_sync(file_id):
        return list(Fragment.objects.filter(file_id=file_id).order_by("sequence"))

    async def _stream_file(self, entry: dict, chunk_size=8192 * 16):
        async with aiohttp.ClientSession() as session:
            decryptor = Decryptor(
                method=EncryptionMethod(entry["encryption_method"]),
                key=entry.get("key"),
                iv=entry.get("iv"),
            )

            fragments = await sync_to_async(self._fetch_fragments_sync)(entry["id"])

            for fragment in fragments:
                url = await sync_to_async(discord.get_attachment_url)(self.owner, fragment, True)
                auto_prefetch(fragment.id)

                async with session.get(url) as response:
                    response.raise_for_status()

                    async for raw_data in response.content.iter_chunked(chunk_size):
                        if self.decrypted:
                            yield decryptor.decrypt(raw_data)
                        else:
                            yield raw_data

    def _make_zipfly_file(self, entry: dict):
        if entry["isDir"]:
            return EmptyFolder(name=entry["name"])

        custom_payload = None
        if not self.decrypted:
            method = int(entry["encryption_method"]).to_bytes(2, byteorder="little")
            iv = bytes(entry.get("iv") or b"")
            key = bytes(entry.get("key") or b"")
            custom_payload = method + iv + key

        return GenFile(
            name=entry["name"],
            generator=self._stream_file(entry),
            size=entry["size"],
            crc=entry["crc"],
            validate_crc=self.decrypted,
            custom_payload=custom_payload
        )

    def _build_zipfly(self, byte_offset: int = 0):
        files = [self._make_zipfly_file(entry) for entry in self.entries]
        return ZipFly(files, byte_offset=byte_offset)

    def _calculate_size(self) -> int:
        zipfly = self._build_zipfly()
        return zipfly.calculate_archive_size()

    # -----------------------------------------------------

    def size(self) -> int:
        return self._size

    # -----------------------------------------------------

    async def read(self, byte_range: Optional[ByteRange] = None, chunk_size=128 * 1024):
        byte_offset = byte_range.start
        max_bytes = byte_range.length

        zipfly = self._build_zipfly(byte_offset=byte_offset)

        sent = 0

        async for chunk in zipfly.async_stream_parallel(prefetch_files=self.num_bots):
            if sent >= max_bytes:
                break

            remaining = max_bytes - sent
            if len(chunk) > remaining:
                chunk = chunk[:remaining]

            sent += len(chunk)
            yield chunk
