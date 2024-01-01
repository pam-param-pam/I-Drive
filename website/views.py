import os
import time
import uuid
from wsgiref.util import FileWrapper

import m3u8
import requests
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import HttpResponse, StreamingHttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from rest_framework.decorators import permission_classes, api_view, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle

from website.decorators import view_cleanup
from website.forms import UploadFileForm
from website.models import File, Fragment, Folder
from website.tasks import process_download, handle_uploaded_file, delete_file_task, test_task, delete_folder_task
from website.utilities.Discord import discord
from website.utilities.other import create_temp_request_dir, create_temp_file_dir, build_folder_tree

MAX_MB = 25
MAX_STREAM_MB = 23

# TODO return only if ready=true
# TODO user_id to user lol

@csrf_exempt
@api_view(['GET', 'POST'])  # TODO maybe change it later? when removing form idk
# @permission_classes([IsAuthenticated])
def upload_file(request):
    # request.upload_handlers.insert(0, ProgressBarUploadHandler(request)) #TODO tak z lekka nie działa ale moze to dlatego ze lokalna siec? nwm
    return _upload_file(request)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@throttle_classes([UserRateThrottle])
def index(request):
    return HttpResponse(f"hello {request.user}")


@api_view(['GET'])
# @permission_classes([IsAuthenticated])
def download(request, file):
    try:
        file_obj = File.objects.get(id=file)
    except (File.DoesNotExist, ValidationError):

        return HttpResponse(f"doesn't exist", status=404)

    # owner, maintainer or viewer perms needed
    if request.user.id not in (
            file_obj.owner.id,
            getattr(file_obj.maintainer, 'id', None),
            getattr(file_obj.viewer, 'id', None)
    ):
        return HttpResponse(f"unauthorized", status=403)

    if file_obj.streamable:
        return HttpResponse(f"This file is not downloadable on this endpoint, use m3u8 file", status=404)
    if not file_obj.ready:
        return HttpResponse(f"This file is not uploaded yet", status=404)

    # checking if the file is already downloaded
    file_path = os.path.join("temp", "downloads",
                             str(file_obj.id), file_obj.name)  # temp/downloads/file_id/name.extension
    if os.path.isfile(file_path):
        chunk_size = 8192
        response = StreamingHttpResponse(
            FileWrapper(
                open(file_path, "rb"),
                chunk_size,
            ),
            content_type='application/force-download',
        )
        response['Content-Disposition'] = f'attachment; filename={file_obj.name}'
        response['Content-Length'] = os.path.getsize(file_path)
        return response

    process_download.delay(request.user.id, request.request_id, file_obj.id)
    return HttpResponse("file is being processed for the download")


@csrf_protect
def _upload_file(request):
    if request.method == "POST":
        form = UploadFileForm(request.POST, request.FILES)

        if form.is_valid():
            folder_id = form.data["folder_id"]
            if not Folder.objects.filter(id=folder_id).exists():
                return HttpResponse(f"doesn't exist", status=404)

            file = request.FILES["file"]
            request_dir = create_temp_request_dir(request.request_id)  # creating /temp/<int>/
            file_id = uuid.uuid4()
            file_dir = create_temp_file_dir(request_dir, file_id)  # creating /temp/<int>/file_id/
            with open(os.path.join(file_dir, file.name),
                      "wb+") as destination:  # saving in /temp/<int>/file_id/filename
                for chunk in file.chunks():
                    destination.write(chunk)

            handle_uploaded_file.delay(request.user.id, request.request_id, file_id, request_dir, file_dir, file.name,
                                       file.size, folder_id)

            return HttpResponse(f"{request.request_id}", status=200)

    else:
        form = UploadFileForm()
    return render(request, "upload.html", {"form": form})


@api_view(['GET'])
# @permission_classes([IsAuthenticated])
@view_cleanup
def stream_key(request, file_id):
    try:
        file_obj = File.objects.get(id=file_id)
    except (File.DoesNotExist, ValidationError):

        return HttpResponse(f"doesn't exist", status=404)
    if not file_obj.ready:
        return HttpResponse(f"This file is not uploaded yet", status=404)
    # owner, maintainer or viewer perms needed
    if request.user.id not in (
            file_obj.owner.id,
            getattr(file_obj.maintainer, 'id', None),
            getattr(file_obj.viewer, 'id', None)
    ):
        return HttpResponse(f"unauthorized", status=403)
    if not file_obj.streamable:
        return HttpResponse(f"This file is not streamable!", status=404)

    request_dir = create_temp_request_dir(request.request_id)
    file_dir = create_temp_file_dir(request_dir, file_obj.id)

    key_file_path = os.path.join(file_dir, "enc.key")

    with open(key_file_path, 'wb+') as file:
        file.write(file_obj.key)
        # Move the file cursor to the beginning before reading
        file.seek(0)  # vevy important
        file_content = file.read()

    response = HttpResponse(file_content, content_type='application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="key.enc"'
    return response


def process_m3u8(request_id, file_obj):
    file_url = discord.get_file_url(file_obj.m3u8_message_id)

    request_dir = create_temp_request_dir(request_id)
    file_dir = create_temp_file_dir(request_dir, file_obj.id)

    response = requests.get(file_url, stream=True)

    m3u8_file_path = os.path.join(file_dir, "manifest.m3u8")
    with open(m3u8_file_path, 'wb') as file:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                file.write(chunk)

    playlist = m3u8.load(m3u8_file_path)
    new_key = m3u8.Key(method="AES-128", base_uri=f"https://pamparampam.dev/stream/{file_obj.id}/key",
                       # TODO change it back later
                       uri=f"https://pamparampam.dev/stream/{file_obj.id}/key")
    new_key = m3u8.Key(method="AES-128", base_uri=f"http://127.0.0.1:8000/stream/{file_obj.id}/key",
                       # TODO change it back later
                       uri=f"http://127.0.0.1:8000/stream/{file_obj.id}/key")
    fragments = Fragment.objects.filter(file_id=file_obj).order_by('sequence')
    for fragment, segment in zip(fragments, playlist.segments.by_key(playlist.keys[-1])):
        url = discord.get_file_url(fragment.message_id)
        segment.uri = url
        segment.key = new_key

    playlist.keys[-1] = new_key

    playlist.dump(m3u8_file_path)
    with open(m3u8_file_path, 'rb') as file:
        file_content = file.read()

    return file_content


def test(request):
    test_task.delay()
    return HttpResponse(f"yupi", status=200)


@api_view(['GET'])
# @permission_classes([IsAuthenticated])
@view_cleanup
def get_m3u8(request, file_id):
    try:
        file_obj = File.objects.get(id=file_id)
    except (File.DoesNotExist, ValidationError):
        return HttpResponse(f"doesn't exist", status=404)
    if not file_obj.ready:
        return HttpResponse(f"This file is not uploaded yet", status=404)
    # owner, maintainer or viewer perms needed
    if request.user.id not in (
            file_obj.owner.id,
            getattr(file_obj.maintainer, 'id', None),
            getattr(file_obj.viewer, 'id', None)
    ):
        return HttpResponse(f"unauthorized", status=403)
    if not file_obj.streamable:
        return HttpResponse(f"This file is not streamable!", status=404)

    file_content = process_m3u8(request.request_id, file_obj)

    response = HttpResponse(file_content, content_type='application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="manifest.m3u8"'

    return response


@api_view(['POST'])
# @permission_classes([IsAuthenticated])
def create_folder(request):
    try:
        name = request.POST['name']

        parent = Folder.objects.get(id=request.POST['parent_id'])

        user = request.user

        user = 1  # todo
        folder_obj = Folder(
            name=name,
            parent=parent,
            owner_id=user,
        )
        folder_obj.save()
        return HttpResponse(f"folder created {request.request_id} id={folder_obj.id}", status=200)

    except (ValidationError, Folder.DoesNotExist):
        return HttpResponse(f"bad request: parent is not correct", status=404)

    except KeyError:
        return HttpResponse(f"bad request", status=404)


@api_view(['POST'])
# @permission_classes([IsAuthenticated])
def movefolder(request):
    try:

        folder = Folder.objects.get(id=request.POST['folder_id'])  # folder to be moved

        parent = Folder.objects.get(id=request.POST['parent_id'])  # destination folder

        user = request.user

        user = 1  # todo
        if parent == folder.parent or parent == folder:
            return HttpResponse(f"bad request: folders are the same", status=404)

        if folder.owner_id != user or (folder.maintainer_id and folder.maintainer_id != user) or \
                parent.owner_id != user or (parent.maintainer_id and parent.maintainer_id != user):
            return HttpResponse("unauthorized", status=403)

        folder.parent = parent

        folder.save()
        return HttpResponse(f"folder moved {request.request_id} to={parent.name}", status=200)

    except (ValidationError, Folder.DoesNotExist):
        return HttpResponse(f"bad request: folder id or parent id are not correct", status=404)

    except KeyError:
        return HttpResponse(f"bad request", status=404)


@api_view(['POST'])  # not tested lul
# @permission_classes([IsAuthenticated])
def movefile(request):
    try:

        file = Folder.objects.get(id=request.POST['file_id'])  # file to be moved

        parent = Folder.objects.get(id=request.POST['parent_id'])  # destination folder

        user = request.user

        user = 1  # todo
        if parent == file.parent:  # if old folder and new folder are the same, throw error
            return HttpResponse(f"bad request: folders are the same", status=404)

        if file.owner_id != user or (file.maintainer_id and file.maintainer_id != user) or \
                parent.owner_id != user or (parent.maintainer_id and parent.maintainer_id != user):
            return HttpResponse("unauthorized", status=403)

        file.parent = parent

        file.save()
        return HttpResponse(f"file moved {request.request_id} to={parent.name}", status=200)

    except (ValidationError, Folder.DoesNotExist):
        return HttpResponse(f"bad request: file id or parent id are not correct", status=404)

    except KeyError:
        return HttpResponse(f"bad request", status=404)


@api_view(['POST'])  # this should be a post or delete imo
# @permission_classes([IsAuthenticated])
def delete_file(request):
    try:
        file_obj = File.objects.get(id=request.POST['file_id'])  # file to be moved
        user = request.user

        user.id = 1  # todo
        if file_obj.owner.id != user.id:  # owner perms needed
            return HttpResponse(f"unauthorized", status=403)

        delete_file_task.delay(user.id, request.request_id, file_obj.id)
        return HttpResponse("file deleted")

    except (File.DoesNotExist, ValidationError):
        return HttpResponse(f"doesn't exist", status=404)


@api_view(['POST'])  # this should be a post or delete imo
# @permission_classes([IsAuthenticated])
def delete_folder(request):
    try:

        folder_obj = Folder.objects.get(id=request.POST['folder_id'])  # file to be moved

        user = request.user

        user.id = 1  # todo

        if folder_obj.owner.id != request.user.id:  # owner perms needed
            return HttpResponse(f"unauthorized", status=403)

        delete_folder_task.delay(request.user.id, request.request_id, folder_obj.id)
        return HttpResponse("folder deleted")
    except (Folder.DoesNotExist, ValidationError):
        return HttpResponse(f"doesn't exist", status=404)
    except KeyError:
        return HttpResponse(f"bad request", status=404)

@api_view(['POST'])  # this should be a post or delete imo
# @permission_classes([IsAuthenticated])
def change_file_name(request):
    try:
        user = request.user

        user.id = 1  # todo

        file_obj = File.objects.get(id=request.POST['file_id'])  # file to be moved
        new_name = request.POST['new_name']
        if file_obj.owner.id != request.user.id:  # todo fix perms
            return HttpResponse(f"unauthorized", status=403)

        file_obj.name = new_name
        file_obj.save()
        return HttpResponse(f"Changed name to {new_name}", status=200)

    except (Folder.DoesNotExist, ValidationError):
        return HttpResponse(f"doesn't exist", status=404)
    except KeyError:
        return HttpResponse(f"bad request", status=404)


@api_view(['POST'])  # this should be a post or delete imo
# @permission_classes([IsAuthenticated])
def change_folder_name(request):
    try:
        user = request.user

        user.id = 1  # todo

        folder_obj = Folder.objects.get(id=request.POST['folder_id'])  # file to be moved
        new_name = request.POST['new_name']

        if folder_obj.owner.id != request.user.id:  # todo fix perms
            return HttpResponse(f"unauthorized", status=403)

        folder_obj.name = new_name
        folder_obj.save()
        return HttpResponse(f"Changed name to {new_name}", status=200)

    except (Folder.DoesNotExist, ValidationError):
        return HttpResponse(f"doesn't exist", status=404)
    except KeyError:
        return HttpResponse(f"bad request", status=404)


def get_folders(request):
    user = request.user

    user.id = 1  # todo
    try:

        user_folders = Folder.objects.filter(owner_id=user.id) # todo
        folder_structure = build_folder_tree(user_folders)
        return JsonResponse(folder_structure[0], safe=False)

    except (Folder.DoesNotExist, ValidationError):
        return HttpResponse(f"doesn't exist", status=404)
    except Folder.MultipleObjectsReturned:
        return HttpResponse(f"Database is malformed WHOOPS", status=404)
    except KeyError:
        return HttpResponse(f"bad request", status=404)


def get_folder(request, folder_id):
    user = request.user

    user.id = 1  # todo
    try:

        folder_obj = Folder.objects.get(id=folder_id)
        if folder_obj.owner.id != request.user.id:  # todo fix perms
            return HttpResponse(f"unauthorized", status=403)
        json_string = create_folder_dict(folder_obj)

        return JsonResponse(json_string)

    except (Folder.DoesNotExist, ValidationError):
        return HttpResponse(f"doesn't exist", status=404)
    except KeyError:
        return HttpResponse(f"bad request", status=404)

def search(request, query):
    user = request.user

    user.id = 1  # todo
    try:
        files = File.objects.filter()
        filtered_files = File.objects.filter(Q(name__icontains=query) | Q(parent__name__icontains=query), owner_id=user.id) # todo fix id

        print(filtered_files)

        return HttpResponse(filtered_files, status=200)

    except (Folder.DoesNotExist, ValidationError):
        return HttpResponse(f"doesn't exist", status=404)
    except KeyError:
        return HttpResponse(f"bad request", status=404)
