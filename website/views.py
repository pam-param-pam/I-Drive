import os
import subprocess
import uuid
from base64 import urlsafe_b64encode, urlsafe_b64decode
from pathlib import Path
from wsgiref.util import FileWrapper

import m3u8
import requests
from cryptography.fernet import Fernet
from django.http import HttpResponse
from django.shortcuts import render
from django.utils.encoding import smart_str
from django.views.decorators.csrf import csrf_exempt, csrf_protect

from website.decorators import cleanup
from website.forms import UploadFileForm
from website.models import File, Fragment
from website.utilities.Discord import discord
from website.utilities.merge import Merge
from website.utilities.split import Split

MAX_MB = 1

# TODO make real size and encrypted size
@csrf_exempt
def upload_file(request):
    # request.upload_handlers.insert(0, ProgressBarUploadHandler(request))
    return _upload_file(request)


def upload_files_from_folder(path, file_obj):
    for filename in os.listdir(path):
        file_path = os.path.join(path, filename)
        if os.path.isfile(file_path):
            extension = Path(file_path).suffix

            with open(file_path, 'rb') as file:

                name = Path(file_path).stem

                file_name = name + extension

                files = {'file': (file_name, file, 'application/octet-stream')}
                response = discord.send_file(files)
                message_id = response.json()["id"]

                if extension == ".m3u8":
                    file_obj.m3u8_message_id = message_id
                    file_obj.save()
                elif extension == ".ts":
                    fragment_obj = Fragment(
                        sequence=name,
                        file=file_obj,
                        message_id=message_id,
                    )
                    fragment_obj.save()

                else:
                    fragment_obj = Fragment(
                        sequence=name,
                        file=file_obj,
                        message_id=message_id,
                    )
                    fragment_obj.save()


def calculate_time(file_size_bytes, bitrate_bps):
    time_seconds = (file_size_bytes * 8) / bitrate_bps
    return time_seconds


def create_temp_request_dir(request_id):
    upload_folder = os.path.join("temp", request_id)
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
    return upload_folder


def create_temp_file_dir(upload_folder, file_id):
    out_folder_path = os.path.join(upload_folder, str(file_id))
    if not os.path.exists(out_folder_path):
        os.makedirs(out_folder_path)
    return out_folder_path


def handle_uploaded_file(request):
    split_required = False
    f = request.FILES["file"]
    request_dir = create_temp_request_dir(request.request_id)  # creating /temp/<int>/
    file_id = uuid.uuid4()
    file_dir = create_temp_file_dir(request_dir, file_id)  # creating /temp/<int>/file_id/
    with open(os.path.join(file_dir, f.name), "wb+") as destination:
        for chunk in f.chunks():
            destination.write(chunk)

    extension = Path(f.name).suffix
    file_obj = File(
        extension=extension,
        name=f.name,
        id=file_id,
        streamable=False,
        size=f.size,
        parent_id="root",
    )

    file_obj.save()
    file_path = os.path.join(file_dir, f.name)

    if extension == ".mp4":
        try:

            result = subprocess.run(
                f"ffprobe -v quiet -select_streams v:0 -show_entries stream=bit_rate -of default=noprint_wrappers=1:nokey=1 {file_path}",
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

            #  don't ask me why we multiply it by 900 bytes and not 1024, it just works(mostly)
            calculated_time = calculate_time(MAX_MB * 900 * 900, int(result.stdout.strip()))

            ffmpeg_command = [
                'ffmpeg',
                '-i', file_path,
                '-c', 'copy',
                '-start_number', '0',
                '-hls_enc', '1',
                '-hls_time', f'{calculated_time}',
                '-hls_list_size', '0',
                '-f', 'hls',
                '-hls_base_url', f'https://pamparampam.dev/stream/{file_obj.id}/',
                # '-hls_flags', 'temp_file',  # Use temp_file option
                '-hls_segment_filename', f"{file_dir}/%d.ts",
                f'{os.path.join(file_dir, "manifest.m3u8")}'
            ]

            subprocess.run(ffmpeg_command, check=True)
            key_file_path = os.path.join(file_dir, "manifest.m3u8.key")

            with open(key_file_path, 'rb') as file:
                key = file.read()
                file_obj.key = key

            os.remove(key_file_path)  # removing file key to not send it to Discord accidentally...
            file_obj.streamable = True
            file_obj.save()
        except subprocess.CalledProcessError:
            # TODO inform user that an error occured
            split_required = True

    if split_required or extension != ".mp4":
        key = Fernet.generate_key()
        file_obj.key = key

        file_obj.save()
        print(file_obj.key)
        with open(file_path, 'rb+') as file:
            original = file.read()
            fernet = Fernet(file_obj.key)
            encrypted = fernet.encrypt(original)
            file.seek(0) #  vevy important
            file.write(encrypted)

        split = Split(file_path, file_dir)
        split.manfilename = "0"
        split.bysize(MAX_MB * 1024 * 1023)

    os.remove(file_path)  # removing original file, as we have it split already
    upload_files_from_folder(file_dir, file_obj)


def merge_callback(filename, size, key):
    with open(filename, 'rb+') as file:
        fernet = Fernet(key)
        content = fernet.decrypt(file.read())
        file.seek(0) #  vevy important
        file.write(content)
    print("merge finished")


def index(request):
    return HttpResponse("hello")


def process_download(request_id, file_obj):
    fragments = Fragment.objects.filter(file=file_obj)
    request_dir = create_temp_request_dir(request_id)
    file_dir = create_temp_file_dir(request_dir, file_obj.id)

    if fragments:


        for fragment in fragments:
            url = discord.get_file_url(fragment.message_id)
            response = requests.get(url)

            with open(os.path.join(file_dir, str(fragment.sequence)), 'wb') as file:

                file.write(response.content)

        download_file_path = os.path.join("temp", "downloads",
                                          str(file_obj.id))  # temp/downloads/file_id/name.extension

        if not os.path.exists(download_file_path):
            os.makedirs(download_file_path)

        merge = Merge(file_dir, download_file_path, file_obj.name)
        merge.manfilename = "0"  # handle manifest UwU
        merge.merge(cleanup=True, key=file_obj.key, callback=merge_callback)


@cleanup
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

        wrapper = FileWrapper(open(file_path, "rb"))
        response = HttpResponse(wrapper, content_type='application/force-download')
        response['Content-Disposition'] = f'attachment; filename={file_obj.name}'

        response['Content-Length'] = os.path.getsize(file_path)
        return response

    process_download(request.request_id, file_obj)

    return HttpResponse("file is being processed for the download")


def test(request):
    print(request.request_id)
    return HttpResponse(f"this was a test", status=200)


@csrf_protect
@cleanup
def _upload_file(request):
    if request.method == "POST":
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            handle_uploaded_file(request)

    else:
        form = UploadFileForm()
    return render(request, "upload.html", {"form": form})


def proccess_streamkey(request_id, file_obj):
    request_dir = create_temp_request_dir(request_id)
    file_dir = create_temp_file_dir(request_dir, file_obj.id)

    key_file_path = os.path.join(file_dir, "enc.key")

    with open(key_file_path, 'wb+') as file:
        file.write(file_obj.key)
        # Move the file cursor to the beginning before reading
        file.seek(0) #  vevy important
        file_content = file.read()

    response = HttpResponse(file_content, content_type='application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="key.enc"'
    return response


@cleanup
def streamkey(request, file_id):
    try:
        file_obj = File.objects.get(id=file_id)
    except File.DoesNotExist:
        return HttpResponse(f"doesn't exist", status=404)

    if not file_obj.streamable:
        return HttpResponse(f"This file is not streamable!", status=404)

    response = proccess_streamkey(request.request_id, file_obj)
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
                       uri=f"https://pamparampam.dev/stream/{file_obj.id}/key")

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


@cleanup
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
