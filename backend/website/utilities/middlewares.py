import random

from django.contrib.auth.models import AnonymousUser
from rest_framework.authtoken.models import Token
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware


@database_sync_to_async
def get_user(token_key):
    try:
        token = Token.objects.get(key=token_key)
        return token.user
    except Token.DoesNotExist:
        return AnonymousUser()


class TokenAuthMiddleware(BaseMiddleware):
    def __init__(self, inner):
        super().__init__(inner)

    async def __call__(self, scope, receive, send):
        try:
            token_key = dict(scope['headers'])[b'sec-websocket-protocol'].decode('utf-8')
        except (ValueError, KeyError):
            token_key = None
        scope['user'] = AnonymousUser() if token_key is None else await get_user(token_key)
        scope['token'] = token_key
        return await super().__call__(scope, receive, send)

class ApplyRateLimitHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        response = self.get_response(request)

        if "rate_limit_remaining" in request.META:
            remaining = request.META["rate_limit_remaining"]
            response["X-RateLimit-Remaining"] = remaining

        if "rate_limit_reset_after" in request.META:
            reset_after = request.META["rate_limit_reset_after"]
            response["X-RateLimit-Reset-After"] = reset_after

        if "rate_limit_bucket" in request.META:
            bucket = request.META["rate_limit_bucket"]
            response["X-RateLimit-Bucket"] = bucket

        return response

class RequestIdMiddleware:
    def __init__(self, get_response=None):
        self.get_response = get_response

    def __call__(self, request):
        request_id = str(random.randint(0, 100000))
        request.request_id = request_id

        response = self.get_response(request)
        return response


