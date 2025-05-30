import base64
import time
from datetime import datetime

from django.contrib.contenttypes.models import ContentType
from django.db.utils import IntegrityError
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from rest_framework.decorators import api_view, throttle_classes, permission_classes
from rest_framework.permissions import IsAuthenticated

from ..models import File, Fragment, Thumbnail
from ..utilities.Discord import discord
from ..utilities.Permissions import CreatePerms
from ..utilities.constants import MAX_DISCORD_MESSAGE_SIZE, EventCode, EncryptionMethod
from ..utilities.decorators import handle_common_errors
from ..utilities.errors import BadRequestError
from ..utilities.other import send_event, create_file_dict, check_resource_perms, get_folder, get_file, check_if_bots_exists, get_discord_author, delete_single_discord_attachment, \
    create_video_metadata, validate_ids_as_list, group_and_send_event
from ..utilities.throttle import defaultAuthUserThrottle, ProxyRateThrottle


@api_view(['POST', 'PATCH', 'PUT'])
@permission_classes([IsAuthenticated & CreatePerms])
@throttle_classes([defaultAuthUserThrottle])
@handle_common_errors
def create_file(request):
    check_if_bots_exists(request.user)
    # return HttpResponse(status=500)
    if request.method == "POST":
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

            file_type = mimetype.split("/")[0]

            parent = get_folder(parent_id)
            check_resource_perms(request, parent, checkRoot=False, checkTrash=True)

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
                    message_id=message_id,
                    attachment_id=attachment_id,
                    content_type=ContentType.objects.get_for_model(author),
                    object_id=author.discord_id
                )

            if thumbnail:
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

    if request.method == "PUT":
        file_id = request.data['file_id']
        fragment_size = request.data['fragment_size']
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

        file_obj = get_file(file_id)
        check_resource_perms(request, file_obj)

        if file_obj.type != "text":
            raise BadRequestError("You can only edit text files!")

        fragments = Fragment.objects.filter(file=file_obj)

        if file_obj.size > MAX_DISCORD_MESSAGE_SIZE:
            raise BadRequestError("You cannot edit a file larger than 10Mb!")
        if len(fragments) > 1:
            raise BadRequestError("Fragments > 1")

        fragment = fragments[0]
        delete_single_discord_attachment(request.user, fragment)
        fragment.delete()

        Fragment.objects.create(
            sequence=1,
            file=file_obj,
            size=fragment_size,
            offset=offset,
            message_id=message_id,
            attachment_id=attachment_id,
            content_type=ContentType.objects.get_for_model(author),
            object_id=author.discord_id
        )

        file_obj.key = key
        file_obj.iv = iv
        file_obj.size = fragment_size
        file_obj.last_modified_at = timezone.now()
        file_obj.crc = crc
        file_obj.save()
        send_event(file_obj.owner.id, request.request_id, file_obj.parent, EventCode.ITEM_UPDATE, create_file_dict(file_obj))

        return HttpResponse(status=204)


@api_view(['POST'])
@permission_classes([IsAuthenticated & CreatePerms])
@throttle_classes([defaultAuthUserThrottle])
@handle_common_errors
def create_thumbnail(request):
    file_id = request.data['file_id']
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

    file_obj = get_file(file_id)
    check_resource_perms(request, file_obj)
    try:
        delete_single_discord_attachment(request.user, file_obj.thumbnail)
        file_obj.thumbnail.delete()
    except Thumbnail.DoesNotExist:
        pass

    Thumbnail.objects.create(
        file=file_obj,
        size=size,
        key=key,
        iv=iv,
        message_id=message_id,
        attachment_id=attachment_id,
        content_type=ContentType.objects.get_for_model(author),
        object_id=author.discord_id
    )

    file_obj.remove_cache()

    file_dict = create_file_dict(file_obj)
    send_event(file_obj.owner.id, request.request_id, file_obj.parent, EventCode.ITEM_UPDATE, file_dict)

    return HttpResponse(status=204)

@api_view(["POST"])
@permission_classes([IsAuthenticated & CreatePerms])
@throttle_classes([ProxyRateThrottle])
@handle_common_errors
def proxy_discord(request):
    check_if_bots_exists(request.user)

    # todo secure to prevent denial of service
    json_payload = request.data.get("json_payload")
    # return HttpResponse(status=429)
    files = request.FILES
    start_time = time.time()
    message = discord.send_file(request.user, json=json_payload, files=files)
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"Time taken to send the file: {elapsed_time:.4f} seconds")
    return JsonResponse(message, status=200, safe=False)
