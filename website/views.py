import os
import random
import secrets
import shutil
import subprocess
from pathlib import Path

import httpx
import m3u8
import requests
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from filesplit.merge import Merge
from filesplit.split import Split

from website.forms import UploadFileForm
from website.models import File, Fragment

BOT_TOKEN = "ODk0NTc4MDM5NzI2NDQwNTUy.GAqXhm.8M61gjcKM5d6krNf6oWBOt1ZSVmpO5PwPoGVa4"
BASE_URL = 'https://discord.com/api/v10'
channel_id = '870781149583130644'


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
                url = f'{BASE_URL}/channels/{channel_id}/messages'
                headers = {'Authorization': f'Bot {BOT_TOKEN}'}

                with open(file_path, 'rb') as file:

                    name = Path(file_path).stem
                    extension = Path(file_path).suffix

                    file_name = name + extension

                    files = {'file': (file_name, file, 'application/octet-stream')}
                    response = client.post(url, headers=headers, files=files)

                    message_id = response.json()["id"]
                    if extension == ".m3u8":
                        file_obj.m3u8_message_id = message_id
                        file_obj.save()
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


def handle_uploaded_file(f):
    upload_folder = os.path.join("temp", str(random.randint(0, 100000)))
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
    with open(os.path.join(upload_folder, f.name), "wb+") as destination:
        for chunk in f.chunks():
            destination.write(chunk)

    aes_key = secrets.token_hex(16)

    extension = Path(f.name).suffix
    file_obj = File(
        extension=extension,
        name=f.name,
        streamable=False,
        size=f.size,
        parent_id="root",
        key=aes_key,
    )

    file_obj.save()

    out_folder_path = os.path.join(upload_folder, str(file_obj.id))
    file_path = os.path.join(upload_folder, f.name)
    if not os.path.exists(out_folder_path):
        os.makedirs(out_folder_path)
    result = subprocess.run(
        f"ffprobe -v quiet -select_streams v:0 -show_entries stream=bit_rate -of default=noprint_wrappers=1:nokey=1 {file_path}",
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

    calculated_time = calculate_time(23 * 900 * 900, int(result.stdout.strip()))

    if extension == ".mp4":
        key_info_file_path = os.path.join(out_folder_path, "enc.keyinfo")
        key_file_path = os.path.join(out_folder_path, "enc.key")
        with open(key_file_path, 'w') as file:
            file.write(aes_key)

        with open(key_info_file_path, 'w') as file:
            file.write(f"https://pamparampam.dev/stream/{file_obj.id}/key\n")
            file.write(key_file_path)

        ffmpeg_command = [
            'ffmpeg',
            '-i', file_path,
            '-c', 'copy',
            '-start_number', '0',
            '-hls_key_info_file', key_info_file_path,
            '-hls_time', f'{calculated_time}',
            '-hls_list_size', '0',
            '-f', 'hls',
            '-hls_base_url', f'https://pamparampam.dev/stream/{file_obj.id}/',
            # '-hls_flags', 'temp_file',  # Use temp_file option
            '-hls_segment_filename', f"{out_folder_path}/%d.ts",
            f'{os.path.join(out_folder_path, "manifest.m3u8")}'
        ]
        subprocess.run(ffmpeg_command, check=True)
        os.remove(key_info_file_path)
        os.remove(key_file_path)

    else:

        split = Split(file_path, out_folder_path)
        split.bysize(5 * 1024 * 1023)

    upload_files_from_folder(out_folder_path, file_obj)

    shutil.rmtree(upload_folder)


def download_callback(filename, size):
    print("download finished")


def index(request):
    return HttpResponse("hello")


def download(request, file_id):
    file_obj = File.objects.get(id=file_id)

    fragments = Fragment.objects.filter(file=file_obj)
    if fragments:  # TODO creating folder based on not secure input
        folder_path = os.path.join("temp")
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        for fragment in fragments:
            print(fragment.file_url)
            response = requests.get(fragment.file_url)
            with open(os.path.join(folder_path, fragment.name), 'wb') as file:
                file.write(response.content)
        merge = Merge(folder_path, "temp", str(file_obj.id))
        merge.merge(cleanup=True, callback=download_callback)
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
        return HttpResponse(f"doesnt exist", status=404)

    return HttpResponse({file_obj.key})

def get_m3u8(request, file_id):
    try:
        file_obj = File.objects.get(id=file_id)
    except File.DoesNotExist:
        return HttpResponse(f"doesnt exist", status=404)
    file_url = get_file_url(file_obj.m3u8_message_id)


    upload_folder = os.path.join("temp", str(random.randint(0, 100000)))
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)

    response = requests.get(file_url, stream=True)
    m3u8_file_path = os.path.join(upload_folder, "manifest.m3u8")
    with open(m3u8_file_path, 'wb') as file:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                file.write(chunk)

    playlist = m3u8.load(m3u8_file_path)

    fragments = Fragment.objects.filter(file_id=file_obj).order_by('sequence')
    for fragment, segment in zip(fragments, playlist.segments.by_key(playlist.keys[-1])):
        url = get_file_url(fragment.message_id)
        segment.uri = url

    playlist.dump(m3u8_file_path)
    with open(m3u8_file_path, 'rb') as file:
        file_content = file.read()
    shutil.rmtree(upload_folder)

    response = HttpResponse(file_content, content_type='application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="manifest.m3u8"'

    return response




