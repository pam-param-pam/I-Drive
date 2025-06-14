import os
import traceback
from functools import wraps

import httpx
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from httpx import ConnectError
from mptt.exceptions import InvalidMove
from requests.exceptions import SSLError
from rest_framework.exceptions import Throttled

from ..models import File, Folder, ShareableLink, Thumbnail, UserZIP, Preview, Moment, VideoMetadata, Tag, Subtitle
from ..utilities.errors import ResourceNotFoundError, ResourcePermissionError, BadRequestError, \
    RootPermissionError, DiscordError, DiscordBlockError, MissingOrIncorrectResourcePasswordError, CannotProcessDiscordRequestError, MalformedDatabaseRecord, NoBotsError
from ..utilities.other import build_http_error_response, verify_signed_resource_id, check_resource_perms, get_file, get_folder, get_attr

is_dev_env = os.getenv('IS_DEV_ENV', 'False') == 'True'

def no_gzip(view_func):
    """Decorator to prevent GZipMiddleware from compressing the response."""
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        request.META["HTTP_ACCEPT_ENCODING"] = "identity"
        response = view_func(request, *args, **kwargs)
        return response
    return wrapped_view


def check_signed_url(view_func):
    @wraps(view_func)
    def wrapper(request, signed_file_id, *args, **kwargs):

        file_id = verify_signed_resource_id(signed_file_id)

        return view_func(request, file_id, *args, **kwargs)

    return wrapper


def check_file_and_permissions(view_func):
    @wraps(view_func)
    def wrapper(request, file_id, *args, **kwargs):

        file_obj = get_file(file_id)
        check_resource_perms(request, file_obj, checkRoot=False)

        return view_func(request, file_obj, *args, **kwargs)

    return wrapper

# goofy ah code duplication
def check_file(view_func):
    @wraps(view_func)
    def wrapper(request, file_id, *args, **kwargs):

        file_obj = get_file(file_id)
        check_resource_perms(request, file_obj, checkOwnership=False, checkRoot=False, checkFolderLock=False)

        if file_obj.inTrash and file_obj.is_locked:
            raise ResourcePermissionError("Cannot access resource in trash!")

        return view_func(request, file_obj, *args, **kwargs)

    return wrapper


def check_folder_and_permissions(view_func):
    @wraps(view_func)
    def wrapper(request, folder_id, *args, **kwargs):

        folder_obj = get_folder(folder_id)

        check_resource_perms(request, folder_obj, checkRoot=False)

        return view_func(request, folder_obj, *args, **kwargs)

    return wrapper


def handle_common_errors(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):

        try:
            return view_func(request, *args, **kwargs)

        # 404 NOT FOUND
        except (Moment.DoesNotExist, UserZIP.DoesNotExist, Preview.DoesNotExist, Thumbnail.DoesNotExist, File.DoesNotExist, Folder.DoesNotExist, VideoMetadata.DoesNotExist, Tag.DoesNotExist, Subtitle.DoesNotExist):
            return JsonResponse(build_http_error_response(code=404, error="errors.resourceNotFound", details=""),
                                status=404)
        except ShareableLink.DoesNotExist:
            return JsonResponse(build_http_error_response(code=404, error="errors.resourceNotFound", details="Share not found or expired"),
                                status=404)
        except ResourceNotFoundError as e:
            return JsonResponse(build_http_error_response(code=404, error="errors.resourceNotFound", details=str(e)), status=404)

        # 400 BAD REQUEST
        except (ValidationError, BadRequestError) as e:
            return JsonResponse(build_http_error_response(code=400, error="errors.badRequest", details=str(e)), status=400)

        except NoBotsError:
            return JsonResponse(build_http_error_response(code=400, error="error.badRequest", details="User has no bots, unable to fetch anything from discord."), status=400)

        except NotImplementedError as e:
            return JsonResponse(build_http_error_response(code=400, error="error.notImplemented", details=str(e)), status=400)

        except InvalidMove:
            return JsonResponse(build_http_error_response(code=400, error="error.badRequest", details="Invalid parent, recursion detected."), status=400)

        except KeyError:
            if is_dev_env:
                traceback.print_exc()
            return JsonResponse(build_http_error_response(code=400, error="errors.badRequest", details="Missing some required parameters"), status=400)

        except (ValueError, TypeError):
            if is_dev_env:
                traceback.print_exc()
            return JsonResponse(build_http_error_response(code=400, error="errors.badRequest", details="Bad parameters"), status=400)

        except OverflowError:
            return JsonResponse(build_http_error_response(code=400, error="errors.badRequest", details="Params are too big"), status=400)

        # 403 REQUEST FORBIDDEN
        except ResourcePermissionError as e:
            return JsonResponse(build_http_error_response(code=403, error="errors.resourceAccessForbidden", details=str(e)), status=403)
        except RootPermissionError:
            return JsonResponse(build_http_error_response(code=403, error="errors.rootFolderNoAccess", details="Access to root folder denied"), status=403)

        # 429 RATE LIMIT
        except Throttled as e:
            return JsonResponse(build_http_error_response(code=403, error="errors.rateLimit", details=str(e)), status=403)

        # 469 WRONG FOLDER PASSWORD
        except MissingOrIncorrectResourcePasswordError as e:
            json_error = build_http_error_response(code=469, error="errors.missingOrIncorrectResourcePassword", details=str(e))
            list_of_dicts = []
            for folder in e.requiredPasswords:
                list_of_dicts.append({"id": get_attr(folder, "id"), "name": get_attr(folder, "name")})
            json_error["requiredFolderPasswords"] = list_of_dicts

            return JsonResponse(json_error, status=469)

        # 500 SERVER ERROR
        except (ConnectError, SSLError, MalformedDatabaseRecord) as e:
            return JsonResponse(build_http_error_response(code=500, error="errors.internal", details=str(e)), status=500)

        # 503 Service Unavailable
        except CannotProcessDiscordRequestError as e:
            return JsonResponse(build_http_error_response(code=503, error="errors.serviceUnavailable", details=str(e)), status=503)

        except DiscordBlockError as e:
            res = build_http_error_response(code=503, error="errors.discordBlocked", details=str(e))
            res['retry_after'] = e.retry_after
            return JsonResponse(res, status=503)

        except httpx.ConnectError as e:
            return JsonResponse(build_http_error_response(code=503, error="errors.serviceUnavailable", details=str(e)), status=503)

        # DYNAMIC STATUS CODE
        except DiscordError as e:
            return JsonResponse(build_http_error_response(code=e.status, error="errors.unexpectedDiscordResponse", details=e.message), status=e.status)

    return wrapper
