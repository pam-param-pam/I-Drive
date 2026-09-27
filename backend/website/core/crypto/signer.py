import base64
import hashlib
import hmac
import os
import time

from website.constants import SIGNED_URL_EXPIRY_SECONDS
from website.core.errors import URLInvalidOrExpired


SECRET = os.environ["SIGNING_SECRET"].encode()


def _signature(path: str, expires: int) -> str:
    payload = f"{path}:{expires}".encode()
    digest = hmac.new(SECRET, payload, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def sign_resource(path: str) -> str:
    expires = int(time.time()) + SIGNED_URL_EXPIRY_SECONDS
    return f"?sig={_signature(path, expires)}&expires={expires}"


def unsign_resource(path: str, expires: int, sig: str) -> str:
    if time.time() > expires:
        raise URLInvalidOrExpired("URL expired.")
    if not hmac.compare_digest(sig, _signature(path, expires)):
        raise URLInvalidOrExpired("Bad signature.")
    return path

def verify_signed_url(request) -> int:
    try:
        expires = int(request.GET["expires"])
        sig = request.GET["sig"]
    except (KeyError, TypeError, ValueError) as exception:
        raise URLInvalidOrExpired("Malformed signed URL.") from exception

    unsign_resource(request.path_info, expires, sig)
    return expires