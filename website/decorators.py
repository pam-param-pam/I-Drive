import os
import shutil
import traceback

from django.http import HttpResponse


def cleanup(view_func):
    def _wrapped_view(request, *args, **kwargs):
        try:
            a = view_func(request, *args, **kwargs)
            return a
        except Exception as e:
            print(traceback.format_exc())
            return HttpResponse(status=500)
        finally:
            #shutil.rmtree(os.path.join("temp", request.request_id), ignore_errors=True)
            pass
    return _wrapped_view

