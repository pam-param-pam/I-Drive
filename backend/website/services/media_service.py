import base64
import hashlib
from itertools import batched

from django.contrib.auth import get_user_model

from website.auth.permissions import (
    ResourceAction, ResourceType, SignedResourcePrincipal)
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

from website.auth.permissions.engine import permissions


def list_download_folder_children(principal, folder_id, credentials=None):
    folder = permissions.authorize(ResourceAction.DOWNLOAD_SELECTED, principal, folder_id, credentials,
                                   resource_type=ResourceType.FOLDER).items[0].resource
    files = []
    file_ids = File.objects.filter(owner_id=principal.user_id, parent_id=folder.id).order_by("id").values_list("id", flat=True)
    for batch in batched(file_ids.iterator(chunk_size=500), 500):
        authorized = permissions.authorize(ResourceAction.DOWNLOAD_CHILDREN, principal, str(folder.id),
                                           file_ids=list(batch), credentials=credentials)
        files.extend({**item.row, "lock_from_id": item.state.lock_id} for item in authorized.items)

    folders = []
    folder_rows = Folder.objects.filter(owner_id=principal.user_id, parent_id=folder.id).order_by("id").values(
        "id", "visible_descendant_file_size", "visible_descendant_file_count",
    )
    for batch in batched(folder_rows.iterator(chunk_size=500), 500):
        metadata = {str(row["id"]): row for row in batch}
        authorized = permissions.authorize(ResourceAction.DOWNLOAD_CHILDREN, principal, str(folder.id),
                                           folder_ids=list(metadata), credentials=credentials)
        folders.extend({
            "id": item.row["id"], "name": item.row["name"],
            "size": metadata[item.row["id"]]["visible_descendant_file_size"],
            "file_count": metadata[item.row["id"]]["visible_descendant_file_count"],
        } for item in authorized.items)
    return folder, files, folders


def _authorized_signed_file(principal: SignedResourcePrincipal, *, for_zip: bool = False) -> File:
    action = ResourceAction.STREAM_ZIP_ENTRY if for_zip else ResourceAction.STREAM_FILE
    return permissions.authorize(action, principal).items[0].resource


def _stable_file_etag(file_obj: File) -> str:
    payload = f"{file_obj.id}:{file_obj.last_modified_at.isoformat()}:{file_obj.size}:{file_obj.crc}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get_thumbnail_response(request, principal: SignedResourcePrincipal, thumbnail_id: str):
    isInline = validate_key(request.GET, "inline", bool, default=False, converter=param_to_bool)
    file_obj = permissions.authorize(ResourceAction.STREAM_THUMBNAIL, principal).items[0].resource
    try:
        thumbnail = Thumbnail.objects.get(id=thumbnail_id, file_id=file_obj.id)
    except Thumbnail.DoesNotExist as exception:
        raise ResourceNotFoundError() from exception

    cache_key = cache_service.get_thumbnail_key(file_obj.id)
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
    authorized = permissions.authorize(ResourceAction.STREAM_ZIP, principal)
    user_zip = authorized.data["record"]
    roots = tuple(item.row for item in authorized.items)
    scope = authorized.data["scope"]
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
