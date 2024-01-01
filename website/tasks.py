import os
import random
import shutil
import subprocess
import time
import traceback
import uuid
from functools import partial
from pathlib import Path

import requests
from asgiref.sync import async_to_sync, sync_to_async
from celery.utils.log import get_task_logger
from channels.layers import get_channel_layer
from cryptography.fernet import Fernet
from django.db import transaction

from website.celery import app
from website.models import File, Fragment, Folder
from website.utilities.Discord import discord
from website.utilities.merge import Merge
from website.utilities.other import create_temp_request_dir, create_temp_file_dir, calculate_time, get_percentage
from website.utilities.split import Split
from threading import Lock

logger = get_task_logger(__name__)

MAX_MB = 25
MAX_STREAM_MB = 24

lock = Lock()

def send_message(message, user_id, request_id):
    with lock:
        channel_layer = get_channel_layer()

        async_to_sync(channel_layer.group_send)(
            'test',
            {
                'type': 'chat_message',
                'user_id': user_id,
                'message': message,
                'request_id': request_id
            }
        )


@app.task
def delete_file_task(user, request_id, file_id):
    user = user  # TODO
    user = 1
    try:
        file_obj = File.objects.get(id=file_id)

        send_message("Deleting file...", user, request_id)

        fragments = Fragment.objects.filter(file=file_obj)
        if fragments:
            file_obj.ready = False
            file_obj.save()
            for i, fragment in enumerate(fragments, start=1):
                discord.remove_message(fragment.message_id)
                send_message(f"Deleting... {get_percentage(i, len(fragments))}%", user, request_id)

                fragment.delete()

        if file_obj.m3u8_message_id:  # remove m3u8 manifest file
            discord.remove_message(file_obj.m3u8_message_id)

        file_obj.delete()
        send_message(f"Deleted!", user, request_id)
    except Exception:
        traceback.print_exc()

@app.task
def delete_folder_task(user, request_id, folder_id):
    user = user  # TODO
    user = 1
    try:
        folder_obj = Folder.objects.get(id=folder_id)
        send_message("Deleting folder...", user, request_id)

        files = File.objects.filter(parent=folder_obj)
        if files:
            folder_obj.ready = False
            for i, file in enumerate(files, start=1):
                delete_file_task(user, request_id, file.id)
                send_message(f"Deleting... {get_percentage(i, len(files))}%", user, request_id)

        folder_obj.delete()
        send_message(f"Deleted!", user, request_id)
    except Exception:
        traceback.print_exc()


def upload_files_from_folder(user, request_id, path, file_obj):
    send_message(f"Uploading file...", user, request_id)
    file_count = len(os.listdir(path))
    for i, filename in enumerate(sorted(os.listdir(path)), start=1):

        file_path = os.path.join(path, filename)
        if os.path.isfile(file_path):
            extension = Path(file_path).suffix
            size = os.path.getsize(file_path)
            with open(file_path, 'rb') as file:

                name = Path(file_path).stem

                file_name = name + extension

                files = {'file': (file_name, file, 'application/octet-stream')}
                response = discord.send_file(files)
                message_id = response.json()["id"]

                if extension == ".m3u8":
                    file_obj.m3u8_message_id = message_id
                    file_obj.save()

                else:
                    fragment_obj = Fragment(
                        sequence=name,
                        file=file_obj,
                        size=size,
                        message_id=message_id,
                    )
                    fragment_obj.save()

            os.remove(file_path)
            send_message(f"Uploading file...{get_percentage(i, file_count)}%", user, request_id)


def merge_callback(path, size, key, user, request_id):
    send_message(f"File is ready to download!", user, request_id)

    print("merge finished")


@app.task
def process_download(user, request_id, file_id):
    user = user  # TODO
    user = 1
    request_dir = create_temp_request_dir(request_id)
    try:
        file_obj = File.objects.get(id=file_id)

        fragments = Fragment.objects.filter(file=file_obj)
        file_dir = create_temp_file_dir(request_dir, file_obj.id)

        send_message("Processing download...", user, request_id)
        download_file_path = os.path.join("temp", "downloads",
                                          str(file_obj.id))  # temp/downloads/file_id/name.extension
        file_path = os.path.join(download_file_path, file_obj.name)

        if os.path.isfile(file_path):  # we need to check if a process before us didn't already do a job for us :3
            send_message(f"File is ready to download!", user, request_id)
            return

        if fragments:

            for i, fragment in enumerate(fragments, start=1):
                url = discord.get_file_url(fragment.message_id)
                response = requests.get(url)

                with open(os.path.join(file_dir, str(fragment.sequence)), 'wb') as file:
                    file.write(response.content)
                send_message(f"Downloading {get_percentage(i, len(fragments))}%", user, request_id)

            if not os.path.exists(download_file_path):
                os.makedirs(download_file_path)

            send_message(f"Merging download", user, request_id)

            merge = Merge(file_dir, download_file_path, file_obj.name)
            merge.manfilename = "0"  # handle manifest UwU
            merge.merge(cleanup=True, key=file_obj.key, user=user, request_id=request_id, callback=merge_callback)

    except Exception:
        traceback.print_exc()
    finally:
        shutil.rmtree(request_dir)

@app.task
def handle_uploaded_file(user, request_id, file_id, request_dir, file_dir, file_name, file_size, folder_id):
    try:
        user = user  # TODO
        user = 1
        send_message(f"Processing file...", user, request_id)

        split_required = False

        extension = Path(file_name).suffix

        file_obj = File(
            extension=extension,
            name=file_name,
            id=file_id,
            streamable=False,
            size=file_size,
            owner_id=user,
            parent_id=folder_id,
        )

        file_obj.save()
        file_path = os.path.join(file_dir, file_name)

        # ffmpeg doesn't like spaces in file names :(
        new_file_path = file_path.replace(" ", "")
        os.rename(file_path, new_file_path)
        file_path = new_file_path

        if extension == ".mp4":
            try:

                result = subprocess.run(
                    f"ffprobe -v quiet -select_streams v:0 -show_entries stream=bit_rate -of default=noprint_wrappers=1:nokey=1 {file_path}",
                    check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

                #  don't ask me why we multiply it by 900 bytes and not 1024, it just works(mostly)
                calculated_time = calculate_time(MAX_STREAM_MB * 900 * 900, int(result.stdout.strip()))

                ffmpeg_command = [
                    'ffmpeg',
                    '-i', file_path,
                    '-c', 'copy',
                    '-start_number', '0',
                    '-hls_enc', '1',
                    '-hls_time', f'{calculated_time}',
                    '-hls_list_size', '0',
                    '-f', 'hls',
                    '-hls_base_url', f'UwU :3',  # TODO change it back later'
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
                os.remove(file_path)  # removing original file, as we have it split already

                file_obj.streamable = True
                file_obj.save()
            except subprocess.CalledProcessError:
                print(traceback.print_exc())
                send_message(f"Error occurred, can't make it streamable :(", user, request_id)
                split_required = True

        if split_required or extension != ".mp4":
            key = Fernet.generate_key()
            file_obj.key = key

            file_obj.save()

            out_file_path = os.path.join(file_dir, str(file_id) + extension)

            with open(file_path, "rb") as fin, open(out_file_path, "wb") as fout:
                while True:
                    block = fin.read(524288)
                    if not block:
                        break
                    f = Fernet(key)
                    output = f.encrypt(block)
                    fout.write(output)

            os.remove(file_path)  # removing unencrypted file

            encrypted_size = os.path.getsize(out_file_path)

            file_obj.encrypted_size = encrypted_size
            file_obj.save()

            split = Split(out_file_path, file_dir)
            split.manfilename = "0"
            split.bysize(MAX_MB * 1024 * 1023)

            os.remove(out_file_path)  # removing encrypted file as it's already split, and not needed
        transaction.on_commit(partial(upload_files_from_folder, user=user, request_id=request_id, path=file_dir, file_obj=file_obj))
        file_obj.ready = True
        file_obj.save()
        send_message(f"File uploaded!", user, request_id)

    except Exception:
        traceback.print_exc()

    finally:
        shutil.rmtree(request_dir)

@app.task
def test_task():
    file_obj = File.objects.get(id="5d47d2a6-e68d-4d00-b238-e16dc23185ec")
    time.sleep(5)
    file_obj.name = str(random.randint(10, 1000))
    time.sleep(1)

    file_obj.save()
    file_obj = File.objects.get(id="d90502dd-d56e-42d8-8de0-c2b8cb92a271")
    time.sleep(1)

    file_obj.name = str(random.randint(10, 1000))
    file_obj.save()
    file_id = uuid.uuid4()
    time.sleep(1)

    file_obj = File(
        extension="test",
        name="lol",
        streamable=False,
        size=1000,
        id=file_id,
        owner_id=1,
        parent_id="459d3567-b667-40bc-a27d-38eb0b173c06",
    )
    time.sleep(1)

    file_obj.save()

    time.sleep(1)
