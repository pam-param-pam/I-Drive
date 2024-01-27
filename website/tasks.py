import io
import os
import shutil
import subprocess
import traceback
from functools import partial
from pathlib import Path

import requests
from asgiref.sync import async_to_sync
from celery import shared_task
from celery.utils.log import get_task_logger
from channels.layers import get_channel_layer
from cryptography.fernet import Fernet
from django.db import transaction

from website.celery import app
from website.models import File, Fragment, Folder
from website.utilities.Discord import discord, DiscordError
from website.utilities.merge import Merge
from website.utilities.other import create_temp_request_dir, create_temp_file_dir, calculate_time, get_percentage
from website.utilities.split import Split

logger = get_task_logger(__name__)

MAX_MB = 25  # todo
MAX_STREAM_MB = 24


# thanks to this genius - https://github.com/django/channels/issues/1799#issuecomment-1219970560
@shared_task(bind=True, name='queue_ws_event', ignore_result=True, queue='wsQ')
def queue_ws_event(self, ws_channel, ws_event: dict, group=True):  # yes this self arg is needed - no, don't ask me why
    channel_layer = get_channel_layer()
    if group:
        async_to_sync(channel_layer.group_send)(ws_channel, ws_event)
    else:
        async_to_sync(channel_layer.send)(ws_channel, ws_event)


def send_message(message, finished, user_id, request_id, isError=False):
    queue_ws_event.delay(
        'test',
        {
            'type': 'chat_message',
            'user_id': user_id,
            'message': message,
            'finished': finished,
            'error': isError,
            'request_id': request_id
        }
    )


@app.task
def delete_file_task(user, request_id, file_id):
    try:
        file_obj = File.objects.get(id=file_id)
        file_obj.ready = False
        file_obj.save()
        send_message("Deleting file...", False, user, request_id)

        fragments = Fragment.objects.filter(file=file_obj)
        if fragments:

            for i, fragment in enumerate(fragments, start=1):
                try:
                    discord.remove_message(fragment.message_id)
                except DiscordError:
                    send_message(str(DiscordError), False, user, request_id, True)

                send_message(f"Deleting... {get_percentage(i, len(fragments))}%", False, user, request_id)

                fragment.delete()

        if file_obj.m3u8_message_id:  # remove m3u8 manifest file
            try:
                discord.remove_message(file_obj.m3u8_message_id)
            except DiscordError:
                send_message(str(DiscordError), False, user, request_id, True)
        file_obj.delete()
        send_message(f"Deleted!", user, True, request_id)
    except Exception as e:
        send_message(str(e), False, user, request_id, True)

        traceback.print_exc()


@app.task
def delete_folder_task(user, request_id, folder_id):
    try:
        folder_obj = Folder.objects.get(id=folder_id)
        send_message("Deleting folder...", False, user, request_id)

        files = File.objects.filter(parent=folder_obj)
        if files:
            for i, file in enumerate(files, start=1):
                delete_file_task(user, request_id, file.id)
                send_message(f"Deleting... {get_percentage(i, len(files))}%", False, user, request_id)

        folder_obj.delete()
        send_message(f"Deleted!", user, True, request_id)
    except Exception as e:
        send_message(str(e), False, user, request_id, True)

        traceback.print_exc()


def merge_callback(path, size, key, user, request_id):
    send_message(f"File is ready to download!", False, user, request_id)

    print("merge finished")


@app.task
def process_download(user, request_id, file_id):
    request_dir = create_temp_request_dir(request_id)
    try:
        file_obj = File.objects.get(id=file_id)

        fragments = Fragment.objects.filter(file=file_obj)
        file_dir = create_temp_file_dir(request_dir, file_obj.id)

        send_message("Processing download...", False, user, request_id)
        download_file_path = os.path.join("temp", "downloads",
                                          str(file_obj.id))  # temp/downloads/file_id/name.extension
        file_path = os.path.join(download_file_path, file_obj.name)

        if os.path.isfile(file_path):  # we need to check if a process before us didn't already do a job for us :3
            send_message(f"File is ready to download!", False, user, request_id)
            return

        if fragments:

            for i, fragment in enumerate(fragments, start=1):
                url = discord.get_file_url(fragment.message_id)
                response = requests.get(url)

                with open(os.path.join(file_dir, str(fragment.sequence)), 'wb') as file:
                    file.write(response.content)
                send_message(f"Downloading {get_percentage(i, len(fragments))}%", False, user, request_id)

            if not os.path.exists(download_file_path):
                os.makedirs(download_file_path)

            send_message(f"Merging download", False, user, request_id)

            merge = Merge(file_dir, download_file_path, file_obj.name)
            merge.manfilename = "0"  # handle manifest UwU
            merge.merge(cleanup=True, key=file_obj.key, user=user, request_id=request_id, callback=merge_callback)

    except Exception as e:
        send_message(str(e), False, user, request_id, True)

        traceback.print_exc()
    finally:
        shutil.rmtree(request_dir)


def upload_files_from_folder(user, request_id, path, file_obj):
    send_message(f"Uploading file...", False, user, request_id)

    file_count = len(os.listdir(path))
    fernet = Fernet(file_obj.key)
    for i, filename in enumerate(sorted(os.listdir(path)), start=1):

        file_path = os.path.join(path, filename)
        if os.path.isfile(file_path):
            extension = Path(file_path).suffix
            size = os.path.getsize(file_path)
            with open(file_path, 'rb') as file:
                file_content = file.read()
                encrypted_content = fernet.encrypt(file_content)
                encrypted_file = io.BytesIO(encrypted_content)
                encrypted_size = len(encrypted_content)
                name = Path(file_path).stem
                if name == "0":
                    continue
                file_name = name + extension
                print(f"sending file of size: {encrypted_size}")
                files = {'file': (file_name, file_content, 'application/octet-stream')}
                response = discord.send_file(files)
                message_id = response.json()["id"]

                fragment_obj = Fragment(
                    sequence=name,
                    file=file_obj,
                    size=size,
                    encrypted_size=encrypted_size,
                    message_id=message_id,
                )
                fragment_obj.save()

            os.remove(file_path)
            send_message(f"Uploading file...{get_percentage(i, file_count)}%", False, user, request_id)


@app.task
def handle_uploaded_file(user, request_id, file_id, request_dir, file_dir, file_name, file_size, folder_id):
    try:

        user = 1  # todo
        send_message(f"Processing file...", False, user, request_id)

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

        key = Fernet.generate_key()
        file_obj.key = key
        file_obj.save()

        split = Split(file_path, file_dir)
        split.manfilename = "0"
        split.bysize(MAX_MB * 1024 * 1023)

        os.remove(file_path)
        #os.remove(os.path.join(file_dir, "0"))  # removing manifest file from split

        upload_files_from_folder(user=user, request_id=request_id, path=file_dir, file_obj=file_obj)

        file_obj.ready = True
        file_obj.save()
        send_message(f"File uploaded!", True, user, request_id)

    except Exception as e:
        send_message(str(e), False, user, request_id, True)

        traceback.print_exc()

    finally:
        #shutil.rmtree(request_dir)
        pass