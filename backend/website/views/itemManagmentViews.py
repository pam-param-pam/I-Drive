from django.http import HttpResponse, JsonResponse
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated

from website.auth.permissions import PrincipalFactory, ResourceAction, extract_resource_credentials
from website.auth.throttle import FolderPasswordThrottle, defaultAuthUserThrottle
from website.core.Serializers import MomentSerializer, SubtitleSerializer, TagSerializer, ZipSerializer
from website.core.helpers import extract_key
from website.core.http.utils import build_response
from website.services import namespace_service, zip_service
from website.services.file_service import FileService
from website.services.folder_service import FolderService
from website.services.resource_query_service import FileQueryService
from website.services.thumbnail_service import ThumbnailService


def _inputs(request):
    return PrincipalFactory.from_authenticated_request(request), extract_resource_credentials(request)


@api_view(["POST"])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated])
def create_folder_view(request):
    principal, credentials = _inputs(request)
    result = FolderService.create(principal, str(extract_key(request.data, "parent_id")), extract_key(request.data, "name"), credentials)
    return JsonResponse({"id": result.folder_id, "resource_version": result.resource_version}, status=200)


@api_view(["PATCH"])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated])
def move_items_view(request):
    principal, credentials = _inputs(request)
    namespace_service.move(principal, extract_key(request.data, "ids"), str(extract_key(request.data, "new_parent_id")), credentials)
    return JsonResponse(build_response(principal.request_id, "Moving items..."))


@api_view(["PATCH"])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated])
def move_items_to_trash_view(request):
    principal, credentials = _inputs(request)
    namespace_service.trash(principal, extract_key(request.data, "ids"), credentials)
    return JsonResponse(build_response(principal.request_id, "Moving to Trash..."))


@api_view(["PATCH"])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated])
def restore_from_trash_view(request):
    principal, credentials = _inputs(request)
    namespace_service.restore(principal, extract_key(request.data, "ids"), credentials)
    return JsonResponse(build_response(principal.request_id, "Restoring from Trash..."))


@api_view(["POST"])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated])
def delete_view(request):
    principal, credentials = _inputs(request)
    ids = extract_key(request.data, "ids")
    namespace_service.request_deletion(principal, ids, credentials)
    return JsonResponse(build_response(principal.request_id, f"{len(ids)} items are being deleted..."))


@api_view(["POST"])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated])
def create_zip_model_view(request):
    principal, credentials = _inputs(request)
    refs = namespace_service.classify_item_ids(extract_key(request.data, "ids"))
    user_zip = zip_service.create_zip_model(principal, [ref.as_dict() for ref in refs], credentials)
    return JsonResponse(ZipSerializer.serialize_object(user_zip), status=200)


@api_view(["PATCH"])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated])
def rename_view(request, item_id):
    principal, credentials = _inputs(request)
    namespace_service.rename(principal, item_id, extract_key(request.data, "new_name"), credentials)
    return HttpResponse(status=204)


@api_view(["POST"])
@throttle_classes([FolderPasswordThrottle])
@permission_classes([IsAuthenticated])
def change_folder_password_view(request, folder_id):
    principal, credentials = _inputs(request)
    new_password = extract_key(request.data, "new_password")
    if new_password:
        FolderService.apply_lock(principal, folder_id, new_password, credentials)
        message = "Folder is being locked..."
    else:
        FolderService.remove_lock(principal, folder_id, credentials)
        message = "Folder is being unlocked..."
    return JsonResponse(build_response(principal.request_id, message))


@api_view(["POST"])
@throttle_classes([FolderPasswordThrottle])
@permission_classes([IsAuthenticated])
def reset_folder_password_view(request, folder_id):
    principal, credentials = _inputs(request)
    new_password = extract_key(request.data, "folderPassword")
    FolderService.reset_lock(principal, folder_id, extract_key(request.data, "accountPassword"), new_password, credentials)
    message = "Folder password is being changed..." if new_password else "Folder is being unlocked..."
    return JsonResponse(build_response(principal.request_id, message))


@api_view(["PUT"])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated])
def update_media_position_view(request, file_id):
    principal, credentials = _inputs(request)
    FileService.update_media_position(principal, file_id, extract_key(request.data, "position"), credentials)
    return HttpResponse(status=204)


@api_view(["POST"])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated])
def add_tag_view(request, file_id):
    principal, credentials = _inputs(request)
    tag = FileService.add_tag(principal, file_id, extract_key(request.data, "tag_name"), credentials)
    return JsonResponse(TagSerializer.serialize_object(tag), status=200)


@api_view(["DELETE"])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated])
def remove_tag_view(request, file_id, tag_id):
    principal, credentials = _inputs(request)
    FileService.remove_tag(principal, file_id, tag_id, credentials)
    return HttpResponse(status=204)


@api_view(["POST"])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated])
def add_moment_view(request, file_id):
    principal, credentials = _inputs(request)
    FileQueryService.get(principal, file_id, ResourceAction.DOWNLOAD, credentials)
    moment = FileService.add_moment(principal, file_id, request.data, credentials)
    return JsonResponse(MomentSerializer.serialize_object(moment), status=200)


@api_view(["DELETE"])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated])
def remove_moment_view(request, file_id, moment_id):
    principal, credentials = _inputs(request)
    FileService.remove_moment(principal, file_id, moment_id, credentials)
    return HttpResponse(status=204)


@api_view(["POST"])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated])
def add_subtitle_view(request, file_id):
    principal, credentials = _inputs(request)
    FileQueryService.get(principal, file_id, ResourceAction.DOWNLOAD, credentials)
    subtitle = FileService.create_subtitle(principal, file_id, request.data, credentials)
    return JsonResponse(SubtitleSerializer.serialize_object(subtitle), status=200)


@api_view(["PATCH"])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated])
def rename_subtitle_view(request, file_id, subtitle_id):
    principal, credentials = _inputs(request)
    FileService.rename_subtitle(principal, file_id, subtitle_id, extract_key(request.data, "new_language"), credentials)
    return HttpResponse(status=204)


@api_view(["DELETE"])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated])
def delete_thumbnail_view(request, file_id):
    principal, credentials = _inputs(request)
    ThumbnailService.remove(principal, file_id, must_exist=True, credentials=credentials)
    return HttpResponse(status=204)


@api_view(["DELETE"])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated])
def remove_subtitle_view(request, file_id, subtitle_id):
    principal, credentials = _inputs(request)
    FileService.remove_subtitle(principal, file_id, subtitle_id, credentials)
    return HttpResponse(status=204)
