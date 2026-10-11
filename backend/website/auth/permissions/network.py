import ipaddress

from rest_framework.permissions import BasePermission
from website.auth.utils import _trusted_client_ip

from website.config import ALLOWED_IPS_LOCKED
from website.constants import cache
from website.services import cache_service


def ip_is_allowed(ip: str | None) -> bool:
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


def principal_network_allowed(context) -> bool:
    return ip_is_allowed(context.request.principal.client_ip)


def signed_file_network_allowed(context) -> bool:
    return context.request.principal.share_id is not None or principal_network_allowed(context)


class AllowedNetwork(BasePermission):
    message = "IP validation failed. Must be private or allowed."

    def has_permission(self, request, view):
        return ip_is_allowed(_trusted_client_ip(request))
