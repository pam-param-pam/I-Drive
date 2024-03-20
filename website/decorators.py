import os
import shutil
import traceback

from django.http import HttpResponse, JsonResponse

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

def check_args(view_func):
    def _wrapped_view(request,  *args, **kwargs):
        #file_id = kwargs.pop("file_id")
        print(str(kwargs))
        return view_func(request, *args, **kwargs)
    return _wrapped_view



