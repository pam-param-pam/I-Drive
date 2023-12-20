import os
import uuid
from wsgiref.util import FileWrapper

import m3u8
import requests
from django.core.exceptions import ValidationError
from django.http import HttpResponse, StreamingHttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from rest_framework.decorators import permission_classes, api_view
from rest_framework.permissions import IsAuthenticated

from website.decorators import view_cleanup
from website.forms import UploadFileForm
from website.models import File, Fragment, Folder
from website.tasks import process_download, handle_uploaded_file, delete_files
from website.utilities.Discord import discord
from website.utilities.other import create_temp_request_dir, create_temp_file_dir

MAX_MB = 25
MAX_STREAM_MB = 23


# TODO user_id to user lol

# TODO make real size and encrypted size
@csrf_exempt
def upload_file(request):
    # request.upload_handlers.insert(0, ProgressBarUploadHandler(request)) #TODO tak z lekka nie działa ale moze to dlatego ze lokalna siec? nwm
    return _upload_file(request)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def index(request):
    return HttpResponse(f"hello {request.user}")





def download(request, file_id):
    try:
        file_obj = File.objects.get(id=file_id)
    except File.DoesNotExist:
        return HttpResponse(f"doesn't exist", status=404)
    if request.user.id not in (
            file_obj.owner.id, file_obj.maintainer.id, file_obj.viewer.id):  # owner, maintainer or viewer perms needed
        return HttpResponse(f"unauthorized", status=403)

    if file_obj.streamable:
        return HttpResponse(f"This file is not downloadable on this endpoint, use m3u8 file", status=404)
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
            with open(os.path.join(file_dir, file.name), "wb+") as destination:
                for chunk in file.chunks():
                    destination.write(chunk)
            handle_uploaded_file.delay(request.user.id, request.request_id, file_id, request_dir, file_dir, file.name,
                                       file.size, folder_id)

            return HttpResponse(f"{request.request_id}", status=200)

    else:
        form = UploadFileForm()
    return render(request, "upload.html", {"form": form})


@view_cleanup
def streamkey(request, file_id):
    try:
        file_obj = File.objects.get(id=file_id)
    except File.DoesNotExist:
        return HttpResponse(f"doesn't exist", status=404)
    if request.user.id not in (
            file_obj.owner.id, file_obj.maintainer.id, file_obj.viewer.id):  # owner, maintainer or viewer perms needed
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
    pass


@view_cleanup
def get_m3u8(request, file_id):
    try:
        file_obj = File.objects.get(id=file_id)
    except File.DoesNotExist:
        return HttpResponse(f"doesn't exist", status=404)
    if request.user.id not in (
            file_obj.owner.id, file_obj.maintainer.id, file_obj.viewer.id):  # owner, maintainer or viewer perms needed
        return HttpResponse(f"unauthorized", status=403)
    if not file_obj.streamable:
        return HttpResponse(f"This file is not streamable!", status=404)

    file_content = process_m3u8(request.request_id, file_obj)

    response = HttpResponse(file_content, content_type='application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="manifest.m3u8"'

    return response


@api_view(['POST'])
def create_folder(request):
    if request.method == "POST":
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
def movefolder(request):
    if request.method == "POST":
        try:

            folder = Folder.objects.get(id=request.POST['folder_id'])

            parent = Folder.objects.get(id=request.POST['parent_id'])

            user = request.user

            user = 1  # todo
            if parent == folder.parent or folder == parent:  # im surprised i fought of that(there's prob a bug somewhere here)
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
def movefile(request):
    if request.method == "POST":
        try:

            file = Folder.objects.get(id=request.POST['file_id'])

            parent = Folder.objects.get(id=request.POST['parent_id'])

            user = request.user

            user = 1  # todo
            if parent == file.parent:  # im surprised I fought of that(there's prob a bug somewhere here)
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


# this should be a post or delete imo
def delete_file(request, file_id):
    try:
        file_obj = File.objects.get(id=file_id)
    except File.DoesNotExist:
        return HttpResponse(f"doesn't exist", status=404)

    if file_obj.owner.id != request.user.id:  # owner perms needed
        return HttpResponse(f"unauthorized", status=403)

    delete_files.delay(request.user.id, request.request_id, file_id)
    return HttpResponse("file deleted")