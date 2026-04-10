import mimetypes
import re
from typing import Optional
from urllib.parse import quote

import requests
from django.http import HttpResponse, HttpRequest
from django.utils.encoding import smart_str

from .stream.MyStreamingResponse import MyStreamingResponse
from ..crypto.Decryptor import Decryptor
from ..errors import DiscordError


def decrypt_bytes(content: bytes, decryptor: Decryptor) -> bytes:
    out = decryptor.decrypt(content)
    out += decryptor.finalize()
    return out


def fetch_discord_file(url: str, timeout=5) -> bytes:
    response = requests.get(url, timeout=timeout)
    if not response.ok:
        raise DiscordError(response)
    return response.content


def get_content_disposition_string(name: str) -> tuple[str, str]:
    name_ascii = smart_str(name, errors="ignore")
    name_ascii = re.sub(r'[^\x20-\x7E]', '_', name_ascii)

    # filename*= → RFC 5987 UTF-8 + percent encoding
    name_encoded = quote(name, safe="")

    return name_ascii, name_encoded


def build_binary_response(content: bytes, filename: str, content_type: str, inline: bool, cache_control: str | None = None, vary: list[str] | None = None) -> HttpResponse:
    response = HttpResponse(content, content_type=content_type)

    name_ascii, name_encoded = get_content_disposition_string(filename)
    disposition = "inline" if inline else "attachment"

    response["Content-Disposition"] = (
        f'{disposition}; filename="{name_ascii}"; filename*=UTF-8\'\'{name_encoded}'
    )

    if cache_control:
        response["Cache-Control"] = cache_control

    if vary:
        response["Vary"] = ", ".join(vary)

    return response


def build_streaming_response(request: HttpRequest, byte_source, filename: str, content_type: Optional[str] = None, inline: bool = False, etag: Optional[str] = None,
                             cache_control: Optional[str] = None, vary: Optional[list[str]] = None, x_frame_from_referer: bool = True) -> MyStreamingResponse:
    if not content_type:
        mime, _ = mimetypes.guess_type(filename)
        content_type = mime or "application/octet-stream"

    name_ascii, name_encoded = get_content_disposition_string(filename)
    disposition_type = "inline" if inline else "attachment"
    content_disposition = (
        f'{disposition_type}; filename="{name_ascii}"; filename*=UTF-8\'\'{name_encoded}'
    )

    response = MyStreamingResponse(
        request=request,
        byte_source=byte_source,
        content_type=content_type,
        content_disposition=content_disposition,
        etag=etag,
        cache_control=cache_control,
    )

    if vary:
        response["Vary"] = ", ".join(vary)

    if x_frame_from_referer:
        referer = request.headers.get("Referer")
        response["X-Frame-Options"] = f"ALLOW-FROM {referer}" if referer else "DENY"

    return response
