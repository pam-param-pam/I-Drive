import os
import traceback
from typing import Any

import httpx
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import OperationalError, IntegrityError, ProgrammingError
from django.http import JsonResponse
from httpx import ConnectError
from mptt.exceptions import InvalidMove
from requests.exceptions import SSLError
from rest_framework.exceptions import PermissionDenied, ValidationError, APIException
from rest_framework.exceptions import Throttled
from rest_framework.views import exception_handler

from .utils import build_http_error_response
from ..errors import IDriveException, BadRequestError, NoBotsError, LockedFolderWrongIpError, ResourcePermissionError, RootPermissionError, ResourceNotFoundError, \
    MissingOrIncorrectResourcePasswordError, MalformedDatabaseRecord, CannotProcessDiscordRequestError, FailedToResizeImageError, DiscordBlockError, DiscordTextError, DiscordError, \
    UsernameTakenError
from ..helpers import format_wait_time
from ..helpers import get_attr
from ...models import ShareableLink

is_dev_env = os.getenv('IS_DEV_ENV', 'False') == 'True'
def custom_exception_handler(exception, context):
    if not isinstance(exception, (IDriveException, APIException)):
        traceback.print_exc()

    view = context.get('view')
    if view and getattr(view, 'disable_common_errors', False):
        return exception_handler(exception, context)

    # Call REST framework's default exception handler first,
    # to get the standard error response.
    response = exception_handler(exception, context)
    if isinstance(exception, Throttled):
        custom_response_data: Any = build_http_error_response(error='errors.rateLimitExceeded', code=429, details=f'Enhance your calm, try again in {format_wait_time(exception.wait)}')
        custom_response_data['retry_after'] = f'{exception.wait} seconds'
        return JsonResponse(custom_response_data, status=429)

    elif isinstance(exception, ValidationError):
        details = (response.data.get('non_field_errors') or [response.data])[0]
        return JsonResponse(build_http_error_response(error='errors.validationFailed', code=400, details=details), status=400)

    elif isinstance(exception, PermissionDenied):
        return JsonResponse(build_http_error_response(error='errors.permissionDenied', code=403, details=exception.detail), status=403)

    #  400 BAD REQUEST
    elif isinstance(exception, ValidationError):
        return JsonResponse(build_http_error_response(code=400, error="errors.badRequest", details=str(exception.message)), status=400)

    elif isinstance(exception, BadRequestError):
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

    # 404 NOT FOUND
    elif isinstance(exception, ObjectDoesNotExist):
        return JsonResponse(build_http_error_response(code=404, error="errors.resourceNotFound", details=""), status=404)

    elif isinstance(exception, ShareableLink.DoesNotExist):
        return JsonResponse(build_http_error_response(code=404, error="errors.resourceNotFound", details="Share not found or expired"), status=404)

    elif isinstance(exception, ResourceNotFoundError):
        return JsonResponse(build_http_error_response(code=404, error="errors.resourceNotFound", details=str(exception)), status=404)

    elif isinstance(exception, UsernameTakenError):
        return JsonResponse(build_http_error_response(code=409, error="errors.usernameTakenError", details=""), status=409)

    # 429 RATE LIMIT
    elif isinstance(exception, Throttled):
        return JsonResponse(build_http_error_response(code=429, error="errors.rateLimit", details=str(exception)), status=429)

    # 469 INVALID RESOURCE PASSWORD
    elif isinstance(exception, MissingOrIncorrectResourcePasswordError):
        json_error: Any = build_http_error_response(code=469, error="errors.missingOrIncorrectResourcePassword", details=str(exception))
        list_of_dicts = []
        for folder in exception.requiredPasswords:
            list_of_dicts.append({"id": get_attr(folder, "id"), "name": get_attr(folder, "name")})
        json_error["requiredFolderPasswords"] = list_of_dicts
        return JsonResponse(json_error, status=469)

    # 500 INTERNAL SERVER ERROR
    elif isinstance(exception, IntegrityError):
        return JsonResponse(build_http_error_response(code=500, error="errors.integrityError", details=str(exception)), status=500)

    elif isinstance(exception, (ConnectError, SSLError, MalformedDatabaseRecord, FailedToResizeImageError)):
        return JsonResponse(build_http_error_response(code=500, error="errors.internal", details=str(exception)), status=500)

    elif isinstance(exception, ProgrammingError):
        return JsonResponse(build_http_error_response(code=500, error="errors.internal", details="Database schema error"), status=500)

    # 503 SERVICE UNAVAILABLE
    elif isinstance(exception, CannotProcessDiscordRequestError):
        return JsonResponse(build_http_error_response(code=503, error="errors.serviceUnavailable", details=str(exception)), status=503)

    elif isinstance(exception, DiscordBlockError):
        res: Any = build_http_error_response(code=503, error="errors.discordBlocked", details=str(exception))
        res['retry_after'] = exception.retry_after
        return JsonResponse(res, status=503)

    elif isinstance(exception, httpx.ConnectError):
        return JsonResponse(build_http_error_response(code=503, error="errors.serviceUnavailable", details=str(exception)), status=503)

    elif isinstance(exception, OperationalError):
        return JsonResponse(build_http_error_response(code=503, error="errors.databaseError", details=str(exception)), status=503)

    # OTHER
    elif isinstance(exception, (DiscordTextError, DiscordError)):
        return JsonResponse(build_http_error_response(code=exception.status, error="errors.unexpectedDiscordResponse", details=exception.message), status=exception.status)

    elif not isinstance(exception, APIException):
        if is_dev_env:
            traceback.print_exc()
        return JsonResponse(build_http_error_response(code=500, error="errors.internal", details=str(exception)), status=500)

    return exception
