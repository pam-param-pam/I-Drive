from functools import wraps


def no_gzip(view_func):
    """Prevent GZipMiddleware from compressing a streaming response."""
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        request.META["HTTP_ACCEPT_ENCODING"] = "identity"
        return view_func(request, *args, **kwargs)
    return wrapped_view


def disable_common_errors(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        setattr(wrapper, "disable_common_errors", True)
        return view_func(*args, **kwargs)
    return wrapper
