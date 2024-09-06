import os
from typing import Generator
from zipFly.BaseFile import BaseFile

class LocalFile(BaseFile):
    def __init__(self, file_path: str, name: str = None, compression_method: int = None):
        self._file_path = file_path
        self.chunk_size = 1048
        self._name = name if name else file_path
        super().__init__(compression_method)

    def _generate_file_data(self) -> Generator:
        with open(self._file_path, 'rb') as file:
            while True:
                chunk = file.read(self.chunk_size)
                if not chunk:
                    break
                yield chunk

    @property
    def name(self) -> str:
        return self._name

    @property
    def size(self) -> int:
        return os.path.getsize(self._file_path)

    @property
    def modification_time(self) -> float:
        return os.path.getmtime(self._file_path)

