import traceback
from datetime import timedelta
from io import BytesIO
from itertools import groupby

import rawpy
import requests
from PIL import Image
from celery.utils.log import get_task_logger
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from .helper import send_message
from ..celery import app
from ..constants import MAX_RAW_IMAGE_SIZE_ALLOWED_FOR_CONVERSION, EventCode, MAX_DISCORD_MESSAGE_SIZE, MAX_ATTACHMENTS_PER_MESSAGE, MAX_RAW_EXTRACTION_ATTEMPTS
from ..core.Serializers import FileSerializer
from ..core.crypto.Decryptor import Decryptor
from ..core.crypto.Encryptor import Encryptor
from ..core.dataModels.http import RequestContext
from ..core.errors import FailedToParseRawImage
from ..discord.Discord import discord
from ..models import (Folder, Fragment, File, DiscordSettings)
from ..models.other_models import RawExtractionClaim
from ..services import folder_service, file_service, create_file_service
from ..websockets.utils import send_event

logger = get_task_logger(__name__)

RAW_EXTRACTION_BATCH_SIZE = 25
RAW_EXTRACTION_STALE_TIMEOUT = 30

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

@app.task(expires=2)
def prefetch_next_fragments(fragment_id: str, number_to_prefetch: int):
    fragment = Fragment.objects.get(id=fragment_id)
    fragments = Fragment.objects.filter(file=fragment.file)

    filtered_fragments = fragments.filter(sequence__gt=fragment.sequence).order_by('sequence')[:number_to_prefetch]

    for fragment in filtered_fragments:
        discord.get_attachment_url(user=fragment.file.owner, resource=fragment)


def format_shutter(speed: float | None) -> str:
    if speed is None:
        return ""

    if speed >= 1:
        return f"{speed:.1f}s"

    denominator = round(1 / speed)
    return f"1/{denominator}s"


def format_aperture(aperture: float | None) -> str:
    if aperture is None:
        return ""

    return f"f/{aperture:g}"

def _extract_raw_metadata(other, lens) -> dict:
    try:
        return {
            "iso": str(other.iso_speed) if other.iso_speed is not None else "",
            "shutter": format_shutter(other.shutter_speed),
            "aperture": format_aperture(other.aperture),
            "focal_length": str(other.focal_length) if other.focal_length is not None else "",
            "camera": lens.model if lens and lens.model else "",
            "camera_owner": other.artist if other.artist else "",
        }
    except Exception as e:
        logger.warning("FailedToParseRawImage")
        raise FailedToParseRawImage(e)

def _download_and_decrypt_fragments(file_obj):
    raw_buffer = BytesIO()
    fragments = file_obj.fragments.all().order_by("sequence")
    decryptor = Decryptor(method=file_obj.get_encryption_method(), key=file_obj.key, iv=file_obj.iv)
    for frag in fragments:
        url = discord.get_attachment_url(file_obj.owner, frag)
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        raw_buffer.write(decryptor.decrypt(r.content))

    raw_buffer.seek(0)
    return raw_buffer


def _process_raw_to_webp(raw_buffer):
    with rawpy.imread(raw_buffer) as raw:
        rgb = raw.postprocess(use_camera_wb=True, half_size=True)
        metadata = _extract_raw_metadata(raw.other, raw.lens)

    img = Image.fromarray(rgb)
    img.thumbnail((1920, 1080))
    webp_buffer = BytesIO()
    img.save(webp_buffer, format="WEBP", quality=80)
    thumbnail_bytes = webp_buffer.getvalue()
    return thumbnail_bytes, metadata


def _encrypt_thumbnail(data, file_obj: File):
    method = file_obj.get_encryption_method()
    key = Encryptor.generate_key(method)
    iv = Encryptor.generate_iv(method)
    encryptor = Encryptor(method, key=key, iv=iv)
    encrypted = encryptor.encrypt(data)
    return encrypted, encryptor.get_base64_key(), encryptor.get_base64_iv(), len(encrypted)


def _save_thumbnail_and_metadata(user, file_obj: File, thumbnail_info: dict, metadata: dict):
    create_file_service.create_or_edit_thumbnail(user, file_obj, thumbnail_info)
    file_service.create_raw_metadata(file_obj, metadata)
    file_obj.remove_cache()
    send_event(
        RequestContext.from_user(file_obj.owner.id),
        file_obj.parent,
        EventCode.ITEM_UPDATE,
        FileSerializer.serialize_object(file_obj)
    )


def _handle_parse_failure(file_obj: File):
    meta = file_service.create_raw_metadata(
        file_obj,
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
    file_obj.remove_cache()


def _flush_uploads(user, state):
    if not state["upload_queue"]:
        return

    resp = discord.send_files_webhook(user, state["upload_queue"])
    attachments = resp["attachments"]

    for (file_obj, enc_key, enc_iv, size, metadata), att in zip(state["upload_map"], attachments):
        thumbnail_info = {
            "channel_id": resp["channel_id"],
            "message_id": resp["id"],
            "attachment_id": att["id"],
            "message_author_id": resp["author"]["id"],
            "key": enc_key,
            "iv": enc_iv,
            "size": size
        }
        _save_thumbnail_and_metadata(user, file_obj, thumbnail_info, metadata)

    state["upload_queue"].clear()
    state["upload_map"].clear()
    state["current_size"] = 0


def _flush_uploads_and_clear_claims(owner, state):
    file_ids = [file_obj.id for file_obj, *_ in state["upload_map"]]

    try:
        _flush_uploads(owner, state)
    except Exception as e:
        logger.exception(f"Failed to flush raw thumbnail uploads for owner {owner.id}: {e}")
        _mark_raw_extraction_failed(file_ids, str(e))

        state["upload_queue"].clear()
        state["upload_map"].clear()
        state["current_size"] = 0
        return

    RawExtractionClaim.objects.filter(file_id__in=file_ids).delete()

def _claim_raw_image_files():
    now = timezone.now()
    cutoff = now - timedelta(minutes=RAW_EXTRACTION_STALE_TIMEOUT)

    candidate_ids = list(
        File.objects
        .filter(
            type="Raw image",
            thumbnail__isnull=True,
            rawmetadata__isnull=True,
            inTrash=False,
            parent__inTrash=False,
        )
        .filter(
            Q(rawextractionclaim__isnull=True) |
            Q(
                rawextractionclaim__state=RawExtractionClaim.State.FAILED,
                rawextractionclaim__attempts__lt=MAX_RAW_EXTRACTION_ATTEMPTS,
            ) |
            Q(
                rawextractionclaim__state=RawExtractionClaim.State.RUNNING,
                rawextractionclaim__claimed_at__lt=cutoff,
                rawextractionclaim__attempts__lt=MAX_RAW_EXTRACTION_ATTEMPTS,
            )
        )
        .order_by("owner_id", "id")
        .values_list("id", flat=True)[:RAW_EXTRACTION_BATCH_SIZE]
    )

    claimed_ids = []

    for file_id in candidate_ids:
        try:
            with transaction.atomic():
                file_obj = (
                    File.objects
                    .select_for_update(skip_locked=True)
                    .filter(id=file_id)
                    .first()
                )

                if file_obj is None:
                    continue

                file_still_needs_work = (
                    File.objects
                    .filter(
                        id=file_id,
                        type="Raw image",
                        thumbnail__isnull=True,
                        rawmetadata__isnull=True,
                        inTrash=False,
                        parent__inTrash=False,
                    )
                    .exists()
                )

                if not file_still_needs_work:
                    continue

                claim, created = (
                    RawExtractionClaim.objects
                    .select_for_update()
                    .get_or_create(
                        file_id=file_id,
                        defaults={
                            "state": RawExtractionClaim.State.RUNNING,
                            "claimed_at": now,
                            "attempts": 1,
                            "last_error": None,
                        },
                    )
                )

                if not created:
                    if claim.attempts >= MAX_RAW_EXTRACTION_ATTEMPTS:
                        continue

                    if claim.state == RawExtractionClaim.State.RUNNING and claim.claimed_at >= cutoff:
                        continue

                    claim.state = RawExtractionClaim.State.RUNNING
                    claim.claimed_at = now
                    claim.attempts += 1
                    claim.last_error = None
                    claim.save(update_fields=["state", "claimed_at", "attempts", "last_error"])

                claimed_ids.append(file_id)

        except IntegrityError:
            continue

    return list(
        File.objects
        .filter(id__in=claimed_ids)
        .select_related("owner")
        .order_by("owner_id", "id")
    )


def _mark_raw_extraction_failed(file_ids: list[str], error: str):
    RawExtractionClaim.objects.filter(file_id__in=file_ids).update(
        state=RawExtractionClaim.State.FAILED,
        last_error=str(error)[:2000],
    )


def _clear_raw_extraction_claim(file_obj: File):
    RawExtractionClaim.objects.filter(file=file_obj).delete()


def _handle_parse_failure_and_clear_claim(file_obj: File):
    _handle_parse_failure(file_obj)
    _clear_raw_extraction_claim(file_obj)

@app.task()
def generate_raw_image_thumbnails():
    files = _claim_raw_image_files()

    files_by_owner_id = {
        owner_id: list(group)
        for owner_id, group in groupby(files, key=lambda f: f.owner_id)
    }

    for owner_id, owner_files in files_by_owner_id.items():
        owner = owner_files[0].owner
        settings = DiscordSettings.objects.get(user=owner)

        state = {
            "upload_queue": [],
            "upload_map": [],
            "current_size": 0,
        }

        for file_obj in owner_files:
            if file_obj.size > MAX_RAW_IMAGE_SIZE_ALLOWED_FOR_CONVERSION:
                _mark_raw_extraction_failed([file_obj.id], "Raw image too large for conversion")
                _handle_parse_failure_and_clear_claim(file_obj)
                continue

            try:
                raw_buffer = _download_and_decrypt_fragments(file_obj)
                thumbnail_bytes, metadata = _process_raw_to_webp(raw_buffer)
                encrypted, key_b64, iv_b64, enc_size = _encrypt_thumbnail(thumbnail_bytes, file_obj)

                if len(state["upload_queue"]) >= MAX_ATTACHMENTS_PER_MESSAGE or state["current_size"] + enc_size > MAX_DISCORD_MESSAGE_SIZE:
                    _flush_uploads_and_clear_claims(owner, state)

                state["upload_queue"].append((settings.attachment_name, encrypted))
                state["upload_map"].append((file_obj, key_b64, iv_b64, enc_size, metadata))
                state["current_size"] += enc_size

            except FailedToParseRawImage as e:
                logger.warning(f"Failed to parse raw file {file_obj.id}: {e}")
                _handle_parse_failure_and_clear_claim(file_obj)

            except Exception as e:
                logger.exception(f"Unexpected error processing raw file {file_obj.id}: {e}")
                _mark_raw_extraction_failed([file_obj.id], str(e))

        if state["upload_queue"]:
            _flush_uploads_and_clear_claims(owner, state)

    generate_raw_image_thumbnails.delay()
