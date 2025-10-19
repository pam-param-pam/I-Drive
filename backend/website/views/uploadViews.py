import base64
from datetime import datetime

from django.contrib.contenttypes.models import ContentType
from django.db.utils import IntegrityError
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from rest_framework.decorators import api_view, throttle_classes, permission_classes
from rest_framework.permissions import IsAuthenticated

from ..models import File, Fragment, Thumbnail
from ..utilities.Permissions import CreatePerms, default_checks, ModifyPerms
from ..utilities.Serializers import FileSerializer
from ..utilities.constants import MAX_DISCORD_MESSAGE_SIZE, EventCode, EncryptionMethod
from ..utilities.decorators import extract_file, check_resource_permissions, disable_common_errors
from ..utilities.errors import BadRequestError
from ..utilities.other import send_event, check_resource_perms, get_folder, check_if_bots_exists, get_discord_author, delete_single_discord_attachment, \
    create_video_metadata, validate_ids_as_list, group_and_send_event, get_file_type
from ..utilities.throttle import defaultAuthUserThrottle


@api_view(['POST'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & CreatePerms])
@disable_common_errors
def create_file(request):
    # raise KeyError("aaa")
    # return HttpResponse(status=503)
    check_if_bots_exists(request.user)

    files = request.data['files']
    validate_ids_as_list(files, max_length=25)

    response_json = []
    file_objs = []

    for file in files:
        file_name = file['name']
        parent_id = file['parent_id']
        extension = file['extension']
        mimetype = file['mimetype']
        file_size = file['size']
        frontend_id = file['frontend_id']
        encryption_method = file['encryption_method']
        crc = file['crc']
        attachments = file['attachments']

        thumbnail = file.get('thumbnail')
        duration = file.get('duration')
        created_at = file.get('created_at')
        key = file.get('key')
        iv = file.get('iv')
        video_metadata = file.get('videoMetadata')

        if EncryptionMethod(encryption_method) != EncryptionMethod.Not_Encrypted and (not iv or not key):
            raise BadRequestError("Encryption key and/or iv not provided")

        if iv:
            iv = base64.b64decode(iv)
        if key:
            key = base64.b64decode(key)

        if not mimetype:
            raise BadRequestError("'mimetype' cannot be empty")

        if not file_name:
            raise BadRequestError("'name' cannot be empty")

        file_type = get_file_type(extension)

        parent = get_folder(parent_id)
        check_resource_perms(request, parent, default_checks)

        if File.objects.filter(frontend_id=frontend_id).exists():
            continue

        if created_at:
            try:
                timestamp_in_seconds = int(created_at) / 1000
                created_at = timezone.make_aware(datetime.fromtimestamp(timestamp_in_seconds))
            except (ValueError, OverflowError):
                raise BadRequestError("Invalid 'created_at' timestamp format.")

        file_obj = File(
            extension=extension,
            name=file_name,
            size=file_size,
            mimetype=mimetype,
            type=file_type,
            owner_id=request.user.id,
            parent=parent,
            key=key,
            iv=iv,
            frontend_id=frontend_id,
            encryption_method=encryption_method,
            created_at=created_at,
            crc=crc,
            ready=True
        )

        if duration:
            file_obj.duration = duration

        try:
            file_obj.save()
        except IntegrityError:
            raise BadRequestError("This file already exists!")

        for attachment in attachments:
            fragment_sequence = attachment['fragment_sequence']
            channel_id = attachment['channel_id']
            message_id = attachment['message_id']
            attachment_id = attachment['attachment_id']
            fragment_size = attachment['fragment_size']
            offset = attachment['offset']
            message_author_id = attachment['message_author_id']

            author = get_discord_author(request, message_author_id)

            Fragment.objects.create(
                sequence=fragment_sequence,
                file=file_obj,
                size=fragment_size,
                offset=offset,
                channel_id=channel_id,
                message_id=message_id,
                attachment_id=attachment_id,
                content_type=ContentType.objects.get_for_model(author),
                object_id=author.discord_id
            )

        if thumbnail:
            channel_id = thumbnail['channel_id']
            message_id = thumbnail['message_id']
            attachment_id = thumbnail['attachment_id']
            size = thumbnail['size']
            message_author_id = thumbnail['message_author_id']
            iv = thumbnail.get('iv')
            key = thumbnail.get('key')

            author = get_discord_author(request, message_author_id)

            if file_obj.is_encrypted() and not (iv and key):
                raise BadRequestError("Encryption key and/or iv not provided")

            if iv:
                iv = base64.b64decode(iv)
            if key:
                key = base64.b64decode(key)

            Thumbnail.objects.create(
                file=file_obj,
                size=size,
                iv=iv,
                key=key,
                channel_id=channel_id,
                message_id=message_id,
                attachment_id=attachment_id,
                content_type=ContentType.objects.get_for_model(author),
                object_id=author.discord_id,
            )
        if video_metadata:
            create_video_metadata(file_obj, video_metadata)

        file_response_dict = {"frontend_id": frontend_id, "file_id": file_obj.id, "parent_id": parent_id, "name": file_obj.name, "type": file_type, "encryption_method": file_obj.encryption_method}
        file_objs.append(file_obj)
        response_json.append(file_response_dict)

    if file_objs:
        group_and_send_event(request.user.id, request.request_id, EventCode.ITEM_CREATE, file_objs)

    return JsonResponse(response_json, safe=False, status=200)

@api_view(['PATCH'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ModifyPerms])
@extract_file()
@check_resource_permissions(default_checks, resource_key="file_obj")
def edit_file(request, file_obj):

    check_if_bots_exists(request.user)

    fragments = Fragment.objects.filter(file=file_obj)

    if file_obj.size > MAX_DISCORD_MESSAGE_SIZE:
        raise BadRequestError("You cannot edit a file larger than 10Mb!")

    if len(fragments) > 1:
        raise BadRequestError("Fragments > 1")

    isEmpty = request.data.get('empty')

    if not isEmpty:
        fragment_size = request.data['fragment_size']
        channel_id = request.data['channel_id']
        message_id = request.data['message_id']
        attachment_id = request.data['attachment_id']
        offset = request.data['offset']
        message_author_id = request.data['message_author_id']
        crc = request.data['crc']
        iv = request.data.get('iv')
        key = request.data.get('key')

        if iv:
            iv = base64.b64decode(iv)
        if key:
            key = base64.b64decode(key)

        author = get_discord_author(request, message_author_id)

        if file_obj.type not in ("Text", "Code"):
            raise BadRequestError("You can only edit text files!")

    if fragments.exists():
        fragment = fragments[0]
        delete_single_discord_attachment(request.user, fragment)
        fragment.delete()

    if not isEmpty:
        Fragment.objects.create(
            sequence=1,
            file=file_obj,
            size=fragment_size,
            offset=offset,
            channel_id=channel_id,
            message_id=message_id,
            attachment_id=attachment_id,
            content_type=ContentType.objects.get_for_model(author),
            object_id=author.discord_id
        )

        file_obj.key = key
        file_obj.iv = iv
        file_obj.size = fragment_size
        file_obj.crc = crc
    else:
        file_obj.crc = 0
        file_obj.size = 0
        file_obj.iv = None
        file_obj.key = None

    file_obj.save()
    send_event(file_obj.owner.id, request.request_id, file_obj.parent, EventCode.ITEM_UPDATE, FileSerializer().serialize_object(file_obj))

    return HttpResponse(status=204)

@api_view(['POST'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & CreatePerms])
@extract_file()
@check_resource_permissions(default_checks, resource_key="file_obj")
def create_thumbnail(request, file_obj):
    check_if_bots_exists(request.user)

    channel_id = request.data['channel_id']
    message_id = request.data['message_id']
    attachment_id = request.data['attachment_id']
    size = request.data['size']
    message_author_id = request.data['message_author_id']
    author = get_discord_author(request, message_author_id)

    iv = request.data.get('iv')
    key = request.data.get('key')

    if iv:
        iv = base64.b64decode(iv)
    if key:
        key = base64.b64decode(key)

    try:
        # todo sadly i dont remember what should i do here???
        delete_single_discord_attachment(request.user, file_obj.thumbnail)
        file_obj.thumbnail.delete()
    except Thumbnail.DoesNotExist:
        pass

    Thumbnail.objects.create(
        file=file_obj,
        size=size,
        key=key,
        iv=iv,
        channel_id=channel_id,
        message_id=message_id,
        attachment_id=attachment_id,
        content_type=ContentType.objects.get_for_model(author),
        object_id=author.discord_id
    )

    file_obj.remove_cache()

    file_dict = FileSerializer().serialize_object(file_obj)
    send_event(file_obj.owner.id, request.request_id, file_obj.parent, EventCode.ITEM_UPDATE, file_dict)

    return HttpResponse(status=204)
