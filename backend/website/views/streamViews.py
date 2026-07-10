from django.views.decorators.cache import cache_page
from rest_framework.decorators import api_view, throttle_classes, permission_classes
from rest_framework.permissions import AllowAny

from website.auth.Permissions import CheckIPForLockedResources, CheckTrash, CheckState
from website.auth.throttle import MediaThrottle, NonCacheMediaThrottle
from website.core.decorators import check_resource_permissions, extract_file_from_signed_url, no_gzip
from website.core.errors import ResourceNotFoundError
from website.models import File, Subtitle, Moment, UserZIP
from website.services import media_service

@api_view(['GET'])
@throttle_classes([MediaThrottle])
@permission_classes([AllowAny])
@extract_file_from_signed_url
@check_resource_permissions([CheckIPForLockedResources, CheckState], resource_key="file_obj")
def serve_thumbnail(request, file_obj: File, thumbnail_id):
    return media_service.get_thumbnail_response(request, file_obj)


@api_view(['GET'])
@throttle_classes([MediaThrottle])
@permission_classes([AllowAny])
@extract_file_from_signed_url
@check_resource_permissions([CheckIPForLockedResources, CheckTrash, CheckState], resource_key="file_obj")
def serve_subtitle(request, file_obj: File, subtitle_id):
    subtitle = Subtitle.objects.get(file=file_obj, id=subtitle_id)
    return media_service.get_subtitle_response(request, file_obj, subtitle)


@api_view(['GET'])
@throttle_classes([MediaThrottle])
@permission_classes([AllowAny])
@extract_file_from_signed_url
@check_resource_permissions([CheckIPForLockedResources, CheckTrash, CheckState], resource_key="file_obj")
def serve_moment(request, file_obj: File, moment_id):
    moment = Moment.objects.get(file=file_obj, id=moment_id)
    return media_service.get_moment_response(request, file_obj, moment)


@api_view(['GET'])
@no_gzip
@throttle_classes([NonCacheMediaThrottle])
@permission_classes([AllowAny])
@extract_file_from_signed_url
@check_resource_permissions([CheckIPForLockedResources, CheckState], resource_key="file_obj")
def stream_file(request, file_obj: File):
    zip_mode = request.GET.get("zip_mode", False)
    if zip_mode:
        return media_service.get_zip_entry_response(request, file_obj)
    return media_service.get_file_response(request, file_obj)


@api_view(['GET'])
@no_gzip
@throttle_classes([NonCacheMediaThrottle])
@permission_classes([AllowAny])
def stream_zip_files(request, token):
    user_zip = UserZIP.objects.get(token=token)
    if user_zip.is_expired():
        user_zip.delete()
        raise ResourceNotFoundError()

    response = media_service.get_zip_response(request, user_zip)
    return response
