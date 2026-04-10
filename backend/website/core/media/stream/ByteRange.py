from dataclasses import dataclass


@dataclass(frozen=True)
class ByteRange:
    start: int
    end: int
    total: int

    def __post_init__(self):
        if self.total < 0:
            raise ValueError("Total size cannot be negative")
        if self.start < 0:
            raise ValueError("Range start cannot be negative")
        if self.end < self.start:
            raise ValueError("Range end cannot be smaller than start")
        if self.end >= self.total > 0:
            raise ValueError("Range end exceeds total size")

    @property
    def length(self) -> int:
        if self.total == 0:
            return 0
        return self.end - self.start + 1


