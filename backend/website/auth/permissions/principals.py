import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from django.conf import settings

from website.core.errors import ResourcePermissionError


_FACTORY_TOKEN = object()


def _trusted_client_ip(request) -> str:
    if settings.BEHIND_NGINX:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            return forwarded.split(",", 1)[0].strip()
    return request.META.get("REMOTE_ADDR", "")


class _TrustedPrincipal:
    @staticmethod
    def _assert_factory(token: object) -> None:
        if token is not _FACTORY_TOKEN:
            raise TypeError("Principals must be created by a trusted principal factory")


@dataclass(frozen=True, init=False)
class UserPrincipal(_TrustedPrincipal):
    user_id: int
    device_id: str | None
    request_id: str
    client_ip: str

    def __init__(self, user_id: int, device_id: str | None, request_id: str, client_ip: str, *, _token: object = None):
        self._assert_factory(_token)
        object.__setattr__(self, "user_id", user_id)
        object.__setattr__(self, "device_id", device_id)
        object.__setattr__(self, "request_id", request_id)
        object.__setattr__(self, "client_ip", client_ip)


@dataclass(frozen=True, init=False)
class SharePrincipal(_TrustedPrincipal):
    share_token: str
    authenticated_user_id: int | None

    def __init__(self, share_token: str, authenticated_user_id: int | None, *, _token: object = None):
        self._assert_factory(_token)
        object.__setattr__(self, "share_token", share_token)
        object.__setattr__(self, "authenticated_user_id", authenticated_user_id)


@dataclass(frozen=True, init=False)
class SignedResourcePrincipal(_TrustedPrincipal):
    file_id: str
    purpose: str
    resource_version: int
    expires_at: datetime
    client_ip: str | None
    share_id: str | None

    def __init__(
        self,
        file_id: str,
        purpose: str,
        resource_version: int,
        expires_at: datetime,
        client_ip: str | None,
        share_id: str | None,
        *,
        _token: object = None,
    ):
        self._assert_factory(_token)
        object.__setattr__(self, "file_id", file_id)
        object.__setattr__(self, "purpose", purpose)
        object.__setattr__(self, "resource_version", resource_version)
        object.__setattr__(self, "expires_at", expires_at)
        object.__setattr__(self, "client_ip", client_ip)
        object.__setattr__(self, "share_id", share_id)


@dataclass(frozen=True, init=False)
class WorkPrincipal(_TrustedPrincipal):
    work_type: str
    work_id: str
    owner_id: int

    def __init__(self, work_type: str, work_id: str, owner_id: int, *, _token: object = None):
        self._assert_factory(_token)
        object.__setattr__(self, "work_type", work_type)
        object.__setattr__(self, "work_id", work_id)
        object.__setattr__(self, "owner_id", owner_id)


class PrincipalFactory:
    @staticmethod
    def from_authenticated_request(request) -> UserPrincipal:
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            raise ResourcePermissionError("An authenticated user is required")

        context = getattr(request, "context", None)
        auth = getattr(request, "auth", None)
        device_id = getattr(context, "device_id", None) or getattr(auth, "device_id", None)
        request_id = getattr(context, "request_id", None) or uuid.uuid4().hex
        return UserPrincipal(
            user_id=user.id,
            device_id=device_id,
            request_id=str(request_id),
            client_ip=_trusted_client_ip(request),
            _token=_FACTORY_TOKEN,
        )

    @staticmethod
    def from_share_request(request, token: str) -> SharePrincipal:
        if not isinstance(token, str) or not token:
            raise ResourcePermissionError("A valid share token is required")
        user = getattr(request, "user", None)
        authenticated_user_id = user.id if user and user.is_authenticated else None
        return SharePrincipal(token, authenticated_user_id, _token=_FACTORY_TOKEN)

    @staticmethod
    def from_signed_request(request, expected_purpose: str) -> SignedResourcePrincipal:
        claims = getattr(request, "signed_resource_claims", None)
        if not isinstance(claims, dict) or claims.get("purpose") != expected_purpose:
            raise ResourcePermissionError("The signed resource capability is invalid for this purpose")
        try:
            expires_at = claims["expires_at"]
            if not isinstance(expires_at, datetime):
                raise TypeError
            return SignedResourcePrincipal(
                file_id=str(claims["resource_id"]),
                purpose=expected_purpose,
                resource_version=int(claims["resource_version"]),
                expires_at=expires_at,
                client_ip=None if claims.get("share_id") else _trusted_client_ip(request),
                share_id=str(claims["share_id"]) if claims.get("share_id") else None,
                _token=_FACTORY_TOKEN,
            )
        except (KeyError, TypeError, ValueError) as exception:
            raise ResourcePermissionError("The signed resource capability is malformed") from exception


class WorkPrincipalFactory:
    @staticmethod
    def from_claimed_work(work_row: Any) -> WorkPrincipal:
        work_id = getattr(work_row, "pk", None)
        owner_id = getattr(work_row, "owner_id", None)
        if owner_id is None:
            scope = getattr(work_row, "scope", None)
            owner_id = getattr(scope, "owner_id", None)
        if work_id is None or owner_id is None:
            raise TypeError("A claimed work row must expose a primary key and owner")
        return WorkPrincipal(
            work_type=work_row._meta.label_lower,
            work_id=str(work_id),
            owner_id=int(owner_id),
            _token=_FACTORY_TOKEN,
        )
