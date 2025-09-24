import hashlib
import os
import random
import time
import traceback

import httpx
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import OperationalError
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from httpx import ConnectError
from mptt.exceptions import InvalidMove
from requests.exceptions import SSLError
from rest_framework.exceptions import Throttled

from ..models import ShareableLink, PerDeviceToken
from ..utilities.constants import cache
from ..utilities.errors import ResourceNotFoundError, ResourcePermissionError, BadRequestError, \
    RootPermissionError, DiscordError, DiscordBlockError, MissingOrIncorrectResourcePasswordError, CannotProcessDiscordRequestError, MalformedDatabaseRecord, NoBotsError, \
    FailedToResizeImage, LockedFolderWrongIpError
from ..utilities.other import build_http_error_response, get_attr

is_dev_env = os.getenv('IS_DEV_ENV', 'False') == 'True'


@database_sync_to_async
def get_user(raw_token):
    if not raw_token:
        return AnonymousUser()

    token = PerDeviceToken.objects.get_token_from_raw_token(raw_token=raw_token)
    if not token:
        return AnonymousUser()
    return token.user


class TokenAuthMiddleware(BaseMiddleware):
    def __init__(self, inner):
        super().__init__(inner)

    async def __call__(self, scope, receive, send):
        headers = dict(scope['headers'])
        token_key = None
        is_standard_protocol = False

        # Try authorization header first
        auth_header = headers.get(b'authorization')
        if auth_header:
            try:
                auth_str = auth_header.decode('utf-8')
                if auth_str.lower().startswith('bearer '):
                    token_key = auth_str[7:]
                    is_standard_protocol = True
            except (KeyError, ValueError):
                pass

        # Fallback to sec-websocket-protocol header
        if token_key is None:
            try:
                token_key = headers[b'sec-websocket-protocol'].decode('utf-8')
                is_standard_protocol = False
            except (KeyError, ValueError):
                token_key = None

        scope['user'] = AnonymousUser() if token_key is None else await get_user(token_key)
        scope['token'] = token_key
        scope['is_standard_protocol'] = is_standard_protocol

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


class FailedRequestLoggerMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if response.status_code >= 400:
            key = self._get_key(request)
            data = cache.get(key, [])
            data.append(time.time())
            data = [t for t in data if time.time() - t < 60]  # tylko z ostatniej minuty
            cache.set(key, data, timeout=60)
        return response

    def _get_key(self, request):
        if request.user.is_authenticated:
            return f"fail:{request.user.pk}"
        return f"fail_ip:{self._get_ip(request)}"

    def _get_ip(self, request):
        return request.META.get('REMOTE_ADDR')


class CommonErrorsMiddleware(MiddlewareMixin):
    def process_view(self, request, view_func, view_args, view_kwargs):
        request._view_func = view_func
        return None

    def process_exception(self, request, exception):
        # Check if error handling is disabled for this view
        if getattr(request._view_func, 'disable_common_errors', False):
            return None

        #  400 BAD REQUEST
        if isinstance(exception, (ValidationError, BadRequestError)):
            return JsonResponse(build_http_error_response(code=400, error="errors.badRequest", details=str(exception)), status=400)

        elif isinstance(exception, NoBotsError):
            return JsonResponse(build_http_error_response(code=400, error="errors.badRequest", details="User has no bots, unable to fetch anything from discord."), status=400)

        elif isinstance(exception, NotImplementedError):
            return JsonResponse(build_http_error_response(code=400, error="errors.notImplemented", details=str(exception)), status=400)

        elif isinstance(exception, InvalidMove):
            return JsonResponse(build_http_error_response(code=400, error="errors.badRequest", details="Invalid parent, recursion detected."), status=400)

        elif isinstance(exception, KeyError):
            if is_dev_env:
                traceback.print_exc()
            return JsonResponse(build_http_error_response(code=400, error="errors.badRequest", details="Missing some required parameters"), status=400)

        elif isinstance(exception, (ValueError, TypeError)):
            if is_dev_env:
                traceback.print_exc()
            return JsonResponse(build_http_error_response(code=400, error="errors.badRequest", details="Bad parameters"), status=400)

        elif isinstance(exception, OverflowError):
            return JsonResponse(build_http_error_response(code=400, error="errors.badRequest", details="Params are too big"), status=400)

        #  403 FORBIDDEN
        elif isinstance(exception, LockedFolderWrongIpError):
            return JsonResponse(build_http_error_response(code=403, error="errors.resourceInaccessibleFromIP", details=f"This resource cannot be accessed from this IP({exception.ip})"), status=403)

        elif isinstance(exception, ResourcePermissionError):
            return JsonResponse(build_http_error_response(code=403, error="errors.resourceAccessForbidden", details=str(exception)), status=403)

        elif isinstance(exception, RootPermissionError):
            return JsonResponse(build_http_error_response(code=403, error="errors.rootFolderNoAccess", details="You cannot perform this action on a 'root' folder"), status=403)

        # 404 BAD REQUEST
        elif isinstance(exception, ObjectDoesNotExist):
            return JsonResponse(build_http_error_response(code=404, error="errors.resourceNotFound", details=""), status=404)

        elif isinstance(exception, ShareableLink.DoesNotExist):
            return JsonResponse(build_http_error_response(code=404, error="errors.resourceNotFound", details="Share not found or expired"), status=404)

        elif isinstance(exception, ResourceNotFoundError):
            return JsonResponse(build_http_error_response(code=404, error="errors.resourceNotFound", details=str(exception)), status=404)

        # 429 RATE LIMIT
        elif isinstance(exception, Throttled):
            return JsonResponse(build_http_error_response(code=429, error="errors.rateLimit", details=str(exception)), status=429)

        # 469 INVALID RESOURCE PASSWORD
        elif isinstance(exception, MissingOrIncorrectResourcePasswordError):
            json_error = build_http_error_response(code=469, error="errors.missingOrIncorrectResourcePassword", details=str(exception))
            list_of_dicts = []
            for folder in exception.requiredPasswords:
                list_of_dicts.append({"id": get_attr(folder, "id"), "name": get_attr(folder, "name")})
            json_error["requiredFolderPasswords"] = list_of_dicts
            return JsonResponse(json_error, status=469)

        # 500 INTERNAL SERVER ERROR
        elif isinstance(exception, (ConnectError, SSLError, MalformedDatabaseRecord, FailedToResizeImage)):
            return JsonResponse(build_http_error_response(code=500, error="errors.internal", details=str(exception)), status=500)

        # 503 SERVICE UNAVAILABLE
        elif isinstance(exception, CannotProcessDiscordRequestError):
            return JsonResponse(build_http_error_response(code=503, error="errors.serviceUnavailable", details=str(exception)), status=503)

        elif isinstance(exception, DiscordBlockError):
            res = build_http_error_response(code=503, error="errors.discordBlocked", details=str(exception))
            res['retry_after'] = exception.retry_after
            return JsonResponse(res, status=503)

        elif isinstance(exception, httpx.ConnectError):
            return JsonResponse(build_http_error_response(code=503, error="errors.serviceUnavailable", details=str(exception)), status=503)

        elif isinstance(exception, OperationalError):
            return JsonResponse(build_http_error_response(code=503, error="errors.databaseError", details=str(exception)), status=503)

        # OTHER
        elif isinstance(exception, DiscordError):
            return JsonResponse(build_http_error_response(code=exception.status, error="errors.unexpectedDiscordResponse", details=exception.message), status=exception.status)

        else:
            if is_dev_env:
                traceback.print_exc()
            return JsonResponse(build_http_error_response(code=500, error="errors.internal", details=str(exception)), status=500)

