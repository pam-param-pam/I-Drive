import os
import random
import shutil
import subprocess
import traceback
import uuid
from pathlib import Path

import httpx
import m3u8
import requests
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt, csrf_protect

from website.forms import UploadFileForm
from website.models import File, Fragment
from website.utilities.merge import Merge
from website.utilities.split import Split

BOT_TOKEN = "ODk0NTc4MDM5NzI2NDQwNTUy.GAqXhm.8M61gjcKM5d6krNf6oWBOt1ZSVmpO5PwPoGVa4"
BASE_URL = 'https://discord.com/api/v10'
channel_id = '870781149583130644'


# TODO handle discord rate limiting
@csrf_exempt
def upload_file(request):
    # request.upload_handlers.insert(0, ProgressBarUploadHandler(request))
    return _upload_file(request)


def get_file_url(message_id):
    url = f'{BASE_URL}/channels/{channel_id}/messages/{message_id}'
    headers = {'Authorization': f'Bot {BOT_TOKEN}'}

    with httpx.Client() as client:
        response = client.get(url, headers=headers)

    return response.json()["attachments"][0]["url"]


def upload_files_from_folder(path, file_obj):
    with httpx.Client(timeout=None) as client:
        for filename in os.listdir(path):
            file_path = os.path.join(path, filename)
            if os.path.isfile(file_path):
                extension = Path(file_path).suffix

                url = f'{BASE_URL}/channels/{channel_id}/messages'
                headers = {'Authorization': f'Bot {BOT_TOKEN}'}

                with open(file_path, 'rb') as file:

                    name = Path(file_path).stem

                    file_name = name + extension

                    files = {'file': (file_name, file, 'application/octet-stream')} # todo make it so discord cant see original file name
                    response = client.post(url, headers=headers, files=files)
                    if response.status_code == 429:
                        print(response.headers)
                        print(response.text)
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


def create_temp_request_dir():
    upload_folder = os.path.join("temp", str(random.randint(0, 100000)))
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
    return upload_folder


def create_temp_file_dir(upload_folder, file_id):
    out_folder_path = os.path.join(upload_folder, str(file_id))
    if not os.path.exists(out_folder_path):
        os.makedirs(out_folder_path)
    return out_folder_path


def handle_uploaded_file(f):
    try:
        request_dir = create_temp_request_dir()  # creating /temp/<int>/
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
            result = subprocess.run(
                f"ffprobe -v quiet -select_streams v:0 -show_entries stream=bit_rate -of default=noprint_wrappers=1:nokey=1 {file_path}",
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

            calculated_time = calculate_time(23 * 900 * 900, int(result.stdout.strip()))

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

        else:

            split = Split(file_path, file_dir)
            split.manfilename = "0"
            split.bysize(1 * 1024 * 1023)

        os.remove(file_path)
        upload_files_from_folder(file_dir, file_obj)

    except Exception as e:
        # TODO REPORT EROR
        print(f"Error: {e}")
        traceback.print_exc()
    finally:
        try:
            shutil.rmtree(request_dir)
        except:
            pass


def download_callback(filename, size):
    print("download finished")


def index(request):
    return HttpResponse("hello")

def process_download(file_obj):
    fragments = Fragment.objects.filter(file=file_obj)
    request_dir = create_temp_request_dir()
    file_dir = create_temp_file_dir(request_dir, file_obj.id)

    if fragments:
        for fragment in fragments:
            url = get_file_url(fragment.message_id)

            response = requests.get(url)
            with open(os.path.join(file_dir, str(fragment.sequence)), 'wb') as file:
                file.write(response.content)
        merge = Merge(file_dir, file_dir, file_obj.name)
        merge.manfilename = "0"  # handle manifest UwU
        merge.merge(cleanup=True, callback=download_callback)

def download(request, file_id):
    try:
        file_obj = File.objects.get(id=file_id)
    except File.DoesNotExist:
        return HttpResponse(f"doesn't exist", status=404)
    if file_obj.streamable:
        return HttpResponse(f"This file is not downloadable on this endpoint, use m3u8 file", status=404)

    process_download(file_obj)

    return HttpResponse("file is being processed for the download")


def test(request):
    return render(request, "index.html")


@csrf_protect
def _upload_file(request):
    if request.method == "POST":
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            handle_uploaded_file(request.FILES["file"])

    else:
        form = UploadFileForm()
    return render(request, "upload.html", {"form": form})


def streamkey(request, file_id):
    try:
        file_obj = File.objects.get(id=file_id)
    except File.DoesNotExist:
        return HttpResponse(f"doesn't exist", status=404)

    request_dir = create_temp_request_dir()
    file_dir = create_temp_file_dir(request_dir, file_id)

    key_file_path = os.path.join(file_dir, "enc.key")

    with open(key_file_path, 'wb+') as file:
        file.write(file_obj.key)
        # Move the file cursor to the beginning before reading
        file.seek(0)
        file_content = file.read()

    response = HttpResponse(file_content, content_type='application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="key.enc"'
    return response

def process_m3u8(file_obj):
    file_url = get_file_url(file_obj.m3u8_message_id)

    request_dir = create_temp_request_dir()
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
        url = get_file_url(fragment.message_id)
        segment.uri = url
        segment.key = new_key

    playlist.keys[-1] = new_key

    playlist.dump(m3u8_file_path)
    with open(m3u8_file_path, 'rb') as file:
        file_content = file.read()

    shutil.rmtree(file_dir)

    return file_content
def get_m3u8(request, file_id):
    try:
        file_obj = File.objects.get(id=file_id)
    except File.DoesNotExist:
        return HttpResponse(f"doesn't exist", status=404)

    file_content = process_m3u8(file_obj)

    response = HttpResponse(file_content, content_type='application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="manifest.m3u8"'

    return response
