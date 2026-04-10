from dataclasses import dataclass

import aiohttp
from asgiref.sync import sync_to_async

from ..ByteRange import ByteRange
from ....crypto.Decryptor import Decryptor
from .....discord.Discord import discord
from .....models import Fragment
from .ByteSource import ByteSource
from .....tasks.helper import auto_prefetch


@dataclass(frozen=True)
class FragmentRange:
    fragment_index: int
    fragment: Fragment
    local_start: int
    local_end: int
    global_start: int
    global_end: int

    @property
    def length(self) -> int:
        return self.local_end - self.local_start + 1

class FragmentedDiscordByteSource(ByteSource):
    def __init__(self, file_obj, fragments):
        self.file_obj = file_obj
        self.fragments = list(fragments.order_by("sequence"))

    def size(self) -> int:
        return self.file_obj.size

    def map_range(self, byte_range: ByteRange) -> list[FragmentRange]:
        mappings: list[FragmentRange] = []

        current_global_offset = 0
        target_start = byte_range.start
        target_end = byte_range.end

        for fragment_index, fragment in enumerate(self.fragments):
            fragment_global_start = current_global_offset
            fragment_global_end = current_global_offset + fragment.size - 1

            overlaps = not (target_end < fragment_global_start or target_start > fragment_global_end)
            if overlaps:
                global_start = max(target_start, fragment_global_start)
                global_end = min(target_end, fragment_global_end)

                local_start = global_start - fragment_global_start
                local_end = global_end - fragment_global_start

                mappings.append(FragmentRange(
                    fragment_index=fragment_index,
                    fragment=fragment,
                    local_start=local_start,
                    local_end=local_end,
                    global_start=global_start,
                    global_end=global_end,
                ))

            current_global_offset += fragment.size

            if current_global_offset > target_end:
                break

        if not mappings:
            raise ValueError(f"No fragment mapping produced for range {byte_range.start}-{byte_range.end}")

        return mappings

    async def read(self, byte_range: ByteRange, chunk_size: int = 128 * 1024):
        mappings = self.map_range(byte_range)

        decryptor = Decryptor(
            method=self.file_obj.get_encryption_method(),
            key=self.file_obj.key,
            iv=self.file_obj.iv,
            start_byte=byte_range.start,
        )

        async with aiohttp.ClientSession() as session:
            for mapping in mappings:
                fragment = mapping.fragment

                auto_prefetch(self.file_obj, fragment.id)

                url = await sync_to_async(discord.get_attachment_url)(self.file_obj.owner, fragment)

                headers = {"Range": f"bytes={mapping.local_start}-{mapping.local_end}"}

                async with session.get(url, headers=headers) as response:
                    response.raise_for_status()

                    async for raw_chunk in response.content.iter_chunked(chunk_size):
                        data = decryptor.decrypt(raw_chunk)
                        if data:
                            yield data

        if self.file_obj.is_encrypted():
            tail = decryptor.finalize()
            if tail:
                yield tail
