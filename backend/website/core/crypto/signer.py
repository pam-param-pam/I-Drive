import base64
import hashlib
import hmac
import os
import time

from website.constants import SIGNED_URL_EXPIRY_SECONDS
from website.core.errors import URLInvalidOrExpired

SECRET = os.environ["SIGNING_SECRET"].encode()

def sign_resource(path: str) -> str:
    expires = int(time.time()) + SIGNED_URL_EXPIRY_SECONDS

    payload = f"{path}:{expires}".encode()

    digest = hmac.new(
        SECRET,
        payload,
        hashlib.md5
    ).digest()

    sig = base64.urlsafe_b64encode(digest).rstrip(b'=').decode()

    return f"?sig={sig}&expires={expires}"


def unsign_resource(path: str, expires: int, sig: str) -> str:
    if time.time() > expires:
        raise URLInvalidOrExpired("URL expired.")

    payload = f"{path}:{expires}".encode()

    expected_digest = hmac.new(
        SECRET,
        payload,
        hashlib.md5
    ).digest()

    expected_sig = base64.urlsafe_b64encode(expected_digest).rstrip(b'=').decode()

    if not hmac.compare_digest(sig, expected_sig):
        raise URLInvalidOrExpired("Bad signature.")

    return path
