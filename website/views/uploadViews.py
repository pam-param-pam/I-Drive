from django.core.cache import caches
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from rest_framework.decorators import api_view, throttle_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle

from website.models import Folder, File, Fragment, UserSettings
from website.utilities.Discord import discord
from website.utilities.OPCodes import EventCode
from website.utilities.Permissions import CreatePerms
from website.utilities.constants import MAX_DISCORD_MESSAGE_SIZE, cache
from website.utilities.errors import BadRequestError, ResourcePermissionError
from website.utilities.decorators import handle_common_errors
from website.utilities.other import send_event, create_file_dict


@api_view(['POST', 'PATCH', 'PUT'])
@permission_classes([IsAuthenticated & CreatePerms])
@throttle_classes([UserRateThrottle])
@handle_common_errors
def create_file(request):

    if request.method == "POST":
        files = request.data['files']
        if not isinstance(files, list):
            raise BadRequestError("'ids' must be a list.")

        if len(files) > 100:
            raise BadRequestError("'ids' cannot be larger than 100")

        if len(files) == 0:
            raise BadRequestError("'ids' length cannot be 0.")

        response_json = []

        for file in files:
            file_name = file['name']
            parent_id = file['parent_id']
            extension = file['extension']
            mimetype = file['mimetype']
            file_size = file['size']
            file_index = file['index']
            if mimetype == "":
                mimetype = "text/plain"

            if file_name == "" or not file_name:
                raise BadRequestError("'name' cannot be empty")
            folder_obj = Folder.objects.get(id=parent_id)

            if folder_obj.owner != request.user:
                raise ResourcePermissionError()

            file_type = mimetype.split("/")[0]
            file_obj = File(
                extension=extension,
                name=file_name,
                size=file_size,
                mimetype=mimetype,
                type=file_type,
                owner_id=request.user.id,
                key=b"no key",
                parent_id=parent_id,
            )
            if file_size == 0:
                file_obj.ready = True
            file_obj.save()

            response_json.append(
                {"index": file_index, "file_id": file_obj.id, "parent_id": parent_id, "name": file_obj.name,
                 "type": file_type})

        return JsonResponse(response_json, safe=False)

    if request.method == "PATCH":
        file_id = request.data['file_id']
        fragment_sequence = request.data['fragment_sequence']
        total_fragments = request.data['total_fragments']
        message_id = request.data['message_id']
        attachment_id = request.data['attachment_id']
        fragment_size = request.data['fragment_size']
        # return fragment ID

        file_obj = File.objects.get(id=file_id)
        if file_obj.owner != request.user:
            raise ResourcePermissionError()
        if file_obj.ready:
            raise BadRequestError(f"You cannot further modify a 'ready' file!")

        fragment_obj = Fragment(
            sequence=fragment_sequence,
            file=file_obj,
            size=fragment_size,
            attachment_id=attachment_id,
            encrypted_size=fragment_size,
            message_id=message_id,
        )
        fragment_obj.save()
        if fragment_sequence == total_fragments:
            file_obj.ready = True
            file_obj.save()

            send_event(request.user.id, EventCode.ITEM_CREATE, request.request_id, [create_file_dict(file_obj)])
            return HttpResponse(status=200)

        return HttpResponse(status=200)

    if request.method == "PUT":
        file_id = request.data['file_id']

        file_obj = File.objects.get(id=file_id)
        if file_obj.owner != request.user:
            raise ResourcePermissionError()
        if not file_obj.ready:
            raise BadRequestError(f"You cannot edit a 'not ready' file!")

        fragments = Fragment.objects.filter(file=file_obj)

        if file_obj.size > MAX_DISCORD_MESSAGE_SIZE:
            raise BadRequestError(f"You cannot edit a file larger than 25Mb!")
        if len(fragments) > 1:
            raise BadRequestError(f"Fragments > 1")

        fragment_size = request.data['fragment_size']
        message_id = request.data['message_id']
        attachment_id = request.data['attachment_id']

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

                settings = UserSettings.objects.get(user_id=request.user)
                webhook = settings.discord_webhook

                discord.edit_attachments(webhook, old_message_id, attachment_ids)
            else:
                # single file in 1 message

                discord.remove_message(old_message_id)
            old_message_id = old_fragment.message_id
            old_fragment.delete()
            # important invalidate caches!
            cache.delete(old_message_id)

        fragment_obj = Fragment(
            sequence=1,
            file=file_obj,
            size=fragment_size,
            attachment_id=attachment_id,
            encrypted_size=fragment_size,
            message_id=message_id,
        )
        fragment_obj.save()
        file_obj.size = fragment_size
        file_obj.last_modified_at = timezone.now()

        file_obj.save()

        return HttpResponse(200)
