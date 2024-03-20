import os
import time

import shortuuid
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.core.exceptions import ValidationError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle

from website.forms import UploadFileForm
from website.models import Folder, File, UserSettings, Fragment
from website.tasks import handle_uploaded_file
from website.utilities.other import create_temp_request_dir, create_temp_file_dir, build_response, error_res

DELAY_TIME = 0


@csrf_exempt
@api_view(['GET', 'POST'])  # TODO maybe change it later? when removing form idk
# @permission_classes([IsAuthenticated])
def upload_file(request):
    time.sleep(DELAY_TIME)

    # request.upload_handlers.insert(0, ProgressBarUploadHandler(
    #    request))  # TODO tak z lekka nie działa ale moze to dlatego ze lokalna siec? nwm

    return _upload_file(request)


@api_view(['POST', 'PATCH'])
# @permission_classes([IsAuthenticated])
@throttle_classes([UserRateThrottle])
def create_file(request):
    user = request.user
    user.id = 1
    if request.method == "POST":
        file_name = request.data['name']
        parent_id = request.data['parent_id']
        extension = request.data['extension']
        file_type = request.data['type']

        file_size = request.data['size']

        try:
            folder_obj = Folder.objects.get(id=parent_id)
            if folder_obj.owner.id != request.user.id:  # todo fix perms
                return JsonResponse(
                    error_res(user=request.user, code=403, error_code=5, details="You do not own this resource."),
                    status=403)
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
                backend=default_backend()
            )
            public_key = private_key.public_key()
            private_key_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )

            public_key_pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )

            file_obj = File(
                extension=extension,
                name=file_name,
                size=file_size,
                type=file_type,
                owner_id=user.id,
                key=private_key_pem,
                parent_id=parent_id,
            )
            file_obj.save()
            settings = UserSettings.objects.get(user=request.user)

            return JsonResponse(
                {"key": public_key_pem.decode(), "file_id": file_obj.id, "webhook_url": settings.discord_webhook})

        except (Folder.DoesNotExist, ValidationError):
            return JsonResponse(error_res(user=request.user, code=400, error_code=8,
                                          details="Folder with id of 'parent_id' doesn't exist."), status=400)
        except KeyError:
            return JsonResponse(
                error_res(user=request.user, code=404, error_code=1, details="Missing some required parameters"),
                status=404)

    if request.method == "PATCH":
        file_id = request.data['file_id']
        fragment_sequence = request.data['fragment_sequence']
        total_fragments = request.data['total_fragments']
        message_id = request.data['message_id']
        fragment_size = request.data['fragment_size']
        # return fragment ID
        try:
            file_obj = File.objects.get(id=file_id)
            if file_obj.owner.id != request.user.id:  # todo fix perms
                return JsonResponse(
                    error_res(user=request.user, code=403, error_code=5, details="You do not own this resource."),
                    status=403)
            fragment_obj = Fragment(
                sequence=fragment_sequence,
                file=file_obj,
                size=fragment_size,
                encrypted_size=fragment_size,
                message_id=message_id,
            )
            fragment_obj.save()
            if fragment_sequence == total_fragments:
                file_obj.ready = True
                file_obj.save()
                return JsonResponse({"woo": "file fully saved"}, status=200)

            return JsonResponse({"woo": "fragment saved"}, status=200)

        except (File.DoesNotExist, ValidationError):
            return JsonResponse(error_res(user=request.user, code=400, error_code=8,
                                          details="File with id of 'file_id' doesn't exist."), status=400)
        except KeyError:
            return JsonResponse(
                error_res(user=request.user, code=404, error_code=1, details="Missing some required parameters"),
                status=404)


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
