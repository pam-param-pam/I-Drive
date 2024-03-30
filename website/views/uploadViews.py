from django.http import JsonResponse
from django.http import JsonResponse
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.throttling import UserRateThrottle

from website.models import Folder, File, Fragment
from website.utilities.common.error import BadRequestError, ResourcePermissionError
from website.utilities.decorators import handle_common_errors

DELAY_TIME = 0


@api_view(['POST', 'PATCH'])
# @permission_classes([IsAuthenticated])
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

        response_json = []

        for file in files:
            file_name = file['name']
            parent_id = file['parent_id']
            extension = file['extension']
            mimetype = file['mimetype']
            file_size = file['size']
            file_index = file['index']

            folder_obj = Folder.objects.get(id=parent_id)
            if folder_obj.owner.id != request.user.id:  # todo fix perms
                raise ResourcePermissionError(f"You do not own this resource!")

            file_obj = File(
                extension=extension,
                name=file_name,
                size=file_size,
                mimetype=mimetype,
                type=mimetype.split("/")[0],
                owner_id=user.id,
                key="no key",
                parent_id=parent_id,
            )
            if file_size == 0:
                file_obj.ready = True
            file_obj.save()

            response_json.append({"index": file_index, "file_id": file_obj.id})

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
        if file_obj.owner.id != request.user.id:  # todo fix perms
            raise ResourcePermissionError(f"You do not own this resource!")

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
            return JsonResponse({"woo": "file fully saved"}, status=200)

        return JsonResponse({"woo": "fragment saved"}, status=200)


"""
@csrf_protect
def _upload_file(request):
    if request.method == "POST":
        form = UploadFileForm(request.POST, request.FILES)

        if form.is_valid():
            folder_id = form.data["folder_id"]
            if not Folder.objects.filter(id=folder_id).exists():
                return JsonResponse(error_res(user=request.user, code=400, error_code=8,
                                              details="Folder with id of 'folder_id' doesn't exist."), status=400)
            file = request.FILES["file"]
            request_dir = create_temp_request_dir(request.request_id)  # creating /temp/<int>/
            file_id = shortuuid.uuid()
            file_dir = create_temp_file_dir(request_dir, file_id)  # creating /temp/<int>/file_id/
            with open(os.path.join(file_dir, file.name),
                      "wb+") as destination:  # saving in /temp/<int>/file_id/filename
                for chunk in file.chunks():
                    destination.write(chunk)

            handle_uploaded_file.delay(request.user.id, request.request_id, file_id, request_dir, file_dir, file.name,
                                       file.size, folder_id)

            return JsonResponse(build_response(request.request_id, "file is being uploaded..."), status=200)

    else:
        form = UploadFileForm()
    return render(request, "upload.html", {"form": form})
    

@csrf_exempt
@api_view(['GET', 'POST'])  # TODO maybe change it later? when removing form idk
# @permission_classes([IsAuthenticated])
def upload_file(request):
    time.sleep(DELAY_TIME)

    # request.upload_handlers.insert(0, ProgressBarUploadHandler(
    #    request))  # TODO tak z lekka nie działa ale moze to dlatego ze lokalna siec? nwm

    return _upload_file(request)
"""
