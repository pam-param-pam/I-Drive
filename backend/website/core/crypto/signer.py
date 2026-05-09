import base64
import hashlib
import hmac
import time

from ..errors import URLInvalidOrExpired
from ...constants import SIGNED_URL_EXPIRY_SECONDS

SECRET = b"super-secret"


def sign_resource(resource_id: str) -> str:
    expires = int(time.time()) + SIGNED_URL_EXPIRY_SECONDS

    payload = f"{resource_id}:{expires}".encode()

    digest = hmac.new(
        SECRET,
        payload,
        hashlib.md5
    ).digest()

    sig = base64.urlsafe_b64encode(digest).rstrip(b'=').decode()

    return f"?sig={sig}&expires={expires}"

def unsign_resource(resource_id: str, expires: int, sig: str) -> str:
    if time.time() > expires:
        raise URLInvalidOrExpired("URL expired.")

    payload = f"{resource_id}:{expires}".encode()

    expected_digest = hmac.new(
        SECRET,
        payload,
        hashlib.md5
    ).digest()

    expected_sig = base64.urlsafe_b64encode(expected_digest).rstrip(b'=').decode()

    if not hmac.compare_digest(sig, expected_sig):
        raise URLInvalidOrExpired("Bad signature.")

    return resource_id
