import time
from typing import Generator
from zipFly.BaseFile import BaseFile


class GenFile(BaseFile):

    def __init__(self, name: str, generator: Generator, compression_method: int = None, modification_time: float = None, size: int = None):
        super().__init__(compression_method)
        self._name = name
        self.generator = generator
        self._size = size
        self._modification_time = modification_time if modification_time else time.time()

    def _generate_file_data(self) -> Generator:
        yield from self.generator

    @property
    def name(self) -> str:
        return self._name

    @property
    def size(self) -> int:
        if self._size is not None:
            return self._size
        raise ValueError("Archive size not known before streaming. Probably GenFile() is missing size attribute.")

    @property
    def modification_time(self) -> float:
        return self._modification_time

    def set_file_name(self, new_name: str) -> None:
        self._name = new_name
