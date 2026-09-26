import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from django.conf import settings

from website.core.crypto.signer import unsign_resource
from website.core.errors import ResourcePermissionError, URLInvalidOrExpired


def _trusted_client_ip(request) -> str:
    if settings.BEHIND_NGINX:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            return forwarded.split(",", 1)[0].strip()
    return request.META.get("REMOTE_ADDR", "")


@dataclass(frozen=True)
class UserPrincipal:
    user_id: int
    device_id: str | None
    request_id: str
    client_ip: str

@dataclass(frozen=True)
class SharePrincipal:
    share_token: str
    authenticated_user_id: int | None


@dataclass(frozen=True)
class SignedResourcePrincipal:
    file_id: str
    expires_at: datetime
    client_ip: str | None
    share_id: str | None

@dataclass(frozen=True)
class WorkPrincipal:
    work_type: str
    work_id: str
    owner_id: int

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
        )

    @staticmethod
    def from_share_request(request, token: str) -> SharePrincipal:
        if not isinstance(token, str) or not token:
            raise ResourcePermissionError("A valid share token is required")
        user = getattr(request, "user", None)
        authenticated_user_id = user.id if user and user.is_authenticated else None
        return SharePrincipal(token, authenticated_user_id)

    @staticmethod
    def from_signed_request(request, file_id: str, share_id: str | None = None) -> SignedResourcePrincipal:
        try:
            expires = int(request.GET["expires"])
            sig = request.GET["sig"]
        except (KeyError, TypeError, ValueError) as exception:
            raise URLInvalidOrExpired("Malformed signed URL.") from exception
        unsign_resource(request.path_info, expires, sig)
        return SignedResourcePrincipal(
            file_id=str(file_id),
            expires_at=datetime.fromtimestamp(expires, tz=timezone.utc),
            client_ip=None if share_id else _trusted_client_ip(request),
            share_id=str(share_id) if share_id else None,
        )


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
        )
