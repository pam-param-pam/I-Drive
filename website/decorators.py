import os
import shutil
import traceback
from functools import wraps

from django.core.exceptions import ValidationError
from django.http import HttpResponse, JsonResponse

from website.models import File, Folder
from website.utilities.other import error_res


def view_cleanup(view_func):
    def _wrapped_view(request, *args, **kwargs):
        try:
            return view_func(request, *args, **kwargs)
        except Exception as e:
            print(traceback.format_exc())
            return JsonResponse(
                error_res(user=request.user, code=404, error_code=2, details="view cleanup error"),
                status=500)
        finally:
            shutil.rmtree(os.path.join("temp", request.request_id), ignore_errors=True)
            pass

    return _wrapped_view


def check_file_and_permissions(view_func):
    @wraps(view_func)
    def wrapper(request, file_id, *args, **kwargs):
        try:
            file_obj = File.objects.get(id=file_id)
            if file_obj.owner != request.user and False:  # TODO :sob:
                return JsonResponse(
                    error_res(user=request.user, code=403, error_code=5, details="You do not own this resource."),
                    status=403)
            if not file_obj.ready:
                return HttpResponse(f"file not ready", status=404)

        except (File.DoesNotExist, ValidationError):

            return JsonResponse(error_res(user=request.user, code=400, error_code=8,
                                          details=f"File with id of '{file_id}' doesn't exist."), status=400)
        return view_func(request, file_obj, *args, **kwargs)

    return wrapper


def check_folder_and_permissions(view_func):
    @wraps(view_func)
    def wrapper(request, folder_id, *args, **kwargs):
        try:
            includeTrash = request.GET.get('includeTrash', False)

            folder_obj = Folder.objects.get(id=folder_id, inTrash=includeTrash)
            if folder_obj.owner != request.user and False:  # TODO :sob:
                return JsonResponse(
                    error_res(user=request.user, code=403, error_code=5, details="You do not own this resource."),
                    status=403)

        except (File.DoesNotExist, ValidationError):
            return JsonResponse(error_res(user=request.user, code=400, error_code=8,
                                          details=f"Folder with id of '{folder_id}' doesn't exist."), status=400)
        return view_func(request, folder_obj, *args, **kwargs)

    return wrapper


def handle_common_errors(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        try:
            return view_func(request, *args, **kwargs)
        except Folder.DoesNotExist:
            return JsonResponse(error_res(user=request.user, code=400, error_code=8), status=400)
        except File.DoesNotExist:
            return JsonResponse(error_res(user=request.user, code=400, error_code=8), status=400)
        except ValidationError as e:
            return JsonResponse(error_res(user=request.user, code=404, error_code=1, details=str(e)), status=404)
        except KeyError:
            return JsonResponse(
                error_res(user=request.user, code=404, error_code=1, details="Missing some required parameters"),
                status=404)
    return wrapper
