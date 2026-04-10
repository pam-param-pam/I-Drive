from django.views.decorators.cache import cache_page
from rest_framework.decorators import api_view, throttle_classes, permission_classes
from rest_framework.permissions import AllowAny

from ..auth.Permissions import CheckLockedFolderIP
from ..auth.throttle import MediaThrottle, defaultAuthUserThrottle
from ..core.decorators import extract_file_from_signed_url, no_gzip, check_resource_permissions, extract_file
from ..models import File, Moment, Subtitle
from ..services.media_service import get_thumbnail_response, get_moment_response, get_subtitle_response, get_file_response, get_zip_response, get_zip_entry_response


@api_view(['GET'])
@throttle_classes([MediaThrottle])
@permission_classes([AllowAny])
@extract_file_from_signed_url
@check_resource_permissions([CheckLockedFolderIP], resource_key="file_obj")
def serve_thumbnail(request, file_obj: File):
    return get_thumbnail_response(request, file_obj)


@api_view(['GET'])
@throttle_classes([MediaThrottle])
@permission_classes([AllowAny])
@extract_file_from_signed_url
@check_resource_permissions([CheckLockedFolderIP], resource_key="file_obj")
def serve_subtitle(request, file_obj: File, subtitle_id):
    subtitle = Subtitle.objects.get(file=file_obj, id=subtitle_id)
    return get_subtitle_response(request, file_obj, subtitle)


@api_view(['GET'])
@throttle_classes([MediaThrottle])
@permission_classes([AllowAny])
@cache_page(60 * 60 * 24 * 30)
@extract_file_from_signed_url
@check_resource_permissions([CheckLockedFolderIP], resource_key="file_obj")
def serve_moment(request, file_obj: File, moment_id):
    moment = Moment.objects.get(file=file_obj, id=moment_id)
    return get_moment_response(request, file_obj, moment)


@api_view(['GET'])
@no_gzip
@throttle_classes([MediaThrottle])
@permission_classes([AllowAny])
@extract_file_from_signed_url
@check_resource_permissions([CheckLockedFolderIP], resource_key="file_obj")
def stream_file(request, file_obj: File):
    return get_file_response(request, file_obj)


@api_view(['GET'])
@no_gzip
@throttle_classes([MediaThrottle])
@permission_classes([AllowAny])
def stream_zip_files(request, token):
    return get_zip_response(request, token)

@api_view(['GET'])
@no_gzip
@throttle_classes([MediaThrottle])
@permission_classes([AllowAny])
@extract_file_from_signed_url
@check_resource_permissions([CheckLockedFolderIP], resource_key="file_obj")
def stream_zip_entry(request, file_obj: File):
    return get_zip_entry_response(request, file_obj)
