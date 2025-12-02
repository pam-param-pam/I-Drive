import random

from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication

from ..core.dataModels.http import RequestContext
from ..models import PerDeviceToken


class PerDeviceTokenAuthentication(BaseAuthentication):

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

        request_id = random.randint(0, 100000)
        request.context = RequestContext(user_id=token_obj.user_id, device_id=token_obj.device_id, request_id=request_id)

        return token_obj.user, token_obj

    def authenticate_header(self, request):
        # So DRF knows what to send in WWW-Authenticate
        return 'Token'
