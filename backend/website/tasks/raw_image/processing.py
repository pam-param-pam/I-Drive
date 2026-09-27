from io import BytesIO

import rawpy
import requests
from PIL import Image

from website.core.crypto.Decryptor import Decryptor
from website.core.crypto.Encryptor import Encryptor
from website.core.errors import FailedToParseRawImage
from website.models import File
from website.services import attachment_service

def format_shutter(speed: float | None) -> str:
    if speed is None:
        return ""

    if speed >= 1:
        return f"{speed:.1f}s"

    denominator = round(1 / speed)
    return f"1/{denominator}s"


def format_aperture(aperture: float | None) -> str:
    if aperture is None:
        return ""

    return f"f/{aperture:g}"

def _extract_raw_metadata(other, lens) -> dict:
    try:
        return {
            "iso": str(other.iso_speed) if other.iso_speed is not None else "",
            "shutter": format_shutter(other.shutter_speed),
            "aperture": format_aperture(other.aperture),
            "focal_length": str(other.focal_length) if other.focal_length is not None else "",
            "camera": lens.model if lens and lens.model else "",
            "camera_owner": other.artist if other.artist else "",
        }
    except Exception as e:
        raise FailedToParseRawImage(e)

def _download_and_decrypt_fragments(file_obj):
    raw_buffer = BytesIO()
    fragments = file_obj.fragments.all().order_by("sequence")
    decryptor = Decryptor(method=file_obj.get_encryption_method(), key=file_obj.key, iv=file_obj.iv)
    for frag in fragments:
        url = attachment_service.get_attachment_url(file_obj.owner, frag, file_obj)
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        raw_buffer.write(decryptor.decrypt(r.content))

    raw_buffer.seek(0)
    return raw_buffer


def _process_raw_to_webp(raw_buffer):
    with rawpy.imread(raw_buffer) as raw:
        rgb = raw.postprocess(use_camera_wb=True, half_size=True)
        metadata = _extract_raw_metadata(raw.other, raw.lens)

    img = Image.fromarray(rgb)
    img.thumbnail((1920, 1080))
    webp_buffer = BytesIO()
    img.save(webp_buffer, format="WEBP", quality=80)
    thumbnail_bytes = webp_buffer.getvalue()
    return thumbnail_bytes, metadata


def _encrypt_thumbnail(data, file_obj: File):
    method = file_obj.get_encryption_method()
    key = Encryptor.generate_key(method)
    iv = Encryptor.generate_iv(method)
    encryptor = Encryptor(method, key=key, iv=iv)
    encrypted = encryptor.encrypt(data)
    return encrypted, encryptor.get_base64_key(), encryptor.get_base64_iv(), len(encrypted)



