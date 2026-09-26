import ipaddress

from rest_framework.permissions import BasePermission

from website.config import ALLOWED_IPS_LOCKED
from website.services import cache_service
from website.constants import cache

from .principals import _trusted_client_ip


class AllowedNetwork(BasePermission):
    message = "IP validation failed. Must be private or allowed."

    def has_permission(self, request, view):
        value = _trusted_client_ip(request)
        try:
            address = ipaddress.ip_address(value)
        except (TypeError, ValueError):
            return False
        if address.is_private or address.is_loopback or value in ALLOWED_IPS_LOCKED:
            return True
        public_ip = cache.get(cache_service.get_router_ip_key())
        try:
            return bool(public_ip) and address == ipaddress.ip_address(public_ip)
        except (TypeError, ValueError):
            return False
