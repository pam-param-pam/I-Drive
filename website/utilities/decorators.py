from functools import wraps

from django.core.exceptions import ValidationError
from django.http import JsonResponse
from rest_framework.exceptions import Throttled

from website.models import File, Folder, ShareableLink, Thumbnail
from website.utilities.errors import ResourceNotFoundError, ResourcePermissionError, BadRequestError, \
    RootPermissionError, DiscordError, DiscordBlockError, ResourceNotPreviewableError, ThumbnailAlreadyExistsError, IncorrectResourcePasswordError, MissingResourcePasswordError
from website.utilities.other import error_res, verify_signed_file_id


def check_signed_url(view_func):
    @wraps(view_func)
    def wrapper(request, file_id, *args, **kwargs):
        try:
            file_id = verify_signed_file_id(file_id)
        except ResourcePermissionError as e:
            return JsonResponse(
                error_res(user=request.user, code=403, error_code=5, details=str(e)),
                status=403)
        return view_func(request, file_id, *args, **kwargs)

    return wrapper


def check_file_and_permissions(view_func):
    @wraps(view_func)
    def wrapper(request, file_id, *args, **kwargs):
        try:
            file_obj = File.objects.get(id=file_id)
            if file_obj.owner != request.user:
                return JsonResponse(
                    error_res(user=request.user, code=403, error_code=5, details="You do not own this resource."),
                    status=403)
            if not file_obj.ready:
                return JsonResponse(
                    error_res(user=request.user, code=404, error_code=7, details="File is not ready, perhaps it's still uploading, or being deleted."),
                    status=404)
            if file_obj.is_locked:
                password = request.headers.get("X-Folder-Password")
                if not password:
                    raise MissingResourcePasswordError(lockFrom=file_obj.lockFrom.id, resourceId=file_obj.id)
                if file_obj.password != password:
                    raise IncorrectResourcePasswordError()

        except (File.DoesNotExist, ValidationError):

            return JsonResponse(error_res(user=request.user, code=404, error_code=8,
                                          details=f"File with id of '{file_id}' doesn't exist."), status=404)

        return view_func(request, file_obj, *args, **kwargs)

    return wrapper

# goofy ah code duplication
def check_file(view_func):
    @wraps(view_func)
    def wrapper(request, file_id, *args, **kwargs):
        try:
            file_obj = File.objects.get(id=file_id)
            if not file_obj.ready:
                return JsonResponse(
                    error_res(user=request.user, code=404, error_code=7, details="File is not ready, perhaps it's still uploading, or being deleted."),
                    status=404)

        except (File.DoesNotExist, ValidationError):

            return JsonResponse(error_res(user=request.user, code=404, error_code=8,
                                          details=f"File with id of '{file_id}' doesn't exist."), status=404)

        return view_func(request, file_obj, *args, **kwargs)

    return wrapper


def check_folder_and_permissions(view_func):
    @wraps(view_func)
    def wrapper(request, folder_id, *args, **kwargs):
        try:

            folder_obj = Folder.objects.get(id=folder_id)

            if folder_obj.owner != request.user:
                return JsonResponse(
                    error_res(user=request.user, code=403, error_code=5, details="You do not own this resource."),
                    status=403)

            if folder_obj.is_locked:
                password = request.headers.get("X-Folder-Password")
                if not password:
                    raise MissingResourcePasswordError(lockFrom=folder_obj.lockFrom.id, resourceId=folder_obj.id)
                if folder_obj.password != password:
                    raise IncorrectResourcePasswordError()

        except (File.DoesNotExist, ValidationError):
            return JsonResponse(error_res(user=request.user, code=404, error_code=8,
                                          details=f"Folder with id of '{folder_id}' doesn't exist."), status=404)

        return view_func(request, folder_obj, *args, **kwargs)

    return wrapper


def handle_common_errors(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        try:
            return view_func(request, *args, **kwargs)

        # 404 NOT FOUND
        except Folder.DoesNotExist:
            return JsonResponse(error_res(user=request.user, code=404, error_code=8, details="Folder not found."),
                                status=404)
        except File.DoesNotExist:
            return JsonResponse(error_res(user=request.user, code=404, error_code=8, details="File not found."),
                                status=404)
        except ShareableLink.DoesNotExist:
            return JsonResponse(error_res(user=request.user, code=404, error_code=8, details="Share with provided token not found."),
                                status=404)
        except Thumbnail.DoesNotExist:
            return JsonResponse(error_res(user=request.user, code=404, error_code=8, details="Thumbnail doesn't exist."),
                                status=404)
        except ResourceNotFoundError as e:
            return JsonResponse(error_res(user=request.user, code=404, error_code=1, details=str(e)), status=404)

        # 400 BAD REQUEST
        except ValidationError as e:
            return JsonResponse(error_res(user=request.user, code=400, error_code=1, details=str(e)), status=400)
        except BadRequestError as e:
            return JsonResponse(error_res(user=request.user, code=400, error_code=1, details=str(e)), status=400)
        except DiscordError as e:
            return JsonResponse(error_res(user=request.user, code=400, error_code=13, details=str(e)), status=400)
        except DiscordBlockError as e:
            return JsonResponse(error_res(user=request.user, code=400, error_code=14, details=str(e)), status=400)
        except ResourceNotPreviewableError as e:
            return JsonResponse(error_res(user=request.user, code=400, error_code=11, details=str(e)), status=400)
        except ThumbnailAlreadyExistsError as e:
            return JsonResponse(error_res(user=request.user, code=400, error_code=18, details=str(e)), status=400)
        except NotImplementedError as e:
            return JsonResponse(error_res(user=request.user, code=400, error_code=15, details=str(e)), status=400)
        except KeyError:
            return JsonResponse(
                error_res(user=request.user, code=400, error_code=1, details="Missing some required parameters"),
                status=400)

        # 403 REQUEST FORBIDDEN
        except ResourcePermissionError as e:
            return JsonResponse(error_res(user=request.user, code=403, error_code=5, details=str(e)), status=403)
        except RootPermissionError as e:
            return JsonResponse(error_res(user=request.user, code=403, error_code=12, details=str(e)), status=403)

        # 429 RATE LIMIT
        except Throttled as e:
            return JsonResponse(error_res(user=request.user, code=403, error_code=5, details=str(e)), status=403)

        # 469 CUSTOM STATUS CODE - FOLDER PASSWORD MISSING OR INCORRECT
        except IncorrectResourcePasswordError as e:
            return JsonResponse(error_res(user=request.user, code=469, error_code=16, details=str(e)), status=469)

        except MissingResourcePasswordError as e:
            json_error = error_res(user=request.user, code=469, error_code=19, details=str(e))
            json_error["lockFrom"] = e.lockFrom
            json_error["resourceId"] = e.resourceId
            return JsonResponse(json_error, status=469)

    return wrapper
