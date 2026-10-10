from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class AccountFacts:
    owner_id: int
    globally_locked: bool
    admin: bool
    capabilities: set[str]


@dataclass(frozen=True)
class ZIPScope:
    zip_id: str
    owner_id: int
    parent_id: str
    items: set[tuple[str, str]]
    folder_locks: dict[str, str | None]
    admitted_at: datetime
