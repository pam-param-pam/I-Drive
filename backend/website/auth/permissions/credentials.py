from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping
from urllib.parse import unquote

from website.core.errors import BadRequestError


@dataclass(frozen=True, init=False)
class CredentialSet:
    _credentials: Mapping[str, str]
    fallback: str | None

    def __init__(self, credentials: Mapping[str, str] | None = None, fallback: str | None = None):
        normalized: dict[str, str] = {}
        for key, value in (credentials or {}).items():
            if not isinstance(key, (str, int)) or not isinstance(value, str):
                raise BadRequestError("Resource credentials must map IDs to string passwords")
            normalized[str(key)] = value
        object.__setattr__(self, "_credentials", MappingProxyType(normalized))
        object.__setattr__(self, "fallback", fallback)

    @classmethod
    def empty(cls) -> "CredentialSet":
        return cls()

    def for_policy(self, policy_id: str) -> str | None:
        return self._credentials.get(str(policy_id), self.fallback)

    def for_share(self, share_id: str, share_token: str | None = None) -> str | None:
        return self._credentials.get(str(share_id)) or (
            self._credentials.get(str(share_token)) if share_token else None
        ) or self.fallback

    @property
    def supplied(self) -> bool:
        return bool(self._credentials or self.fallback)


def extract_resource_credentials(request) -> CredentialSet:
    data = getattr(request, "data", {}) or {}
    supplied = data.get("resourcePasswords") or {}
    if not isinstance(supplied, Mapping):
        raise BadRequestError("'resourcePasswords' must be an object")
    header = request.headers.get("X-Resource-Password")
    return CredentialSet(supplied, unquote(header) if header else None)
