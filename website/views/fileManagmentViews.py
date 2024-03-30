import time
from datetime import datetime, timedelta

from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponse, JsonResponse
from rest_framework.decorators import permission_classes, api_view, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle

from website.models import File, Folder, Fragment, UserSettings
from website.models import ShareableLink
from website.utilities.Discord import discord
from website.utilities.common.error import ResourceNotFound, ResourcePermissionError, BadRequestError, \
    RootPermissionError
from website.utilities.decorators import handle_common_errors
from website.utilities.other import build_response, create_folder_dict
from website.utilities.other import create_share_dict

DELAY_TIME = 0


@api_view(['POST'])
@throttle_classes([UserRateThrottle])
# @permission_classes([IsAuthenticated])
@handle_common_errors
def delete_share(request):
    time.sleep(DELAY_TIME)
    token = request.data['token']

    share = ShareableLink.objects.get(token=token)

    if share.owner != request.user:
        raise ResourcePermissionError("You do not own this resource.")
    share.delete()
    return HttpResponse(f"Share deleted!", status=204)


@api_view(['POST'])
# @permission_classes([IsAuthenticated])
@throttle_classes([UserRateThrottle])
@handle_common_errors
def create_share(request):
    time.sleep(DELAY_TIME)

    item_id = request.data['resource_id']
    value = abs(int(request.data['value']))

    unit = request.data['unit']
    password = request.data.get('password')

    current_time = datetime.now()
    try:
        obj = Folder.objects.get(id=item_id)
    except Folder.DoesNotExist:
        try:
            obj = File.objects.get(id=item_id)
        except File.DoesNotExist:
            raise ResourceNotFound(f"Resource with id of '{item_id}' doesn't exist.")

    if obj.owner != request.user:
        raise ResourcePermissionError("You do not own this resource.")

    if unit == 'minutes':
        expiration_time = current_time + timedelta(minutes=value)
    elif unit == 'hours':
        expiration_time = current_time + timedelta(hours=value)
    elif unit == 'days':
        expiration_time = current_time + timedelta(days=value)
    else:
        raise BadRequestError("Invalid unit. Supported units are 'minutes', 'hours', and 'days'.")

    share = ShareableLink.objects.create(
        expiration_time=expiration_time,
        owner_id=1,
        content_type=ContentType.objects.get_for_model(obj),
        object_id=obj.id
    )
    if password:
        share.password = password

    share.save()
    item = create_share_dict(share)

    return JsonResponse(item, status=200, safe=False)


@api_view(['POST'])
@throttle_classes([UserRateThrottle])
@permission_classes([IsAuthenticated])
@handle_common_errors
def create_folder(request):
    time.sleep(DELAY_TIME)
    name = request.data['name']

    parent = Folder.objects.get(id=request.data['parent_id'])

    folder_obj = Folder(
        name=name,
        parent=parent,
        owner=request.user,
    )
    folder_obj.save()
    return JsonResponse(create_folder_dict(folder_obj))


@api_view(['POST'])
@throttle_classes([UserRateThrottle])
# @permission_classes([IsAuthenticated])
@handle_common_errors
def move(request):
    time.sleep(DELAY_TIME)

    print(request.data)

    ids = request.data['ids']
    user = request.user
    items = []
    new_parent_id = request.data['new_parent_id']
    new_parent = Folder.objects.get(id=new_parent_id)

    if not isinstance(ids, list):
        raise BadRequestError("'ids' must be a list.")

    for item_id in ids:

        try:
            item = Folder.objects.get(id=item_id)
        except Folder.DoesNotExist:
            try:
                item = File.objects.get(id=item_id)
            except File.DoesNotExist:
                raise ResourceNotFound(f"Resource with id of '{item_id}' doesn't exist.")

        # if item.owner != user:  # owner perms needed
        #    raise ResourcePermissionError(f"You do not own this resource!")
        if isinstance(item, Folder) and not item.parent:
            raise RootPermissionError("Cannot move 'root' folder!")

        if item == new_parent:
            raise BadRequestError("'item' and 'new_parent_id' cannot be the same!")

        if item.parent == new_parent:
            raise BadRequestError("'new_parent_id' and 'old_parent_id' cannot be the same!")
        x = 0
        while new_parent.parent:  # cannot move item to its descendant
            x += 1
            if new_parent.parent == item.parent and x > 1:
                raise BadRequestError("I beg you not.")
            new_parent = Folder.objects.get(id=new_parent.parent.id)

        items.append(item)

    new_parent = Folder.objects.get(id=new_parent_id)  # goofy ah redeclaration

    for item in items:
        item.parent = new_parent
        item.save()

    return HttpResponse(f"Items moved", status=200)


@api_view(['POST'])  # this should be a post or delete imo
@throttle_classes([UserRateThrottle])
@permission_classes([IsAuthenticated])
@handle_common_errors
def move_to_trash(request):
    time.sleep(DELAY_TIME)
    user = request.user
    items = []
    ids = request.data['ids']

    if not isinstance(ids, list):
        raise BadRequestError("'ids' must be a list.")

    for item_id in ids:
        try:
            item = Folder.objects.get(id=item_id)
        except Folder.DoesNotExist:
            try:
                item = File.objects.get(id=item_id)
            except File.DoesNotExist:
                raise ResourceNotFound(f"Resource with id of '{item_id}' doesn't exist.")

        if item.owner != user:  # owner perms needed
            raise ResourcePermissionError(f"You do not own this resource!")

        if isinstance(item, Folder) and not item.parent:
            raise RootPermissionError("Cannot move 'root' folder to trash!")

        items.append(item)

    for item in items:
        if isinstance(item, File):
            item.moveToTrash()
        elif isinstance(item, Folder):
            item.moveToTrash()

    return JsonResponse(build_response(request.request_id, f"Moved to trash."), status=200)


@api_view(['POST'])  # this should be a post or delete imo
@throttle_classes([UserRateThrottle])
@permission_classes([IsAuthenticated])
@handle_common_errors
def delete(request):
    time.sleep(DELAY_TIME)

    user = request.user
    items = []
    ids = request.data['ids']
    if not isinstance(ids, list):
        raise BadRequestError("'ids' must be a list.")

    for item_id in ids:
        try:
            item = Folder.objects.get(id=item_id)
        except Folder.DoesNotExist:
            try:
                item = File.objects.get(id=item_id)
            except File.DoesNotExist:
                raise ResourceNotFound(f"Resource with id of '{item_id}' doesn't exist.")

        if isinstance(item, Folder) and not item.parent:
            raise RootPermissionError("Cannot delete 'root' folder!")

        if item.owner != user:  # owner perms needed
            raise ResourcePermissionError(f"You do not own this resource!")

        items.append(item)

    message_structure = {}
    all_files = []
    for item in items:
        if isinstance(item, File):
            all_files.append(item)

        elif isinstance(item, Folder):
            files = item.get_all_files()
            all_files += files

    for file in all_files:
        fragments = Fragment.objects.filter(file=file)
        for fragment in fragments:
            key = fragment.message_id
            value = fragment.attachment_id

            # If the key exists, append the value to its list
            if fragment.message_id in message_structure:
                message_structure[key].append(value)
            # If the key doesn't exist, create a new key with a list containing the value
            else:
                message_structure[key] = [value]
    settings = UserSettings.objects.get(user=user)
    webhook = settings.discord_webhook
    for key in message_structure.keys():
        fragments = Fragment.objects.filter(message_id=key)
        if len(fragments) == 1:
            discord.remove_message(key)
        else:
            attachment_ids = []
            for fragment in fragments:
                attachment_ids.append(fragment.attachment_id)

            all_attachment_ids = set(attachment_ids)
            attachment_ids_to_remove = set(message_structure[key])

            # Get the difference
            attachment_ids_to_keep = list(all_attachment_ids - attachment_ids_to_remove)
            if len(attachment_ids_to_keep) > 0:
                discord.edit_attachments(webhook, key, attachment_ids_to_keep)
            else:
                discord.remove_message(key)

    for item in items:
        item.delete()

    return HttpResponse(status=200)


@api_view(['POST'])  # this should be a post or delete imo
@throttle_classes([UserRateThrottle])
@permission_classes([IsAuthenticated])
@handle_common_errors
def rename(request):
    time.sleep(DELAY_TIME)

    obj_id = request.data['id']
    new_name = request.data['new_name']

    try:
        obj = Folder.objects.get(id=obj_id)
    except Folder.DoesNotExist:
        try:
            obj = File.objects.get(id=obj_id)
        except File.DoesNotExist:
            raise ResourceNotFound(f"Resource with id of '{obj_id}' doesn't exist.")

    if obj.owner != request.user:  # todo fix perms
        raise ResourcePermissionError(f"You do not own this resource!")

    if isinstance(obj, Folder) and not obj.parent:
        raise RootPermissionError("Cannot rename 'root' folder!")

    obj.name = new_name
    obj.save()

    return HttpResponse(f"Changed name to {new_name}", status=200)
