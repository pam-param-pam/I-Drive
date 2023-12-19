import os
import shutil
import subprocess
import time
import traceback
from pathlib import Path

import requests
from asgiref.sync import async_to_sync
from celery.utils.log import get_task_logger
from channels.layers import get_channel_layer
from cryptography.fernet import Fernet

from website.celery import app
from website.models import File, Fragment
from website.utilities.Discord import discord
from website.utilities.merge import Merge
from website.utilities.other import create_temp_request_dir, create_temp_file_dir, calculate_time, get_percentage
from website.utilities.split import Split

logger = get_task_logger(__name__)

MAX_MB = 25
MAX_STREAM_MB = 24


def send_message(message):
    channel_layer = get_channel_layer()

    async_to_sync(channel_layer.group_send)(
        'test',
        {
            'type': 'chat_message',
            # 'user_id': user_id,
            'message': message
        }
    )


@app.task
def delete_files(file_id):
    file_obj = File.objects.get(id=file_id)

    send_message("Deleting files...")

    fragments = Fragment.objects.filter(file=file_obj)
    if fragments:
        for i, fragment in enumerate(fragments, start=1):
            discord.remove_message(fragment.message_id)
            send_message(f"Deleting... {get_percentage(i, len(fragments))}%")

            fragment.delete()

    file_obj.delete()
    send_message(f"Deleted!")


def upload_files_from_folder(path, file_obj):
    send_message(f"Uploading file...")
    file_count = len(os.listdir(path))
    for i, filename in enumerate(sorted(os.listdir(path)), start=1):

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

            os.remove(file_path)
            send_message(f"Uploading file...{get_percentage(i, file_count)}%")


def merge_callback(path, size, key):
    send_message(f"File is ready to download!")

    print("merge finished")


@app.task
def process_download(request_id, file_id):
    request_dir = create_temp_request_dir(request_id)
    try:
        file_obj = File.objects.get(id=file_id)

        fragments = Fragment.objects.filter(file=file_obj)
        file_dir = create_temp_file_dir(request_dir, file_obj.id)

        send_message("Processing download...")
        download_file_path = os.path.join("temp", "downloads",
                                          str(file_obj.id))  # temp/downloads/file_id/name.extension
        file_path = os.path.join(download_file_path, file_obj.name)

        if os.path.isfile(file_path):  # we need to check if a process before us didn't already do a job for us :3
            send_message(f"File is ready to download!")
            return

        if fragments:

            for i, fragment in enumerate(fragments, start=1):
                url = discord.get_file_url(fragment.message_id)
                response = requests.get(url)

                with open(os.path.join(file_dir, str(fragment.sequence)), 'wb') as file:
                    file.write(response.content)
                send_message(f"Downloading {get_percentage(i, len(fragments))}%")


            if not os.path.exists(download_file_path):
                os.makedirs(download_file_path)

            send_message(f"Merging download")

            merge = Merge(file_dir, download_file_path, file_obj.name)
            merge.manfilename = "0"  # handle manifest UwU
            merge.merge(cleanup=True, key=file_obj.key, callback=merge_callback)

    except Exception:
        traceback.print_exc()
    finally:
        shutil.rmtree(request_dir)

@app.task
def handle_uploaded_file(user, request_id, file_id, request_dir, file_dir, file_name, file_size):
    try:
        send_message(f"Processing file...")

        split_required = False
        user = 1
        extension = Path(file_name).suffix
        file_obj = File(
            extension=extension,
            name=file_name,
            id=file_id,
            streamable=False,
            size=file_size,
            owner_id=user,
            # parent_id="root",
        )

        file_obj.save()
        file_path = os.path.join(file_dir, file_name)

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
                # TODO inform user that an error occurred
                split_required = True

        if split_required or extension != ".mp4":
            key = Fernet.generate_key()
            file_obj.key = key

            file_obj.save()

            out_file_path = os.path.join(file_dir, str(file_obj.id) + file_obj.extension)

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

        upload_files_from_folder(file_dir, file_obj)
        send_message(f"File uploaded!")

    except Exception:
        traceback.print_exc()

    finally:
        shutil.rmtree(request_dir)
