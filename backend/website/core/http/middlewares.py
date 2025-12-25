import time

from django.utils.deprecation import MiddlewareMixin

from ...constants import cache


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
