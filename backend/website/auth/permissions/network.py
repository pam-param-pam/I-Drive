import ipaddress

from website.config import ALLOWED_IPS_LOCKED
from website.constants import cache
from website.services import cache_service


def ip_is_allowed(ip: str) -> bool:
    try:
        address = ipaddress.ip_address(ip)
    except (TypeError, ValueError):
        return False
    if address.is_private or address.is_loopback or ip in ALLOWED_IPS_LOCKED:
        return True
    try:
        public_ip = cache.get(cache_service.get_router_ip_key())
        return bool(public_ip) and address == ipaddress.ip_address(public_ip)
    except (TypeError, ValueError):
        return False
