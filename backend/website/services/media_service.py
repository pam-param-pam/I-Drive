import base64
import hashlib
from collections import deque
from itertools import batched

from django.contrib.auth import get_user_model

from website.auth.permissions import (
    ResourceAction, SignedResourcePrincipal)
from website.config import MAX_THUMBNAIL_SIZE
from website.constants import cache, MAX_MEDIA_CACHE_AGE
from website.core.converters import param_to_bool
from website.core.crypto.Decryptor import Decryptor
from website.core.errors import BadRequestError, ResourceNotFoundError
from website.core.helpers import validate_key
from website.core.media.stream.sources.DeflateZipEntryByteSource import DeflateZipEntryByteSource
from website.core.media.stream.sources.EmptyByteSource import EmptyByteSource
from website.core.media.stream.sources.FragmentByteSource import FragmentedDiscordByteSource
from website.core.media.stream.sources.ZipByteSource import ZipByteSource
from website.core.media.utils import decrypt_bytes, fetch_discord_file, build_binary_response, build_streaming_response
from website.models import File, Folder, Moment, Subtitle, Thumbnail
from website.queries.selectors import check_if_bots_exists
from website.services import attachment_service, cache_service, zip_service

from website.auth.permissions.authorizer import authorizer


def iter_download_files(principal, item_id, credentials=None):
    root = authorizer.require_download_root(principal, item_id, credentials)
    if root["kind"] == "file":
        yield root
        return
    pending, seen = deque([root["id"]]), {root["id"]}
    while pending:
        parent_ids = [pending.popleft() for _ in range(min(len(pending), 500))]
        parents = authorizer.filter_download_items(
            principal, root["id"], folder_ids=parent_ids, credentials=credentials,
        )
        parent_ids = {row["id"] for row in parents}
        for model, kind in ((File, "file"), (Folder, "folder")):
            ids = model.objects.filter(owner_id=principal.user_id, parent_id__in=parent_ids).order_by("id").values_list("id", flat=True)
            for batch in batched(ids.iterator(chunk_size=500), 500):
                selected = {"folder_ids" if kind == "folder" else "file_ids": list(batch)}
                rows = authorizer.filter_download_items(
                    principal, root["id"], parent_ids=parent_ids, credentials=credentials, **selected,
                )
                for row in rows:
                    if kind == "file":
                        yield row
                    elif row["id"] not in seen:
                        seen.add(row["id"])
                        pending.append(row["id"])


def _authorized_signed_file(principal: SignedResourcePrincipal, *, for_zip: bool = False) -> File:
    action = ResourceAction.STREAM_ZIP_ENTRY if for_zip else ResourceAction.STREAM_FILE
    return authorizer.require_signed_file(principal, action)


def _stable_file_etag(file_obj: File) -> str:
    payload = f"{file_obj.id}:{file_obj.last_modified_at.isoformat()}:{file_obj.size}:{file_obj.crc}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get_thumbnail_response(request, principal: SignedResourcePrincipal, thumbnail_id: str):
    isInline = validate_key(request.GET, "inline", bool, default=False, converter=param_to_bool)
    file_obj = authorizer.require_signed_file(principal, ResourceAction.STREAM_THUMBNAIL)
    try:
        thumbnail = Thumbnail.objects.get(id=thumbnail_id, file_id=file_obj.id)
    except Thumbnail.DoesNotExist as exception:
        raise ResourceNotFoundError() from exception

    cache_key = cache_service.get_thumbnail_key(file_obj.id, file_obj.resource_version)
    thumbnail_content = cache.get(cache_key)

    check_if_bots_exists(file_obj.owner)
    if thumbnail.size > MAX_THUMBNAIL_SIZE:
        raise BadRequestError("Thumbnail too big too stream!")

    if not thumbnail_content:
        decryptor = Decryptor(method=file_obj.get_encryption_method(), key=thumbnail.key, iv=thumbnail.iv)
        url = attachment_service.get_attachment_url(file_obj.owner, thumbnail, file_obj)

        thumbnail_content = decrypt_bytes(fetch_discord_file(url), decryptor)
        cache.set(cache_key, thumbnail_content, timeout=MAX_MEDIA_CACHE_AGE)

    return build_binary_response(
        content=thumbnail_content,
        filename=f"thumbnail_{file_obj.get_name_no_extension()}.webp",
        content_type="image/webp",
        inline=isInline,
        cache_control=f"max-age={MAX_MEDIA_CACHE_AGE}"
    )


def get_moment_response(request, principal: SignedResourcePrincipal, moment_id: str):
    isInline = validate_key(request.GET, "inline", bool, default=False, converter=param_to_bool)
    file_obj = _authorized_signed_file(principal)
    try:
        moment = Moment.objects.get(id=moment_id, file_id=file_obj.id)
    except Moment.DoesNotExist as exception:
        raise ResourceNotFoundError() from exception

    check_if_bots_exists(file_obj.owner)

    decryptor = Decryptor(method=file_obj.get_encryption_method(), key=moment.key, iv=moment.iv)
    url = attachment_service.get_attachment_url(file_obj.owner, moment, file_obj)

    moment_content = decrypt_bytes(fetch_discord_file(url), decryptor)

    return build_binary_response(
        content=moment_content,
        filename=f"moment_{file_obj.get_name_no_extension()}.webp",
        content_type="image/webp",
        inline=isInline,
        cache_control=f"max-age={MAX_MEDIA_CACHE_AGE}"
    )


def get_subtitle_response(request, principal: SignedResourcePrincipal, subtitle_id: str):
    isInline = validate_key(request.GET, "inline", bool, default=False, converter=param_to_bool)
    file_obj = _authorized_signed_file(principal)
    try:
        subtitle = Subtitle.objects.get(id=subtitle_id, file_id=file_obj.id)
    except Subtitle.DoesNotExist as exception:
        raise ResourceNotFoundError() from exception

    check_if_bots_exists(file_obj.owner)

    decryptor = Decryptor(method=file_obj.get_encryption_method(), key=subtitle.key, iv=subtitle.iv)
    url = attachment_service.get_attachment_url(file_obj.owner, subtitle, file_obj)

    subtitle_content = decrypt_bytes(fetch_discord_file(url), decryptor)

    return build_binary_response(
        content=subtitle_content,
        filename=f"subtitle_{file_obj.get_name_no_extension()}.vtt",
        content_type="text/vtt",
        inline=isInline,
        cache_control=f"max-age={MAX_MEDIA_CACHE_AGE}"
    )


def get_file_response(request, principal: SignedResourcePrincipal):
    isInline = validate_key(request.GET, "inline", bool, default=False, converter=param_to_bool)
    raw = validate_key(request.GET, "raw", bool, default=False, converter=param_to_bool)
    file_obj = _authorized_signed_file(principal)

    referer = request.headers.get('Referer')

    fragments = file_obj.fragments.all().order_by("sequence")
    user = file_obj.owner  # without this call it will break lol

    check_if_bots_exists(user)

    if not fragments.exists():
        source = EmptyByteSource()
    else:
        source = FragmentedDiscordByteSource(file_obj=file_obj, fragments=fragments, decrypted=not raw)

    response = build_streaming_response(
        request=request,
        byte_source=source,
        filename=file_obj.name,
        inline=isInline,
        x_frame_from_referer=referer,
        etag=_stable_file_etag(file_obj)
    )
    return response


def get_zip_response(request, principal: SignedResourcePrincipal):
    user_zip, roots, scope = authorizer.require_signed_zip(principal)
    user = get_user_model().objects.filter(id=user_zip.owner_id).first()
    if user is None:
        raise ResourceNotFoundError()

    single_root = len(roots) == 1 and roots[0]["kind"] == "folder"
    zip_name = f"{roots[0]['name'] if single_root else user_zip.name}.zip"
    dict_files = zip_service.iter_zip_entries(principal, roots, scope)

    raw = validate_key(request.GET, "raw", bool, default=False, converter=param_to_bool)
    num_bots = check_if_bots_exists(user)
    source = ZipByteSource(dict_files=dict_files, owner=user, num_bots=num_bots, decrypted=not raw)

    return build_streaming_response(
        request=request,
        byte_source=source,
        filename=zip_name,
        content_type="application/zip",
        etag=user_zip.id,
        cache_control="private, no-store",
    )


def get_zip_entry_response(request, principal: SignedResourcePrincipal):
    file_obj = _authorized_signed_file(principal, for_zip=True)
    isInline = validate_key(request.GET, "inline", bool, default=False, converter=param_to_bool)
    referer = request.headers.get('Referer')

    offset = validate_key(request.GET, "offset", int, converter=int)
    compressed_size = validate_key(request.GET, "compressed_size", int, converter=int)
    uncompressed_size = validate_key(request.GET, "uncompressed_size", int, converter=int)
    compression_method = validate_key(request.GET, "compression_method", int, converter=int)
    filename_b64 = validate_key(request.GET, "filename", str)

    filename = base64.b64decode(filename_b64).decode()
    fragments = file_obj.fragments.all().order_by("sequence")
    user = file_obj.owner

    check_if_bots_exists(user)

    if not fragments.exists():
        source = EmptyByteSource()
    else:
        source = DeflateZipEntryByteSource(file_obj=file_obj, fragments=fragments, offset=offset, compression_method=compression_method, compressed_size=compressed_size,
                                           uncompressed_size=uncompressed_size)

    return build_streaming_response(
        request=request,
        byte_source=source,
        inline=isInline,
        filename=filename,
        cache_control=f"max-age={MAX_MEDIA_CACHE_AGE}",
        x_frame_from_referer=referer,
        vary=["x-resource-password"]
    )
