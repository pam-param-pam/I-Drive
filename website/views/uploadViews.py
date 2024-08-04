import base64

from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from rest_framework.decorators import api_view, throttle_classes, permission_classes
from rest_framework.permissions import IsAuthenticated

from website.models import Folder, File, Fragment, UserSettings, Thumbnail
from website.utilities.Discord import discord
from website.utilities.Permissions import CreatePerms
from website.utilities.constants import MAX_DISCORD_MESSAGE_SIZE, cache, EventCode
from website.utilities.errors import BadRequestError, ResourcePermissionError, ThumbnailAlreadyExistsError, MissingResourcePasswordError
from website.utilities.decorators import handle_common_errors
from website.utilities.other import send_event, create_file_dict, check_folder_password, get_resource, check_resource_perms
from website.utilities.throttle import MyUserRateThrottle


@api_view(['POST', 'PATCH', 'PUT'])
@throttle_classes([MyUserRateThrottle])
@permission_classes([IsAuthenticated & CreatePerms])
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
            parent = Folder.objects.get(id=parent_id)

            if parent.owner != request.user:
                raise ResourcePermissionError()

            file_type = mimetype.split("/")[0]
            file_obj = File(
                extension=extension,
                name=file_name,
                size=file_size,
                mimetype=mimetype,
                type=file_type,
                owner_id=request.user.id,
                parent=parent,
            )
            #  apply lock if needed
            if parent.is_locked:
                file_obj.applyLock(parent, parent.password)

            if file_size == 0:
                file_obj.ready = True
            file_obj.save()

            response_json.append(
                {"index": file_index, "file_id": file_obj.id, "parent_id": parent_id, "name": file_obj.name,
                 "type": file_type, "key": base64.b64encode(file_obj.key).decode('utf-8')})

        return JsonResponse(response_json, safe=False)

    if request.method == "PATCH":
        file_id = request.data['file_id']
        fragment_sequence = request.data['fragment_sequence']
        total_fragments = request.data['total_fragments']
        message_id = request.data['message_id']
        attachment_id = request.data['attachment_id']
        fragment_size = request.data['fragment_size']
        # return fragment ID

        file_obj = get_resource(file_id)
        check_resource_perms(request, file_obj)

        if file_obj.ready:
            raise BadRequestError("You cannot further modify a 'ready' file!")

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
            return HttpResponse(status=204)

        return HttpResponse(status=204)

    if request.method == "PUT":
        file_id = request.data['file_id']

        file_obj = get_resource(file_id)
        check_resource_perms(request, file_obj)

        if not file_obj.ready:
            raise BadRequestError("You cannot edit a 'not ready' file!")

        fragments = Fragment.objects.filter(file=file_obj)

        if file_obj.size > MAX_DISCORD_MESSAGE_SIZE:
            raise BadRequestError("You cannot edit a file larger than 25Mb!")
        if len(fragments) > 1:
            raise BadRequestError("Fragments > 1")

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

        return HttpResponse(status=204)


@api_view(['POST'])
@throttle_classes([MyUserRateThrottle])
@permission_classes([IsAuthenticated & CreatePerms])
@handle_common_errors
def create_preview(request):
    file_id = request.data['file_id']
    message_id = request.data['message_id']
    attachment_id = request.data['attachment_id']
    size = request.data['size']
    encrypted_size = request.data['encrypted_size']
    key = request.data['key']

    file_obj = get_resource(file_id)
    check_resource_perms(request, file_obj)

    if file_obj.thumbnail:
        raise ThumbnailAlreadyExistsError()

    thumbnail_obj = Thumbnail(
        file=file_obj,
        message_id=message_id,
        attachment_id=attachment_id,
        size=size,
        encrypted_size=encrypted_size,
        key=key,

    )
    thumbnail_obj.save()
    return HttpResponse(status=204)
