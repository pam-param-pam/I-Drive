import re
from typing import Optional

import requests
import shortuuid
from django.contrib.admin.utils import quote
from django.utils.encoding import smart_str

from ..dataModels.general import ResponseDict, ErrorDict
from ..helpers import get_ip


def build_response(task_id: str, message: str) -> ResponseDict:
    return {"task_id": task_id, "message": message}


def build_http_error_response(code: int, error: str, details: str) -> ErrorDict:
    return {"code": code, "error": error, "details": details}


def get_content_disposition_string(name: str) -> tuple[str, str]:
    name_ascii = quote(smart_str(name))
    encoded_name = quote(name)
    return name_ascii, encoded_name


def get_location_from_ip(ip: str) -> tuple[Optional[str], Optional[str]]:
    response = requests.get(f'https://ipapi.co/{ip}/json/')
    if not response.ok:
        print("===FAILED TO GET GEO LOCATION DATA===")
        return None, None

    data = response.json()

    country = data.get('country_name')
    city = data.get('city')
    return country, city



def get_device_metadata(request):
    """
    Extracts IP, user-agent, device info, and geolocation from a request.
    """
    ip, _ = get_ip(request)
    ua = request.user_agent

    device_family = '' if (ua.device.family or '') == 'Other' else (ua.device.family or '')
    device_name = f"{device_family} {ua.os.family or ''} {ua.os.version_string or ''}".strip()

    if ua.is_mobile or ua.is_tablet:
        device_type = "mobile"
    elif ua.is_pc:
        device_type = "pc"
    else:
        device_type = "code"

    country, city = get_location_from_ip(ip)

    # Generate backend-only device_id
    device_id = shortuuid.uuid()

    return {
        "ip": ip,
        "user_agent": str(ua),
        "device_name": device_name,
        "device_type": device_type,
        "country": country,
        "city": city,
        "device_id": device_id,
    }



def parse_range_header(range_header: str) -> tuple[bool, int, Optional[int]]:
    if range_header:
        range_match = re.match(r'bytes=(\d+)-(\d+)?', range_header)
        if range_match:
            start_byte = int(range_match.group(1))
            end_byte = int(range_match.group(2)) if range_match.group(2) else None
        else:
            raise ValueError("Invalid range header")
    else:
        start_byte = 0
        end_byte = None

    return bool(range_header), start_byte, end_byte