from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from website.auth.utils import _trusted_client_ip
from website.core.crypto.signer import verify_signed_url
from website.core.errors import ResourcePermissionError


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
    resource_id: str
    resource_kind: Literal["file", "zip"]
    expires_at: datetime
    client_ip: str | None
    share_id: str | None = None


class PrincipalFactory:
    @staticmethod
    def from_authenticated_request(request) -> UserPrincipal:
        """Require an authenticated user and validated request context for owner actions."""
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            raise ResourcePermissionError("An authenticated user is required")

        if not request.context:
            raise ValueError("A valid request context must be provided")

        return UserPrincipal(
            user_id=request.user.id,
            device_id=request.context.device_id,
            request_id=request.context.request_id,
            client_ip=request.context.client_ip,
        )

    @staticmethod
    def from_share_request(request, token: str) -> SharePrincipal:
        authenticated_user_id = request.user.id if request.user and request.user.is_authenticated else None
        return SharePrincipal(token, authenticated_user_id)

    @staticmethod
    def from_signed_request(request, file_id: str, share_id: str | None = None) -> SignedResourcePrincipal:
        """Verify the signed URL and retain its expiry and trusted client address."""
        expires = verify_signed_url(request)
        return SignedResourcePrincipal(
            resource_id=file_id,
            resource_kind="file",
            expires_at=datetime.fromtimestamp(expires, tz=timezone.utc),
            client_ip=_trusted_client_ip(request),
            share_id=share_id,
        )

    @staticmethod
    def from_signed_zip_request(request, zip_id: str) -> SignedResourcePrincipal:
        """Verify the signed ZIP URL before constructing its scoped principal."""
        expires = verify_signed_url(request)
        return SignedResourcePrincipal(
            resource_id=zip_id,
            resource_kind="zip",
            expires_at=datetime.fromtimestamp(expires, tz=timezone.utc),
            client_ip=_trusted_client_ip(request),
        )
