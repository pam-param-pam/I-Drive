import os
import tempfile
import traceback
from io import BytesIO

import exifread
import rawpy
import requests
from PIL import Image
from celery.utils.log import get_task_logger

from .helper import send_message
from ..celery import app
from ..constants import MAX_RAW_IMAGE_SIZE_ALLOWED_FOR_CONVERSION, EventCode, MAX_DISCORD_MESSAGE_SIZE
from ..core.Serializers import FileSerializer
from ..core.crypto.Decryptor import Decryptor
from ..core.crypto.Encryptor import Encryptor
from ..core.dataModels.http import RequestContext
from ..core.errors import FailedToParseRawImage
from ..discord.Discord import discord
from ..models import (Folder, Fragment, File, DiscordSettings)
from ..services import folder_service, file_service, create_file_service
from ..websockets.utils import send_event

logger = get_task_logger(__name__)

@app.task
def lock_folder_task(context: dict, folder_id: str, password: str):
    if not password:
        raise ValueError("Password cannot be None")
    try:
        context = RequestContext.deserialize(context)
        folder = Folder.objects.get(id=folder_id)
        folder_service.internal_apply_lock(folder=folder, lock_from=folder, password=password)
        send_message("toasts.passwordUpdated", args=None, finished=True, context=context)
    except Exception as e:
        traceback.print_exc()
        send_message(message=str(e), args=None, finished=True, context=context, isError=True)

@app.task
def unlock_folder_task(context: dict, folder_id: str):
    try:
        context = RequestContext.deserialize(context)
        folder = Folder.objects.get(id=folder_id)
        folder_service.internal_remove_lock(folder=folder, lock_from=folder.lockFrom)
        send_message("toasts.passwordUpdated", args=None, finished=True, context=context)
    except Exception as e:
        traceback.print_exc()
        send_message(message=str(e), args=None, finished=True, context=context, isError=True)

@app.task(expires=5)
def prefetch_next_fragments(fragment_id: str, number_to_prefetch: int):
    fragment = Fragment.objects.get(id=fragment_id)
    fragments = Fragment.objects.filter(file=fragment.file)

    filtered_fragments = fragments.filter(sequence__gt=fragment.sequence).order_by('sequence')[:number_to_prefetch]

    for fragment in filtered_fragments:
        discord.get_attachment_url(user=fragment.file.owner, resource=fragment)


def _extract_raw_metadata(raw_buffer):
    try:
        raw_buffer.seek(0)

        tags = exifread.process_file(raw_buffer, details=False)

        camera = str(tags["Image Model"])
        iso = str(tags["EXIF ISOSpeedRatings"])
        shutter = str(tags["EXIF ExposureTime"]) + " sec"
        aperture = str(tags["EXIF FNumber"]) + "F"
        focal_length = str(tags["EXIF FocalLength"]) + " mm"

        raw_buffer.seek(0)
        logger.warning(
            "EXIF parsed",
            extra={
                "camera": camera,
                "iso": iso,
                "shutter": shutter,
                "aperture": aperture,
                "focal_length": focal_length,
            }
        )
        return camera, iso, shutter, aperture, focal_length, None
    except Exception as e:
        logger.warning("FailedToParseRawImage")
        raise FailedToParseRawImage(e)

@app.task(expires=5)
def generate_raw_image_thumbnails():
    return
    files = File.objects.filter(type="Raw image", thumbnail__isnull=True, rawmetadata__isnull=True, inTrash=False, parent__inTrash=False).select_related("owner")

    state = {
        "upload_queue": [],
        "upload_map": [],
        "current_size": 0
    }

    def flush_uploads(user):
        if not state["upload_queue"]:
            return

        resp = discord.send_files_webhook(user, state["upload_queue"])
        attachments = resp["attachments"]

        for meta, att in zip(state["upload_map"], attachments):
            file_obj, enc_key, enc_iv, size, metadata = meta

            create_file_service.create_or_edit_thumbnail(
                user,
                file_obj,
                {
                    "channel_id": resp["channel_id"],
                    "message_id": resp["id"],
                    "attachment_id": att["id"],
                    "message_author_id": resp["author"]["id"],
                    "key": enc_key,
                    "iv": enc_iv,
                    "size": size
                }
            )

            if metadata:
                camera, iso, shutter, aperture, focal_length, camera_owner = metadata

                file_service.create_raw_metadata(
                    file_obj,
                    {
                        "camera": camera,
                        "camera_owner": camera_owner,
                        "iso": iso,
                        "shutter": shutter,
                        "aperture": aperture,
                        "focal_length": focal_length
                    }
                )

            file_obj.remove_cache()

            send_event(RequestContext.from_user(file_obj.owner.id), file_obj.parent, EventCode.ITEM_UPDATE, FileSerializer().serialize_object(file_obj))

        state["upload_queue"].clear()
        state["upload_map"].clear()
        state["current_size"] = 0

    for file in files:
        if file.size > MAX_RAW_IMAGE_SIZE_ALLOWED_FOR_CONVERSION:
            continue

        try:
            raw_buffer = BytesIO()

            fragments = file.fragments.all().order_by("sequence")

            decryptor = Decryptor(
                method=file.get_encryption_method(),
                key=file.key,
                iv=file.iv
            )

            for frag in fragments:
                url = discord.get_attachment_url(file.owner, frag)

                r = requests.get(url, timeout=30)
                r.raise_for_status()

                raw_buffer.write(decryptor.decrypt(r.content))

            metadata = _extract_raw_metadata(raw_buffer)

            with rawpy.imread(raw_buffer) as raw:
                rgb = raw.postprocess(
                    use_camera_wb=True,
                    half_size=True
                )

            del raw_buffer

            img = Image.fromarray(rgb)
            del rgb

            img.thumbnail((1920, 1080))

            webp_buffer = BytesIO()
            img.save(webp_buffer, format="WEBP", quality=80)

            del img

            data = webp_buffer.getvalue()
            del webp_buffer

            method = file.get_encryption_method()

            key = Encryptor.generate_key(method)
            iv = Encryptor.generate_iv(method)

            encryptor = Encryptor(method, key=key, iv=iv)

            encrypted = encryptor.encrypt(data)
            del data

            settings = DiscordSettings.objects.get(user=file.owner)
            size = len(encrypted)

            # flush before exceeding limits
            if len(state["upload_queue"]) >= 10 or state["current_size"] + size > MAX_DISCORD_MESSAGE_SIZE:
                flush_uploads(file.owner)

            state["upload_queue"].append((settings.attachment_name, encrypted))

            state["upload_map"].append(
                (
                    file,
                    encryptor.get_base64_key(),
                    encryptor.get_base64_iv(),
                    size,
                    metadata
                )
            )

            state["current_size"] += size

        except FailedToParseRawImage:
            meta = file_service.create_raw_metadata(
                file,
                {
                    "camera": "FAILED TO PARSE",
                    "camera_owner": "FAILED TO PARSE",
                    "iso": "FAILED TO PARSE",
                    "shutter": "FAILED TO PARSE",
                    "aperture": "FAILED TO PARSE",
                    "focal_length": "FAILED TO PARSE"
                }
            )

            meta.failed_to_process = True
            meta.save(update_fields=["failed_to_process"])

            file.remove_cache()

    if state["upload_queue"] and files:
        flush_uploads(files[0].owner)
