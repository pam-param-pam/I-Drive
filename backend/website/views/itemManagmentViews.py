from django.http import HttpResponse, JsonResponse
from rest_framework.decorators import permission_classes, api_view, throttle_classes
from rest_framework.permissions import IsAuthenticated

from ..auth.Permissions import CreatePerms, ModifyPerms, default_checks, CheckRoot, CheckTrash, DeletePerms, LockPerms, ResetLockPerms, CheckFolderLock
from ..auth.throttle import defaultAuthUserThrottle, FolderPasswordThrottle
from ..core.Serializers import FolderSerializer, MomentSerializer, SubtitleSerializer, TagSerializer
from ..core.decorators import extract_folder, check_resource_permissions, extract_items_from_ids_annotated, check_bulk_permissions, extract_item, extract_file, \
    accumulate_password_errors
from ..core.errors import BadRequestError
from ..core.helpers import extract_key
from ..core.http.utils import build_response
from ..models import File, Folder
from ..services import folder_service, item_service, file_service, delete_service


@api_view(['POST'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & CreatePerms])
@extract_folder(source="data", key="parent_id", inject_as="parent")
@check_resource_permissions(default_checks, resource_key="parent")
def create_folder_view(request, parent):
    name = extract_key(request.data, "name")
    folder_obj = folder_service.create_folder(request.context, request.user, parent, name)
    folder_dict = FolderSerializer().serialize_object(folder_obj)
    return JsonResponse(folder_dict, status=200)


@api_view(['PATCH'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ModifyPerms])
@extract_folder(source="data", key="new_parent_id", inject_as="new_parent_obj")
@extract_items_from_ids_annotated(file_values=File.MINIMAL_VALUES, file_annotate=File.LOCK_FROM_ANNOTATE)
@accumulate_password_errors(
    check_resource_permissions(default_checks, resource_key="new_parent_obj"),
    check_bulk_permissions(default_checks & CheckRoot)
)
def move_items_view(request, new_parent_obj, items):
    """This view uses values instead of ORM objects for files"""
    item_service.move_items(request.context, items, new_parent_obj)
    return JsonResponse(build_response(request.context.request_id, "Moving items..."))


@api_view(['PATCH'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ModifyPerms])
@extract_items_from_ids_annotated(file_values=File.STANDARD_VALUES, file_annotate=File.LOCK_FROM_ANNOTATE)
@check_bulk_permissions((default_checks & CheckRoot) - CheckTrash)
def move_items_to_trash_view(request, items):
    """This view uses values instead of ORM objects for files"""
    item_service.move_items_to_trash(request.context, items)
    return JsonResponse(build_response(request.context.request_id, "Moving to Trash..."))


@api_view(['PATCH'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ModifyPerms])
@extract_items_from_ids_annotated(file_values=File.STANDARD_VALUES, file_annotate=File.LOCK_FROM_ANNOTATE)
@check_bulk_permissions((default_checks & CheckRoot) - CheckTrash)
def restore_from_trash(request, items):
    """This view uses values instead of ORM objects for files"""
    item_service.restore_items_from_trash(request.context, items)
    return JsonResponse(build_response(request.context.request_id, "Restoring from Trash..."))


@api_view(['POST'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & DeletePerms])
@extract_items_from_ids_annotated(file_values=File.STANDARD_VALUES, file_annotate=File.LOCK_FROM_ANNOTATE)
@check_bulk_permissions((default_checks & CheckRoot) - CheckTrash)
def delete(request, items):
    """This view uses values instead of ORM objects for files"""
    delete_service.delete_items(request.context, request.user, items)
    return JsonResponse(build_response(request.context.request_id, f"{len(items)} items are being deleted..."))


@api_view(['PATCH'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ModifyPerms])
@extract_item()
@check_resource_permissions(default_checks & CheckRoot, resource_key="item_obj")
def rename_view(request, item_obj):
    new_name = extract_key(request.data, "new_name")
    item_service.rename_item(request.context, item_obj, new_name)
    return HttpResponse(status=204)


@api_view(['POST'])
@throttle_classes([FolderPasswordThrottle])
@permission_classes([IsAuthenticated & ModifyPerms & LockPerms])
@extract_folder()
@check_resource_permissions(default_checks & CheckRoot, resource_key="folder_obj")
def change_folder_password_view(request, folder_obj):
    new_password = extract_key(request.data, "new_password")
    is_locked = folder_service.change_folder_password(request.context, folder_obj, new_password)
    if is_locked:
        return JsonResponse(build_response(request.context.request_id, "Folder is being locked..."))
    return JsonResponse(build_response(request.context.request_id, "Folder is being unlocked..."))


@api_view(['POST'])
@throttle_classes([FolderPasswordThrottle])
@permission_classes([IsAuthenticated & ModifyPerms & ResetLockPerms])
@extract_folder()
@check_resource_permissions((default_checks & CheckRoot) - CheckFolderLock, resource_key="folder_obj")
def reset_folder_password_view(request, folder_obj: Folder):
    account_password = extract_key(request.data, "accountPassword")
    new_folder_password = extract_key(request.data, "folderPassword")
    if not folder_obj.is_locked:
        raise BadRequestError("There is nothing to reset, folder is unlocked.")

    is_locked = folder_service.reset_folder_password(request.context, request.user, folder_obj, account_password, new_folder_password)
    if is_locked:
        return JsonResponse(build_response(request.context.request_id, "Folder password is being changed..."))
    return JsonResponse(build_response(request.context.request_id, "Folder is being unlocked..."))


@api_view(['PUT'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ModifyPerms])
@extract_file()
@check_resource_permissions(default_checks, resource_key="file_obj")
def update_media_position_view(request, file_obj):
    new_position = extract_key(request.data, "position")
    file_service.update_media_position(file_obj, new_position)
    return HttpResponse(status=204)


@api_view(['POST'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ModifyPerms])
@extract_file()
@check_resource_permissions(default_checks, resource_key="file_obj")
def add_tag_view(request, file_obj):
    tag_name = extract_key(request.data, "tag_name")
    tag = file_service.add_tag(file_obj, tag_name)
    return JsonResponse(TagSerializer().serialize_object(tag), status=200)


@api_view(['DELETE'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ModifyPerms])
@extract_file()
@check_resource_permissions(default_checks, resource_key="file_obj")
def remove_tag_view(request, file_obj, tag_id):
    file_service.remove_tag(file_obj, tag_id)
    return HttpResponse(status=204)


@api_view(['POST'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ModifyPerms])
@extract_file()
@check_resource_permissions(default_checks, resource_key="file_obj")
def add_moment_view(request, file_obj):
    moment = file_service.add_moment(request.user, file_obj, request.data)
    return JsonResponse(MomentSerializer().serialize_object(moment), status=200)


@api_view(['DELETE'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ModifyPerms])
@extract_file()
@check_resource_permissions(default_checks, resource_key="file_obj")
def remove_moment_view(request, file_obj, moment_id):
    file_service.remove_moment(request.user, file_obj, moment_id)
    return HttpResponse(status=204)


@api_view(['POST'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ModifyPerms])
@extract_file()
@check_resource_permissions(default_checks, resource_key="file_obj")
def add_subtitle_view(request, file_obj):
    subtitle = file_service.create_subtitle(file_obj, request.data)
    return JsonResponse(SubtitleSerializer().serialize_object(subtitle), status=200)


@api_view(['PATCH'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ModifyPerms])
@extract_file()
@check_resource_permissions(default_checks, resource_key="file_obj")
def rename_subtitle_view(request, file_obj, subtitle_id):
    new_language = extract_key(request.data, "new_language")
    file_service.rename_subtitle(file_obj, subtitle_id, new_language)
    return HttpResponse(status=204)


@api_view(['DELETE'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ModifyPerms])
@extract_file()
@check_resource_permissions(default_checks, resource_key="file_obj")
def remove_subtitle_view(request, file_obj, subtitle_id):
    file_service.remove_subtitle(request.user, file_obj, subtitle_id)
    return HttpResponse(status=204)
