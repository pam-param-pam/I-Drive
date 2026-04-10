from ..auth.Permissions import CheckLockedFolderIP
from ..auth.utils import check_resource_perms
from ..constants import MAX_MEDIA_CACHE_AGE, USE_CACHE, cache, MAX_THUMBNAIL_SIZE
from ..core.crypto.Decryptor import Decryptor
from ..core.errors import BadRequestError
from ..core.media.stream.ZipByteSource import ZipByteSource
from ..core.media.stream.sources.DeflateZipEntryByteSource import DeflateZipEntryByteSource
from ..core.media.stream.sources.EmptyByteSource import EmptyByteSource
from ..core.media.stream.sources.FragmentByteSource import FragmentedDiscordByteSource
from ..core.media.utils import build_binary_response, decrypt_bytes, fetch_discord_file, build_streaming_response
from ..discord.Discord import discord
from ..models import File, Moment, Subtitle, UserZIP
from ..models.mixin_models import ItemState
from ..queries.builders import build_flattened_children, build_zip_file_dict
from ..queries.selectors import check_if_bots_exists


def get_thumbnail_response(request, file_obj: File, ):
    isInline = request.GET.get('inline', False)
    thumbnail = file_obj.thumbnail

    cache_key = f"thumbnail:{thumbnail.id}"
    thumbnail_content = cache.get(cache_key)

    check_if_bots_exists(file_obj.owner)
    if thumbnail.size > MAX_THUMBNAIL_SIZE:
        raise BadRequestError("Thumbnail too big too stream!")

    if not thumbnail_content or not USE_CACHE:
        decryptor = Decryptor(method=file_obj.get_encryption_method(), key=thumbnail.key, iv=thumbnail.iv)
        url = discord.get_attachment_url(file_obj.owner, thumbnail)
        thumbnail_content = decrypt_bytes(fetch_discord_file(url), decryptor)
        cache.set(cache_key, thumbnail_content, timeout=MAX_MEDIA_CACHE_AGE)

    return build_binary_response(
        content=thumbnail_content,
        filename=f"thumbnail_{file_obj.get_name_no_extension()}.webp",
        content_type="image/webp",
        inline=isInline,
        cache_control=f"max-age={MAX_MEDIA_CACHE_AGE}",
        vary=["x-resource-password"],
    )


def get_moment_response(request, file_obj: File, moment: Moment):
    isInline = request.GET.get('inline', False)

    check_if_bots_exists(file_obj.owner)

    decryptor = Decryptor(method=file_obj.get_encryption_method(), key=moment.key, iv=moment.iv)

    url = discord.get_attachment_url(file_obj.owner, moment)
    moment_content = decrypt_bytes(fetch_discord_file(url), decryptor)

    return build_binary_response(
        content=moment_content,
        filename=f"moment_{file_obj.get_name_no_extension()}.webp",
        content_type="image/webp",
        inline=isInline,
        cache_control=f"max-age={MAX_MEDIA_CACHE_AGE}",
        vary=["x-resource-password"],
    )


def get_subtitle_response(request, file_obj: File, subtitle: Subtitle):
    isInline = request.GET.get('inline', False)

    check_if_bots_exists(file_obj.owner)

    decryptor = Decryptor(method=file_obj.get_encryption_method(), key=subtitle.key, iv=subtitle.iv)

    url = discord.get_attachment_url(file_obj.owner, subtitle)
    subtitle_content = decrypt_bytes(fetch_discord_file(url), decryptor)

    return build_binary_response(
        content=subtitle_content,
        filename=f"subtitle_{file_obj.get_name_no_extension()}.webp",
        content_type="image/webp",
        inline=isInline,
        cache_control=f"max-age={MAX_MEDIA_CACHE_AGE}",
        vary=["x-resource-password"],
    )


def get_file_response(request, file_obj: File):
    is_inline = request.GET.get("inline", False)

    fragments = file_obj.fragments.all().order_by("sequence")
    user = file_obj.owner

    check_if_bots_exists(user)

    if not fragments.exists():
        source = EmptyByteSource()
    else:
        source = FragmentedDiscordByteSource(file_obj=file_obj, fragments=fragments)

    return build_streaming_response(
        request=request,
        byte_source=source,
        filename=file_obj.name,
        inline=is_inline,
        cache_control=f"max-age={MAX_MEDIA_CACHE_AGE}",
        vary=["x-resource-password"],
    )


def get_zip_response(request, token: str):
    user_zip = UserZIP.objects.get(token=token)
    user = user_zip.owner

    check_if_bots_exists(user)

    if user_zip.files.exists():
        check_resource_perms(request, user_zip.files.first(), [CheckLockedFolderIP])
    if user_zip.folders.exists():
        check_resource_perms(request, user_zip.folders.first(), [CheckLockedFolderIP])

    files = user_zip.files.filter(state=ItemState.ACTIVE, inTrash=False, parent__inTrash=False)
    folders = user_zip.folders.filter(state=ItemState.ACTIVE, inTrash=False)

    dict_files = []

    single_root = False
    if len(files) == 0 and len(folders) == 1:
        single_root = True
        dict_files = build_flattened_children(folders[0], root_folder=folders[0])
    else:
        for file in files:
            dict_files.append(build_zip_file_dict(file, file.name))
        for folder in folders:
            dict_files += build_flattened_children(folder, root_folder=folder)

    zip_name = (folders[0].name if single_root else user_zip.name) + ".zip"

    source = ZipByteSource(user_zip=user_zip, dict_files=dict_files)

    return build_streaming_response(
        request=request,
        byte_source=source,
        filename=zip_name,
        content_type="application/zip",
        etag=user_zip.id,
        vary=["x-resource-password"]
    )


def get_zip_entry_response(request, file_obj: File):
    offset = int(request.GET["offset"])  # todo
    compressed_size = int(request.GET["compressed_size"])
    uncompressed_size = int(request.GET["uncompressed_size"])
    compression_method = int(request.GET["compression_method"])
    filename = request.GET["filename"]

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
        inline=True,
        filename=filename,
        cache_control=f"max-age={MAX_MEDIA_CACHE_AGE}",
        vary=["x-resource-password"],
    )
