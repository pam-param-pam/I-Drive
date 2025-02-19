import base64
from datetime import datetime

from django.core.files.uploadhandler import FileUploadHandler
from django.db.utils import IntegrityError
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
from ..utilities.throttle import defaultAuthUserThrottle, MediaThrottle, ProxyRateThrottle


@api_view(['POST', 'PATCH', 'PUT'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & CreatePerms])
@handle_common_errors
def create_file(request):
    if request.method == "POST":
        files = request.data['files']
        if not isinstance(files, list):
            raise BadRequestError("'files' must be a list.")

        if len(files) > 25:
            raise BadRequestError("'files' cannot be larger than 100")

        if len(files) == 0:
            raise BadRequestError("'files' length cannot be 0.")

        response_json = []
        ws_json = []

        for file in files:
            file_name = file['name']
            parent_id = file['parent_id']
            extension = file['extension']
            mimetype = file['mimetype']
            file_size = file['size']
            frontend_id = file['frontend_id']
            encryption_method = file['encryption_method']
            attachments = file['attachments']

            thumbnail = file.get('thumbnail')
            duration = file.get('duration')
            created_at = file.get('created_at')
            key = file.get('key')
            iv = file.get('iv')

            if EncryptionMethod(encryption_method) != EncryptionMethod.Not_Encrypted and (not iv or not key):
                raise BadRequestError("Encryption key and/or iv not provided")

            if iv:
                iv = base64.b64decode(iv)
            if key:
                key = base64.b64decode(key)

            if mimetype == "":
                mimetype = "text/plain"

            if file_name == "" or not file_name:
                raise BadRequestError("'name' cannot be empty")

            file_type = mimetype.split("/")[0]

            parent = get_folder(parent_id)
            check_resource_perms(request, parent, checkRoot=False, checkTrash=True)

            if File.objects.filter(frontend_id=frontend_id).exists():
                continue

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
            )

            if created_at:
                try:
                    timestamp_in_seconds = int(created_at) / 1000
                    created_at = timezone.make_aware(datetime.fromtimestamp(timestamp_in_seconds))
                    file_obj.created_at = created_at
                except (ValueError, OverflowError):
                    raise BadRequestError("Invalid 'created_at' timestamp format.")

            if duration:
                file_obj.duration = duration

            file_obj.ready = True

            try:
                file_obj.save()
            except IntegrityError:
                raise BadRequestError("This file already exists!")

            for attachment in attachments:
                fragment_sequence = attachment['fragment_sequence']
                message_id = attachment['message_id']
                attachment_id = attachment['attachment_id']
                fragment_size = attachment['fragment_size']
                webhook_id = attachment['webhook']
                offset = attachment['offset']

                webhook = get_webhook(request, webhook_id)

                check_resource_perms(request, file_obj, checkReady=False)

                fragment_obj = Fragment(
                    sequence=fragment_sequence,
                    file=file_obj,
                    size=fragment_size,
                    attachment_id=attachment_id,
                    message_id=message_id,
                    webhook=webhook,
                    offset=offset,
                )
                fragment_obj.save()

            if thumbnail:
                message_id = thumbnail['message_id']
                attachment_id = thumbnail['attachment_id']
                size = thumbnail['size']
                iv = thumbnail.get('iv')
                key = thumbnail.get('key')
                webhook_id = thumbnail['webhook']

                webhook = get_webhook(request, webhook_id)
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

            if file_obj.ready:
                file_response_dict = {"frontend_id": frontend_id, "file_id": file_obj.id, "parent_id": parent_id, "name": file_obj.name,
                                      "type": file_type, "encryption_method": file_obj.encryption_method}
                ws_json.append(create_file_dict(file_obj))
                response_json.append(file_response_dict)
        if ws_json:
            send_event(request.user.id, EventCode.ITEM_CREATE, request.request_id, ws_json)

        return JsonResponse(response_json, safe=False, status=200)

    if request.method == "PUT":
        file_id = request.data['file_id']
        fragment_size = request.data['fragment_size']
        message_id = request.data['message_id']
        attachment_id = request.data['attachment_id']
        webhook_id = request.data['webhook']
        offset = request.data['offset']

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
            webhook=webhook,
            offset=offset,
        )
        fragment_obj.save()
        file_obj.size = fragment_size
        file_obj.last_modified_at = timezone.now()

        file_obj.save()

        return HttpResponse(status=204)


@api_view(['POST'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & CreatePerms])
@handle_common_errors
def create_thumbnail(request):
    file_id = request.data['file_id']
    message_id = request.data['message_id']
    attachment_id = request.data['attachment_id']
    size = request.data['size']
    webhook_id = request.data['webhook']

    iv = request.data.get('iv')
    key = request.data.get('key')

    if iv:
        iv = base64.b64decode(iv)
    if key:
        key = base64.b64decode(key)

    file_obj = get_file(file_id)
    check_resource_perms(request, file_obj)

    webhook = get_webhook(request, webhook_id)

    if file_obj.thumbnail:
        file_obj.thumbnail.delete()

    thumbnail_obj = Thumbnail(
        file=file_obj,
        message_id=message_id,
        attachment_id=attachment_id,
        size=size,
        key=key,
        iv=iv,
        webhook=webhook

    )
    thumbnail_obj.save()
    file_obj.remove_cache()

    file_dict = create_file_dict(file_obj)
    send_event(file_obj.owner.id, EventCode.ITEM_UPDATE, request.request_id, file_dict)

    return HttpResponse(status=204)

@api_view(["POST"])
@throttle_classes([ProxyRateThrottle])
@permission_classes([IsAuthenticated])
@handle_common_errors
def proxy_discord(request):
    # todo secure to prevent denial of service
    json_payload = request.data.get("json_payload")

    files = request.FILES

    if not json_payload:
        raise BadRequestError("Missing json_payload")

    res = discord.send_file(request.user, json=json_payload, files=files)

    return JsonResponse(res.json(), status=res.status_code, safe=False)
