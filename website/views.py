import os
import uuid
from wsgiref.util import FileWrapper

import m3u8
import requests
from django.http import HttpResponse, StreamingHttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt, csrf_protect

from website.Handlers import ProgressBarUploadHandler
from website.decorators import view_cleanup
from website.forms import UploadFileForm
from website.models import File, Fragment
from website.tasks import process_download, handle_uploaded_file, delete_files
from website.utilities.Discord import discord
from website.utilities.other import create_temp_request_dir, create_temp_file_dir

MAX_MB = 25
MAX_STREAM_MB = 23


# TODO make real size and encrypted size
@csrf_exempt
def upload_file(request):
    # request.upload_handlers.insert(0, ProgressBarUploadHandler(request)) #TODO tak z lekka nie działa ale moze to dlatego ze lokalna siec? nwm
    return _upload_file(request)


def index(request):
    return HttpResponse("hello")


def delete_file(request, file_id):
    if not File.objects.filter(id=file_id).exists():
        return HttpResponse(f"doesn't exist", status=404)

    delete_files.delay(file_id)
    return HttpResponse("file deleted")


def download(request, file_id):
    try:
        file_obj = File.objects.get(id=file_id)
    except File.DoesNotExist:
        return HttpResponse(f"doesn't exist", status=404)
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

    process_download.delay(request.request_id, file_obj.id)
    return HttpResponse("file is being processed for the download")


@csrf_protect
def _upload_file(request):
    if request.method == "POST":
        form = UploadFileForm(request.POST, request.FILES)

        if form.is_valid():
            file = request.FILES["file"]
            request_dir = create_temp_request_dir(request.request_id)  # creating /temp/<int>/
            file_id = uuid.uuid4()
            file_dir = create_temp_file_dir(request_dir, file_id)  # creating /temp/<int>/file_id/
            with open(os.path.join(file_dir, file.name), "wb+") as destination:
                for chunk in file.chunks():
                    destination.write(chunk)
            handle_uploaded_file.delay(request.request_id, file_id, request_dir, file_dir, file.name, file.size)

    else:
        form = UploadFileForm()
    return render(request, "upload.html", {"form": form})


@view_cleanup
def streamkey(request, file_id):
    try:
        file_obj = File.objects.get(id=file_id)
    except File.DoesNotExist:
        return HttpResponse(f"doesn't exist", status=404)

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

    if not file_obj.streamable:
        return HttpResponse(f"This file is not streamable!", status=404)

    file_content = process_m3u8(request.request_id, file_obj)

    response = HttpResponse(file_content, content_type='application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="manifest.m3u8"'

    return response
