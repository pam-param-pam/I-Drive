from django.http import JsonResponse, HttpResponse
from rest_framework.decorators import api_view, throttle_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle

from website.models import Folder, File, Fragment
from website.utilities.OPCodes import EventCode
from website.utilities.errors import BadRequestError, ResourcePermissionError
from website.utilities.decorators import handle_common_errors
from website.utilities.other import send_event, create_file_dict


@api_view(['POST', 'PATCH'])
@permission_classes([IsAuthenticated])
@throttle_classes([UserRateThrottle])
@handle_common_errors
def create_file(request):
    user = request.user
    user.id = 1

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

            folder_obj = Folder.objects.get(id=parent_id)
            if folder_obj.owner != request.user:
                raise ResourcePermissionError(f"You do not own this resource!")

            file_type = mimetype.split("/")[0]
            file_obj = File(
                extension=extension,
                name=file_name,
                size=file_size,
                mimetype=mimetype,
                type=file_type,
                owner_id=user.id,
                key=b"no key",
                parent_id=parent_id,
            )
            if file_size == 0:
                file_obj.ready = True
            file_obj.save()

            response_json.append({"index": file_index, "file_id": file_obj.id, "parent_id": parent_id, "name": file_obj.name, "type": file_type})

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
            raise ResourcePermissionError(f"You do not own this resource!")
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

