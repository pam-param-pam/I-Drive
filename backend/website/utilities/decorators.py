from functools import wraps

from django.core.exceptions import ValidationError
from django.http import JsonResponse
from httpx import ConnectError
from requests.exceptions import SSLError
from rest_framework.exceptions import Throttled

from ..models import File, Folder, ShareableLink, Thumbnail, UserZIP, Preview
from ..utilities.errors import ResourceNotFoundError, ResourcePermissionError, BadRequestError, \
    RootPermissionError, DiscordError, DiscordBlockError, MissingOrIncorrectResourcePasswordError, CannotProcessDiscordRequestError
from ..utilities.other import build_http_error_response, verify_signed_file_id, check_resource_perms, get_file, get_folder


def check_signed_url(view_func):
    @wraps(view_func)
    def wrapper(request, file_id, *args, **kwargs):

        file_id = verify_signed_file_id(file_id)

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
        except Folder.DoesNotExist:
            return JsonResponse(build_http_error_response(code=404, error="errors.resourceNotFound", details="Folder not found"),
                                status=404)
        except File.DoesNotExist:
            return JsonResponse(build_http_error_response(code=404, error="errors.resourceNotFound", details="File not found"),
                                status=404)
        except ShareableLink.DoesNotExist:
            return JsonResponse(build_http_error_response(code=404, error="errors.resourceNotFound", details="Share with provided token not found"),
                                status=404)
        except Thumbnail.DoesNotExist:
            return JsonResponse(build_http_error_response(code=404, error="errors.resourceNotFound", details="Thumbnail doesn't exist"),
                                status=404)
        except Preview.DoesNotExist:
            return JsonResponse(build_http_error_response(code=404, error="errors.resourceNotFound", details="Preview doesn't exist"),
                                status=404)
        except UserZIP.DoesNotExist:
            return JsonResponse(build_http_error_response(code=404, error="errors.resourceNotFound", details="Zip doesn't exist"), status=404)

        except ResourceNotFoundError as e:
            return JsonResponse(build_http_error_response(code=404, error="errors.resourceNotFound", details=str(e)), status=404)


        # 400 BAD REQUEST
        except (ValidationError, BadRequestError) as e:
            return JsonResponse(build_http_error_response(code=400, error="errors.badRequest", details=str(e)), status=400)

        except DiscordError as e:
            return JsonResponse(build_http_error_response(code=400, error="errors.unexpectedDiscordResponse", details=str(e)), status=400)

        except DiscordBlockError as e:
            return JsonResponse(build_http_error_response(code=400, error="errors.discordBlocked", details=str(e)), status=400)

        except NotImplementedError as e:
            return JsonResponse(build_http_error_response(code=400, error="error.notImplemented", details=str(e)), status=400)

        except KeyError:
            return JsonResponse(build_http_error_response(code=400, error="errors.badRequest", details="Missing some required parameters"), status=400)

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

        except MissingOrIncorrectResourcePasswordError as e:
            json_error = build_http_error_response(code=469, error="errors.missingOrIncorrectResourcePassword", details=str(e))
            list_of_dicts = []
            for folder in e.requiredPasswords:
                list_of_dicts.append({"id": folder.id, "name": folder.name})
            json_error["requiredFolderPasswords"] = list_of_dicts

            return JsonResponse(json_error, status=469)

        # 500 SERVER ERROR
        except (ConnectError, SSLError) as e:
            return JsonResponse(build_http_error_response(code=500, error="errors.internal", details=str(e)), status=500)

        # 503 Service Unavailable
        except CannotProcessDiscordRequestError as e:
            return JsonResponse(build_http_error_response(code=503, error="errors.serviceUnavailable", details=str(e)), status=503)

    return wrapper
