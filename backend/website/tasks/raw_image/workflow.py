from datetime import timedelta
from itertools import groupby

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from website.celery import app
from website.config import MAX_RAW_IMAGE_SIZE_ALLOWED_FOR_CONVERSION, GENERATE_RAW_THUMBNAILS
from website.constants import MAX_ATTACHMENTS_PER_MESSAGE, MAX_DISCORD_MESSAGE_SIZE
from website.core.errors import FailedToParseRawImage
from website.discord.Discord import discord
from website.models import File, DiscordSettings
from website.models.other_models import RawExtractionClaim
from website.services.file_service import file_service
from .processing import _download_and_decrypt_fragments, _process_raw_to_webp, _encrypt_thumbnail


RAW_EXTRACTION_BATCH_SIZE = 25
RAW_EXTRACTION_STALE_TIMEOUT = 30
MAX_RAW_EXTRACTION_ATTEMPTS = 3

FAILED_METADATA = {
    field: "FAILED TO PARSE"
    for field in ("camera", "camera_owner", "iso", "shutter", "aperture", "focal_length")
}


def handle_parse_failure(owner_id: int, file_id: str, claim_attempts: int) -> bool:
    return file_service.complete_raw_image_extraction(
        owner_id, file_id, claim_attempts, FAILED_METADATA, failed=True,
    )


def _flush_uploads(user, state):
    if not state["upload_queue"]:
        return

    resp = discord.send_files_webhook(user, state["upload_queue"])
    attachments = resp["attachments"]

    for (file_obj, claim_attempts, enc_key, enc_iv, size, metadata), att in zip(state["upload_map"], attachments):
        thumbnail_info = {
            "channel_id": resp["channel_id"],
            "message_id": resp["id"],
            "attachment_id": att["id"],
            "message_author_id": resp["author"]["id"],
            "key": enc_key,
            "iv": enc_iv,
            "size": size
        }
        file_service.complete_raw_image_extraction(file_obj.owner_id, str(file_obj.id), claim_attempts, metadata, thumbnail=thumbnail_info)

    state["upload_queue"].clear()
    state["upload_map"].clear()
    state["current_size"] = 0


def _flush_uploads_and_clear_claims(owner, state):
    file_ids = [file_obj.id for file_obj, *_ in state["upload_map"]]

    try:
        _flush_uploads(owner, state)
    except Exception as e:
        _mark_raw_extraction_failed(file_ids, str(e))

        state["upload_queue"].clear()
        state["upload_map"].clear()
        state["current_size"] = 0
        return


def _claim_raw_image_files():
    now = timezone.now()
    cutoff = now - timedelta(minutes=RAW_EXTRACTION_STALE_TIMEOUT)

    candidate_ids = list(
        File.objects
        .filter(
            type="Raw image",
            thumbnail__isnull=True,
            rawmetadata__isnull=True,
            trashed_at__isnull=True,
            parent__trashed_at__isnull=True,
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

    claimed_attempts = {}

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
                        trashed_at__isnull=True,
                        parent__trashed_at__isnull=True,
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

                claimed_attempts[str(file_id)] = claim.attempts

        except IntegrityError:
            continue

    files = list(
        File.objects
        .filter(id__in=claimed_attempts)
        .select_related("owner")
        .order_by("owner_id", "id")
    )
    for file_obj in files:
        file_obj.raw_claim_attempts = claimed_attempts[str(file_obj.id)]
    return files


def _mark_raw_extraction_failed(file_ids: list[str], error: str):
    RawExtractionClaim.objects.filter(file_id__in=file_ids).update(
        state=RawExtractionClaim.State.FAILED,
        last_error=str(error)[:2000],
    )


def _handle_parse_failure_and_clear_claim(file_obj: File):
    handle_parse_failure(file_obj.owner_id, str(file_obj.id), file_obj.raw_claim_attempts)

@app.task(queue="cleanup")
def generate_raw_image_thumbnails():
    if not GENERATE_RAW_THUMBNAILS:
        return

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
                state["upload_map"].append((file_obj, file_obj.raw_claim_attempts, key_b64, iv_b64, enc_size, metadata))
                state["current_size"] += enc_size

            except FailedToParseRawImage:
                _handle_parse_failure_and_clear_claim(file_obj)

            except Exception as e:
                _mark_raw_extraction_failed([file_obj.id], str(e))

        if state["upload_queue"]:
            _flush_uploads_and_clear_claims(owner, state)

    if len(files) > 0:
        generate_raw_image_thumbnails.delay()

