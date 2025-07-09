from datetime import timedelta

from django.core.signing import TimestampSigner, SignatureExpired, BadSignature

from ..utilities.constants import SIGNED_URL_EXPIRY_SECONDS
from ..utilities.errors import ResourcePermissionError

signer = TimestampSigner()

# Function to sign a URL with an expiration time
def sign_resource_id_with_expiry(file_id: str) -> str:
    signed_file_id = signer.sign(file_id)
    return signed_file_id

# Function to verify and extract the file id
def verify_signed_resource_id(signed_file_id: str, expiry_seconds: int = SIGNED_URL_EXPIRY_SECONDS) -> str:
    try:
        file_id = signer.unsign(signed_file_id, max_age=timedelta(seconds=expiry_seconds))
        return file_id
    except (BadSignature, SignatureExpired):
        raise ResourcePermissionError("URL not valid or expired.")
