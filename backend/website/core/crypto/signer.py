import base64
import hashlib
import hmac
import os
import re
import time
from datetime import datetime, timezone
from urllib.parse import urlencode

from website.constants import SIGNED_URL_EXPIRY_SECONDS
from website.core.errors import URLInvalidOrExpired


SECRET = os.environ["SIGNING_SECRET"].encode()
_RESOURCE_PATH = re.compile(
    r"^/files/(?P<file_id>[^/]+)(?:/(?P<kind>thumbnail|moments|subtitles)/[^/]+)?/stream$"
)


def _infer_claims(path: str) -> tuple[str, str, int]:
    match = _RESOURCE_PATH.match(path)
    if not match:
        raise ValueError("Signed resource paths must identify a file stream")
    file_id = match.group("file_id")
    purpose = {
        None: "file_download",
        "thumbnail": "thumbnail",
        "moments": "moment",
        "subtitles": "subtitle",
    }[match.group("kind")]
    from website.models import File
    version = File.objects.filter(id=file_id).values_list("resource_version", flat=True).first()
    if version is None:
        raise URLInvalidOrExpired("Resource no longer exists.")
    return file_id, purpose, int(version)


def _payload(path: str, file_id: str, version: int, purpose: str, share_id: str | None, expires: int) -> bytes:
    return f"{path}:{file_id}:{version}:{purpose}:{share_id or ''}:{expires}".encode()


def sign_resource(
    path: str,
    *,
    resource_id: str | None = None,
    resource_version: int | None = None,
    purpose: str | None = None,
    share_id: str | None = None,
) -> str:
    if resource_id is None or resource_version is None or purpose is None:
        inferred_id, inferred_purpose, inferred_version = _infer_claims(path)
        resource_id = resource_id or inferred_id
        resource_version = resource_version if resource_version is not None else inferred_version
        purpose = purpose or inferred_purpose
    expires = int(time.time()) + SIGNED_URL_EXPIRY_SECONDS
    digest = hmac.new(
        SECRET,
        _payload(path, str(resource_id), int(resource_version), purpose, share_id, expires),
        hashlib.sha256,
    ).digest()
    sig = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    values = {
        "sig": sig,
        "expires": expires,
        "resource_id": str(resource_id),
        "resource_version": int(resource_version),
        "purpose": purpose,
    }
    if share_id:
        values["share_id"] = str(share_id)
    return f"?{urlencode(values)}"


def unsign_resource(
    path: str,
    expires: int,
    sig: str,
    resource_id: str,
    resource_version: int,
    purpose: str,
    share_id: str | None = None,
) -> dict:
    if time.time() > expires:
        raise URLInvalidOrExpired("URL expired.")
    expected = base64.urlsafe_b64encode(hmac.new(
        SECRET,
        _payload(path, str(resource_id), int(resource_version), purpose, share_id, expires),
        hashlib.sha256,
    ).digest()).rstrip(b"=").decode()
    if not hmac.compare_digest(sig, expected):
        raise URLInvalidOrExpired("Bad signature.")
    return {
        "resource_id": str(resource_id),
        "resource_version": int(resource_version),
        "purpose": purpose,
        "share_id": str(share_id) if share_id else None,
        "expires_at": datetime.fromtimestamp(expires, tz=timezone.utc),
    }


def verify_signed_resource_request(request, file_id: str, expected_purpose: str) -> dict:
    try:
        claims = unsign_resource(
            request.path_info,
            int(request.GET["expires"]),
            request.GET["sig"],
            request.GET["resource_id"],
            int(request.GET["resource_version"]),
            request.GET["purpose"],
            request.GET.get("share_id"),
        )
    except (KeyError, TypeError, ValueError) as exception:
        raise URLInvalidOrExpired("Malformed signed URL.") from exception
    if claims["resource_id"] != str(file_id) or claims["purpose"] != expected_purpose:
        raise URLInvalidOrExpired("Signed URL has the wrong resource or purpose.")
    request.signed_resource_claims = claims
    return claims
