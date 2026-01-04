from django.http import HttpResponse, JsonResponse
from rest_framework.decorators import permission_classes, api_view, throttle_classes
from rest_framework.permissions import IsAuthenticated

from ..auth.Permissions import CreatePerms, ModifyPerms, default_checks, CheckRoot, CheckTrash, DeletePerms, LockPerms, ResetLockPerms
from ..auth.throttle import defaultAuthUserThrottle, FolderPasswordThrottle
from ..core.Serializers import FolderSerializer, MomentSerializer, SubtitleSerializer, TagSerializer
from ..core.decorators import extract_folder, check_resource_permissions, extract_items_from_ids_annotated, check_bulk_permissions, extract_item, extract_file, \
    accumulate_password_errors
from ..core.errors import BadRequestError
from ..core.helpers import get_attr
from ..core.http.utils import build_response
from ..models import File
from ..queries.selectors import check_if_bots_exists
from ..services import folder_service, item_service, file_service
from ..tasks.deleteTasks import smart_delete_task
from ..tasks.moveTasks import move_task
from ..tasks.trashTasks import restore_from_trash_task, move_to_trash_task


@api_view(['POST'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & CreatePerms])
@extract_folder(source="data", key="parent_id", inject_as="parent")
@check_resource_permissions(default_checks, resource_key="parent")
def create_folder_view(request, parent):
    name = request.data['name']
    folder_obj = folder_service.create_folder(request, request.user, parent, name)
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
def move(request, new_parent_obj, items):
    # todo move to service layer
    """This view uses values instead of ORM objects for files"""
    new_parent_id = new_parent_obj.id

    for item in items:
        item_id = get_attr(item, 'id')
        parent_id = get_attr(item, 'parent_id')
        if item_id == new_parent_id or parent_id == new_parent_id:
            raise BadRequestError("errors.invalidMove")

    ids = request.data['ids']
    move_task.delay(request.context, ids, new_parent_id)

    return JsonResponse(build_response(request.context.request_id, "Moving items..."))


@api_view(['PATCH'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ModifyPerms])
@extract_items_from_ids_annotated(file_values=File.STANDARD_VALUES, file_annotate=File.LOCK_FROM_ANNOTATE)
@check_bulk_permissions((default_checks & CheckRoot) - CheckTrash)
def move_to_trash(request, items):
    """This view uses values instead of ORM objects for files"""
    # todo move to service layer

    for item in items:
        if get_attr(item, 'inTrash'):
            raise BadRequestError("Cannot move to Trash. At least one item is already in Trash.")

    ids = [get_attr(item, 'id') for item in items]

    move_to_trash_task.delay(request.context, ids)

    return JsonResponse(build_response(request.context.request_id, "Moving to Trash..."))


@api_view(['PATCH'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ModifyPerms])
@extract_items_from_ids_annotated(file_values=File.STANDARD_VALUES, file_annotate=File.LOCK_FROM_ANNOTATE)
@check_bulk_permissions((default_checks & CheckRoot) - CheckTrash)
def restore_from_trash(request, items):
    """This view uses values instead of ORM objects for files"""
    # todo move to service layer

    for item in items:
        if not get_attr(item, 'inTrash'):
            raise BadRequestError("Cannot restore from Trash. At least one item is not in Trash.")

    ids = [get_attr(item, 'id') for item in items]
    restore_from_trash_task.delay(request.context, ids)

    return JsonResponse(build_response(request.context.request_id, "Restoring from Trash..."))


@api_view(['POST'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & DeletePerms])
@extract_items_from_ids_annotated(file_values=File.STANDARD_VALUES, file_annotate=File.LOCK_FROM_ANNOTATE)
@check_bulk_permissions((default_checks & CheckRoot) - CheckTrash)
def delete(request, items):
    """This view uses values instead of ORM objects for files"""
    # todo move to service layer

    check_if_bots_exists(request.user)

    for item in items:
        if not get_attr(item, 'ready'):
            raise BadRequestError("Cannot delete. At least one item is not ready.")

    ids = [get_attr(item, 'id') for item in items]
    smart_delete_task.delay(request.context, ids)

    return JsonResponse(build_response(request.context.request_id, f"{len(items)} items are being deleted..."))


@api_view(['PATCH'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ModifyPerms])
@extract_item()
@check_resource_permissions(default_checks & CheckRoot, resource_key="item_obj")
def rename_view(request, item_obj):
    new_name = request.data["new_name"]
    item_service.rename_item(request, item_obj, new_name)
    return HttpResponse(status=204)


@api_view(['POST'])
@throttle_classes([FolderPasswordThrottle])
@permission_classes([IsAuthenticated & ModifyPerms & LockPerms])
@extract_folder()
@check_resource_permissions(default_checks & CheckRoot, resource_key="folder_obj")
def change_folder_password_view(request, folder_obj):
    new_password = request.data['new_password']
    is_locked = folder_service.change_folder_password(request, folder_obj, new_password)
    if is_locked:
        return JsonResponse(build_response(request.context.request_id, "Folder is being locked..."))
    return JsonResponse(build_response(request.context.request_id, "Folder is being unlocked..."))


@api_view(['POST'])
@throttle_classes([FolderPasswordThrottle])
@permission_classes([IsAuthenticated & ModifyPerms & ResetLockPerms])
@extract_folder()
@check_resource_permissions(default_checks & CheckRoot, resource_key="folder_obj")
def reset_folder_password_view(request, folder_obj):
    account_password = request.data['accountPassword']
    new_folder_password = request.data['folderPassword']
    is_locked = folder_service.reset_folder_password(request, folder_obj, account_password, new_folder_password)
    if is_locked:
        return JsonResponse(build_response(request.context.request_id, "Folder password is being changed..."))
    return JsonResponse(build_response(request.context.request_id, "Folder is being unlocked..."))


@api_view(['PUT'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ModifyPerms])
@extract_file()
@check_resource_permissions(default_checks, resource_key="file_obj")
def update_video_position_view(request, file_obj):
    new_position = request.data['position']
    file_service.update_video_position(file_obj, new_position)
    return HttpResponse(status=204)


@api_view(['POST'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ModifyPerms])
@extract_file()
@check_resource_permissions(default_checks, resource_key="file_obj")
def add_tag_view(request, file_obj):
    tag_name = request.data['tag_name']
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


@api_view(['PATCH'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ModifyPerms])
@extract_file()
@check_resource_permissions(default_checks, resource_key="file_obj")
def change_file_crc_view(request, file_obj):
    crc = request.data['crc']
    file_service.change_file_crc(file_obj, crc)
    return HttpResponse(status=204)


@api_view(['PATCH'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ModifyPerms])
def change_fragment_crc_view(request, fragment_id):
    crc = request.data['crc']
    file_service.change_fragment_crc(request.user, fragment_id, crc)
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
    new_language = request.data['new_language']
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
