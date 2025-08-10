# per_device_auth/authentication.py
import hashlib
import hmac
from rest_framework.authentication import BaseAuthentication
from rest_framework import exceptions

from ..models import PerDeviceToken


class PerDeviceTokenAuthentication(BaseAuthentication):
    """
    DRF authentication class for per-device tokens.
    Looks for `Authorization: Token <token>` or `Bearer <token>`.
    """

    keyword_token = 'token'
    keyword_bearer = 'bearer'

    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header:
            return None

        parts = auth_header.split()
        if len(parts) != 2:
            return None

        method, raw_token = parts[0].lower(), parts[1]
        if method not in (self.keyword_token, self.keyword_bearer):
            return None

        token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
        try:
            token_obj = PerDeviceToken.objects.select_related('user').get(token_hash=token_hash)
        except PerDeviceToken.DoesNotExist:
            raise exceptions.AuthenticationFailed('Invalid token')

        if token_obj.is_expired():
            raise exceptions.AuthenticationFailed('Token expired')

        # constant-time check just in case
        if not hmac.compare_digest(token_obj.token_hash, token_hash):
            raise exceptions.AuthenticationFailed('Invalid token')

        token_obj.mark_used()

        return token_obj.user, token_obj  # request.user, request.auth

    def authenticate_header(self, request):
        # So DRF knows what to send in WWW-Authenticate
        return 'Token'
