# per_device_auth/authentication.py
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication

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

        token_obj = PerDeviceToken.objects.get_token_from_raw_token(raw_token)
        if not token_obj:
            raise exceptions.AuthenticationFailed('Invalid token')

        if token_obj.user_agent != str(request.user_agent):
            raise exceptions.AuthenticationFailed('Invalid user agent')

        return token_obj.user, token_obj  # request.user, request.auth

    def authenticate_header(self, request):
        # So DRF knows what to send in WWW-Authenticate
        return 'Token'
