from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny

from website.auth.permissions import PrincipalFactory, extract_resource_credentials
from website.auth.throttle import MediaThrottle, NonCacheMediaThrottle
from website.core.decorators import no_gzip
from website.services import media_service
from website.services.metric_service import record_stream_response


def _signed_principal(request, file_id, share_id=None):
    return PrincipalFactory.from_signed_request(request, file_id, share_id)


@api_view(["GET"])
@throttle_classes([MediaThrottle])
@permission_classes([AllowAny])
def serve_thumbnail(request, file_id, thumbnail_id, share_id=None):
    response = media_service.get_thumbnail_response(request, _signed_principal(request, file_id, share_id), thumbnail_id)
    record_stream_response(response)
    return response


@api_view(["GET"])
@throttle_classes([MediaThrottle])
@permission_classes([AllowAny])
def serve_subtitle(request, file_id, subtitle_id, share_id=None):
    response = media_service.get_subtitle_response(request, _signed_principal(request, file_id, share_id), subtitle_id)
    record_stream_response(response)
    return response


@api_view(["GET"])
@throttle_classes([MediaThrottle])
@permission_classes([AllowAny])
def serve_moment(request, file_id, moment_id, share_id=None):
    response = media_service.get_moment_response(request, _signed_principal(request, file_id, share_id), moment_id)
    record_stream_response(response)
    return response


@api_view(["GET"])
@no_gzip
@throttle_classes([NonCacheMediaThrottle])
@permission_classes([AllowAny])
def stream_file(request, file_id, share_id=None):
    zip_mode = bool(request.GET.get("zip_mode", False))
    principal = _signed_principal(request, file_id, share_id)
    response = media_service.get_zip_entry_response(request, principal) if zip_mode else media_service.get_file_response(request, principal)
    record_stream_response(response)
    return response


@api_view(["GET"])
@no_gzip
@throttle_classes([NonCacheMediaThrottle])
@permission_classes([AllowAny])
def stream_zip_files(request, token, share_token=None):
    if share_token:
        principal = PrincipalFactory.from_share_request(request, share_token)
    else:
        principal = PrincipalFactory.from_authenticated_request(request)
    response = media_service.get_zip_response(request, principal, token, extract_resource_credentials(request))
    record_stream_response(response)
    return response
