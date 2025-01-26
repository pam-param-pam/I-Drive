import base64
import math
from datetime import datetime

from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from rest_framework.decorators import api_view, throttle_classes, permission_classes
from rest_framework.permissions import IsAuthenticated

from ..models import File, Fragment, Thumbnail
from ..utilities.Discord import discord
from ..utilities.Permissions import CreatePerms
from ..utilities.constants import MAX_DISCORD_MESSAGE_SIZE, cache, EventCode, EncryptionMethod
from ..utilities.decorators import handle_common_errors
from ..utilities.errors import BadRequestError
from ..utilities.other import send_event, create_file_dict, check_resource_perms, get_folder, get_file, get_webhook, check_if_bots_exists
from ..utilities.throttle import MyUserRateThrottle


@api_view(['POST', 'PATCH', 'PUT'])
@throttle_classes([MyUserRateThrottle])
@permission_classes([IsAuthenticated & CreatePerms])
@handle_common_errors
def create_file(request):

    if request.method == "POST":
        files = request.data['files']
        if not isinstance(files, list):
            raise BadRequestError("'files' must be a list.")

        if len(files) > 100:
            raise BadRequestError("'files' cannot be larger than 100")

        if len(files) == 0:
            raise BadRequestError("'files' length cannot be 0.")

        response_json = []

        for file in files:
            file_name = file['name']
            parent_id = file['parent_id']
            extension = file['extension']
            mimetype = file['mimetype']
            file_size = file['size']
            frontend_id = file['frontend_id']
            encryption_method = file['encryption_method']

            duration = file.get('duration')
            created_at = file.get('created_at')

            _ = EncryptionMethod(encryption_method)  # validate encryption_method if its wrong it will raise KeyError which will be caught

            if mimetype == "":
                mimetype = "text/plain"

            if file_name == "" or not file_name:
                raise BadRequestError("'name' cannot be empty")

            parent = get_folder(parent_id)

            check_resource_perms(request, parent, checkRoot=False, checkTrash=True)

            file_type = mimetype.split("/")[0]

            file_obj = File(
                extension=extension,
                name=file_name,
                size=file_size,
                mimetype=mimetype,
                type=file_type,
                owner_id=request.user.id,
                parent=parent,
                encryption_method=encryption_method,
            )

            if created_at:
                try:
                    timestamp_in_seconds = int(created_at) / 1000
                    created_at = timezone.make_aware(datetime.fromtimestamp(timestamp_in_seconds))
                    file_obj.created_at = created_at
                except (ValueError, OverflowError):
                    raise BadRequestError("Invalid 'created_at' timestamp format.")
            #  apply lock if needed
            if parent.is_locked:
                file_obj.applyLock(parent.lockFrom, parent.password)

            if file_size == 0:
                file_obj.ready = True
            if duration:
                file_obj.duration = duration

            file_obj.save()

            file_response_dict = {"frontend_id": frontend_id, "file_id": file_obj.id, "parent_id": parent_id, "name": file_obj.name,
                                  "type": file_type, "encryption_method": file_obj.encryption_method}

            if file_obj.is_encrypted():
                file_response_dict['key'] = file_obj.get_base64_key()
                file_response_dict['iv'] = file_obj.get_base64_iv()

            response_json.append(file_response_dict)

        return JsonResponse(response_json, safe=False, status=200)

    if request.method == "PATCH":
        files = request.data['files']
        if not isinstance(files, list):
            raise BadRequestError("'ids' must be a list.")

        if len(files) > 100:
            raise BadRequestError("'ids' cannot be larger than 100")

        if len(files) == 0:
            raise BadRequestError("'ids' length cannot be 0.")

        response_json = []
        for file in files:

            file_id = file['file_id']
            fragment_sequence = file['fragment_sequence']
            message_id = file['message_id']
            attachment_id = file['attachment_id']
            fragment_size = file['fragment_size']
            frontend_id = file['frontend_id']
            webhook_id = file['webhook']

            webhook = get_webhook(request, webhook_id)

            file_obj = get_file(file_id)
            check_resource_perms(request, file_obj, checkReady=False)

            fragment_obj = Fragment(
                sequence=fragment_sequence,
                file=file_obj,
                size=fragment_size,
                attachment_id=attachment_id,
                message_id=message_id,
                webhook=webhook,

            )
            fragment_obj.save()
            file_response_dict = {"frontend_id": frontend_id, "file_id": file_obj.id, 'ready': False}
            total_fragments = math.ceil(file_obj.size / MAX_DISCORD_MESSAGE_SIZE)
            if len(file_obj.fragments.all()) == total_fragments:
                file_obj.ready = True
                file_obj.save()

                send_event(request.user.id, EventCode.ITEM_CREATE, request.request_id, [create_file_dict(file_obj)])

                file_response_dict['ready'] = True

            response_json.append(file_response_dict)
        return JsonResponse(response_json, safe=False, status=200)

    if request.method == "PUT":
        file_id = request.data['file_id']
        fragment_size = request.data['fragment_size']
        message_id = request.data['message_id']
        attachment_id = request.data['attachment_id']
        webhook_id = request.data['webhook']

        file_obj = get_file(file_id)
        check_resource_perms(request, file_obj, checkReady=False)
        check_if_bots_exists(request.user)

        if not file_obj.ready:
            raise BadRequestError("You cannot edit a 'not ready' file!")

        fragments = Fragment.objects.filter(file=file_obj)

        if file_obj.size > MAX_DISCORD_MESSAGE_SIZE:
            raise BadRequestError("You cannot edit a file larger than 10Mb!")
        if len(fragments) > 1:
            raise BadRequestError("Fragments > 1")

        webhook = get_webhook(request, webhook_id)

        # if file is not empty
        if len(fragments) > 0:
            old_fragment = fragments[0]
            old_message_id = old_fragment.message_id
            fragments = Fragment.objects.filter(message_id=old_message_id)
            # multi file in 1 message
            if len(fragments) > 1:
                attachment_ids = []
                for fragment in fragments:
                    if fragment != old_fragment:
                        attachment_ids.append(fragment.attachment_id)

                discord.edit_attachments(old_fragment.webhook.url, old_message_id, attachment_ids)
            else:
                # single file in 1 message

                discord.remove_message(request.user, old_message_id)
            old_message_id = old_fragment.message_id

            old_fragment.delete()
            # important invalidate caches!
            cache.delete(old_message_id)

        fragment_obj = Fragment(
            sequence=1,
            file=file_obj,
            size=fragment_size,
            attachment_id=attachment_id,
            message_id=message_id,
            webhook=webhook
        )
        fragment_obj.save()
        file_obj.size = fragment_size
        file_obj.last_modified_at = timezone.now()

        file_obj.save()

        return HttpResponse(status=204)


@api_view(['POST'])
@throttle_classes([MyUserRateThrottle])
@permission_classes([IsAuthenticated & CreatePerms])
@handle_common_errors
def create_thumbnail(request):
    thumbnails = request.data['thumbnails']
    if not isinstance(thumbnails, list):
        raise BadRequestError("'thumbnails' must be a list.")

    if len(thumbnails) > 100:
        raise BadRequestError("'thumbnails' cannot be larger than 100")

    if len(thumbnails) == 0:
        raise BadRequestError("'thumbnails' length cannot be 0.")

    for thumbnail in thumbnails:
        file_id = thumbnail['file_id']
        message_id = thumbnail['message_id']
        attachment_id = thumbnail['attachment_id']
        size = thumbnail['size']
        iv = thumbnail.get('iv')
        key = thumbnail.get('key')
        webhook_id = thumbnail['webhook']

        webhook = get_webhook(request, webhook_id)
        file_obj = get_file(file_id)
        if file_obj.is_encrypted() and (not iv or not key):  # or not key
            raise BadRequestError("Encryption key and/or iv not provided")

        if iv:
            iv = base64.b64decode(iv)
        if key:
            key = base64.b64decode(key)

        check_resource_perms(request, file_obj, checkReady=False)

        try:
            if file_obj.thumbnail:
                raise BadRequestError("A thumbnail already exists for this file.")
        except File.thumbnail.RelatedObjectDoesNotExist:
            pass

        thumbnail_obj = Thumbnail(
            file=file_obj,
            message_id=message_id,
            attachment_id=attachment_id,
            size=size,
            iv=iv,
            key=key,
            webhook=webhook,
        )
        thumbnail_obj.save()

        send_event(request.user.id, EventCode.ITEM_UPDATE, request.request_id, create_file_dict(file_obj))

    return HttpResponse(status=204)
