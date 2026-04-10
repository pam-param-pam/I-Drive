import aiohttp
from asgiref.sync import sync_to_async
from zipFly import GenFile, ZipFly
from zipFly.EmptyFolder import EmptyFolder

from .ByteRange import ByteRange
from .sources.ByteSource import ByteSource
from ...crypto.Decryptor import Decryptor
from ....discord.Discord import discord
from ....models import File
from ....tasks.helper import auto_prefetch


class ZipByteSource(ByteSource):
    def __init__(self, user_zip, dict_files):
        self.user_zip = user_zip
        self.entries = []

        for entry in dict_files:
            if entry["isDir"]:
                self.entries.append({
                    "isDir": True,
                    "name": entry["name"],
                })
            else:
                file_obj = entry["fileObj"]
                fragments = list(file_obj.fragments.all().order_by("sequence"))

                self.entries.append({
                    "isDir": False,
                    "name": entry["name"],
                    "file_obj": file_obj,
                    "fragments": fragments,
                    "size": file_obj.size,
                    "crc": file_obj.crc,
                    "owner": file_obj.owner,
                })

        self._size = None

    # -----------------------------------------------------

    async def _stream_file(self, file_obj: File, owner, fragments, chunk_size=8192 * 16):
        async with aiohttp.ClientSession() as session:
            decryptor = Decryptor(
                method=file_obj.get_encryption_method(),
                key=file_obj.key,
                iv=file_obj.iv
            )

            for fragment in fragments:
                url = await sync_to_async(discord.get_attachment_url)(owner, fragment, True)
                auto_prefetch(file_obj, fragment.id)

                async with session.get(url) as response:
                    response.raise_for_status()

                    async for raw_data in response.content.iter_chunked(chunk_size):
                        yield decryptor.decrypt(raw_data)

    def _build_zipfly(self, byte_offset=0):
        files = []

        for entry in self.entries:
            if entry["isDir"]:
                files.append(EmptyFolder(name=entry["name"]))
                continue

            files.append(GenFile(
                name=entry["name"],
                generator=self._stream_file(entry["file_obj"], entry["owner"], entry["fragments"]),
                size=entry["size"],
                crc=entry["crc"],
            ))

        return ZipFly(files, byte_offset=byte_offset)

    # -----------------------------------------------------

    def size(self) -> int:
        if self._size is None:
            # build once without offset
            zipFly = self._build_zipfly()
            self._size = zipFly.calculate_archive_size()
        return self._size

    # -----------------------------------------------------

    async def read(self, byte_range: ByteRange, chunk_size=128 * 1024):
        zipfly = self._build_zipfly(byte_offset=byte_range.start)

        sent = 0
        max_bytes = byte_range.length

        async for chunk in zipfly.async_stream_parallel():
            if sent >= max_bytes:
                break

            remaining = max_bytes - sent
            if len(chunk) > remaining:
                chunk = chunk[:remaining]

            sent += len(chunk)
            yield chunk
