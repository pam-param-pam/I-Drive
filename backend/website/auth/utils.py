from django.conf import settings


def _trusted_client_ip(request) -> str:
    if settings.BEHIND_NGINX:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            return forwarded.split(",", 1)[0].strip()
    return request.META.get("REMOTE_ADDR", "")