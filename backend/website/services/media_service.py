import base64
import hashlib

from website.auth.Permissions import CheckIpPrivateOrAllowedIfResourceLocked
from website.auth.utils import check_resource_perms
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
from website.discord.Discord import discord
from website.models import File, Moment, Subtitle, UserZIP, Thumbnail
from website.models.mixin_models import ItemState
from website.queries.builders import build_zip_file_dict, build_flattened_children_mptt_values, FILE_VALUE_FIELDS, FOLDER_VALUE_FIELDS
from website.queries.selectors import check_if_bots_exists
from itertools import chain


def _stable_file_etag(file_obj: File) -> str:
    payload = f"{file_obj.id}:{file_obj.last_modified_at.isoformat()}:{file_obj.size}:{file_obj.crc}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get_thumbnail_response(request, file_obj: File, thumbnail: Thumbnail):
    isInline = validate_key(request.GET, "inline", bool, default=False, converter=param_to_bool)

    cache_key = f"thumbnail:{thumbnail.id}"
    thumbnail_content = cache.get(cache_key)

    check_if_bots_exists(file_obj.owner)
    if thumbnail.size > MAX_THUMBNAIL_SIZE:
        raise BadRequestError("Thumbnail too big too stream!")

    if not thumbnail_content:
        decryptor = Decryptor(method=file_obj.get_encryption_method(), key=thumbnail.key, iv=thumbnail.iv)
        url = discord.get_attachment_url(file_obj.owner, thumbnail)
        thumbnail_content = decrypt_bytes(fetch_discord_file(url), decryptor)
        cache.set(cache_key, thumbnail_content, timeout=MAX_MEDIA_CACHE_AGE)

    return build_binary_response(
        content=thumbnail_content,
        filename=f"thumbnail_{file_obj.get_name_no_extension()}.webp",
        content_type="image/webp",
        inline=isInline,
        cache_control=f"max-age={MAX_MEDIA_CACHE_AGE}"
    )


def get_moment_response(request, file_obj: File, moment: Moment):
    isInline = validate_key(request.GET, "inline", bool, default=False, converter=param_to_bool)

    check_if_bots_exists(file_obj.owner)

    decryptor = Decryptor(method=file_obj.get_encryption_method(), key=moment.key, iv=moment.iv)

    url = discord.get_attachment_url(file_obj.owner, moment)
    moment_content = decrypt_bytes(fetch_discord_file(url), decryptor)

    return build_binary_response(
        content=moment_content,
        filename=f"moment_{file_obj.get_name_no_extension()}.webp",
        content_type="image/webp",
        inline=isInline,
        cache_control=f"max-age={MAX_MEDIA_CACHE_AGE}"
    )


def get_subtitle_response(request, file_obj: File, subtitle: Subtitle):
    isInline = validate_key(request.GET, "inline", bool, default=False, converter=param_to_bool)

    check_if_bots_exists(file_obj.owner)

    decryptor = Decryptor(method=file_obj.get_encryption_method(), key=subtitle.key, iv=subtitle.iv)

    url = discord.get_attachment_url(file_obj.owner, subtitle)
    subtitle_content = decrypt_bytes(fetch_discord_file(url), decryptor)

    return build_binary_response(
        content=subtitle_content,
        filename=f"subtitle_{file_obj.get_name_no_extension()}.vtt",
        content_type="text/vtt",
        inline=isInline,
        cache_control=f"max-age={MAX_MEDIA_CACHE_AGE}"
    )


def get_file_response(request, file_obj: File):
    isInline = validate_key(request.GET, "inline", bool, default=False, converter=param_to_bool)
    raw = validate_key(request.GET, "raw", bool, default=False, converter=param_to_bool)

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


def iter_zip_file_dicts(file_rows):
    for file_row in file_rows:
        yield build_zip_file_dict(file_row, file_row["name"])


def get_zip_response(request, user_zip: UserZIP):
    raw = validate_key(request.GET, "raw", bool, default=False, converter=param_to_bool)
    user = user_zip.owner
    num_bots = check_if_bots_exists(user)

    files_qs = user_zip.files.filter(state=ItemState.ACTIVE, inTrash=False, parent__inTrash=False)
    folders_qs = user_zip.folders.filter(state=ItemState.ACTIVE, inTrash=False)

    # this works only because all items must be in the same parent (ensured during zip model creation)
    first_file = files_qs.first()
    if first_file is not None:
        check_resource_perms(request, first_file, [CheckIpPrivateOrAllowedIfResourceLocked])

    first_folder = folders_qs.first()
    if first_folder is not None:
        check_resource_perms(request, first_folder, [CheckIpPrivateOrAllowedIfResourceLocked])

    if first_file is None and first_folder is None:
        raise ResourceNotFoundError("ZIP is empty")

    files_exists = first_file is not None
    folders = list(folders_qs.values(*FOLDER_VALUE_FIELDS).order_by("id"))

    single_root = not files_exists and len(folders) == 1

    if single_root:
        root_folder = folders[0]
        dict_files = build_flattened_children_mptt_values(root_folder, include_root_name=False)
        zip_name = f"{root_folder['name']}.zip"
    else:
        file_rows = files_qs.values(*FILE_VALUE_FIELDS).order_by("id").iterator(chunk_size=1000)

        folder_iterators = (
            build_flattened_children_mptt_values(folder_row)
            for folder_row in folders
        )

        dict_files = chain(
            iter_zip_file_dicts(file_rows),
            chain.from_iterable(folder_iterators),
        )

        zip_name = f"{user_zip.name}.zip"

    owner = first_file.owner if first_file else first_folder.owner
    source = ZipByteSource(dict_files=dict_files, owner=owner, num_bots=num_bots, decrypted=not raw)

    return build_streaming_response(
        request=request,
        byte_source=source,
        filename=zip_name,
        content_type="application/zip",
        etag=user_zip.id,
        vary=["x-resource-password"],
    )


def get_zip_entry_response(request, file_obj: File):
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
