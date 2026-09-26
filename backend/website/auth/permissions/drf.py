from rest_framework.permissions import BasePermission

from .network import ip_is_allowed
from .principals import _trusted_client_ip


class AllowedNetwork(BasePermission):
    message = "IP validation failed. Must be private or allowed."

    def has_permission(self, request, view):
        return ip_is_allowed(_trusted_client_ip(request))
