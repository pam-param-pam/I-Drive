from typing import Mapping
from urllib.parse import unquote

from website.core.errors import BadRequestError


class CredentialSet:
    def __init__(self, credentials: Mapping[str, str] | None = None, header_password: str | None = None):
        normalized: dict[str, str] = {}
        for key, value in (credentials or {}).items():
            if not isinstance(key, (str, int)) or not isinstance(value, str):
                raise BadRequestError("Resource credentials must map IDs to string passwords")
            normalized[str(key)] = value
        self._credentials = normalized
        self._header_password = header_password

    @classmethod
    def empty(cls) -> "CredentialSet":
        return cls()

    def for_policy(self, policy_id: str) -> str | None:
        return self._credentials.get(str(policy_id), self._header_password)

    def for_share(self, share_id: str) -> str | None:
        return self._credentials.get(str(share_id)) or self._header_password

    @property
    def supplied(self) -> bool:
        return bool(self._credentials or self._header_password)


def extract_resource_credentials(request) -> CredentialSet:
    data = getattr(request, "data", {}) or {}
    supplied = data.get("resourcePasswords") or {}
    if not isinstance(supplied, Mapping):
        raise BadRequestError("'resourcePasswords' must be an object")
    header = request.headers.get("X-Resource-Password")
    return CredentialSet(supplied, header_password=unquote(header) if header else None)
