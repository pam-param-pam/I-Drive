import base64
import hashlib
from itertools import chain

from django.db.models import Exists, OuterRef, Q

from website.auth.permissions import (
    Authorizer, CredentialSet, ResourceAction,
    ResourceContextResolver, ResourceRef, ResourceType, SharePrincipal,
    SignedResourcePrincipal, UserPrincipal)
from website.config import MAX_THUMBNAIL_SIZE
from website.constants import cache, MAX_MEDIA_CACHE_AGE
from website.core.converters import param_to_bool
from website.core.crypto.Decryptor import Decryptor
from website.core.errors import BadRequestError, ResourceNotFoundError, ResourcePermissionError
from website.core.helpers import validate_key
from website.core.media.stream.sources.DeflateZipEntryByteSource import DeflateZipEntryByteSource
from website.core.media.stream.sources.EmptyByteSource import EmptyByteSource
from website.core.media.stream.sources.FragmentByteSource import FragmentedDiscordByteSource
from website.core.media.stream.sources.ZipByteSource import ZipByteSource
from website.core.media.utils import decrypt_bytes, fetch_discord_file, build_binary_response, build_streaming_response
from website.models import DeletionScope, File, Moment, Subtitle, UserZIP, Thumbnail
from website.models.mixin_models import ItemState
from website.queries.builders import build_zip_file_dict, build_flattened_children_values, FILE_VALUE_FIELDS, FOLDER_VALUE_FIELDS
from website.queries.selectors import check_if_bots_exists
from website.services import attachment_service, cache_service

authorizer = Authorizer()
context_resolver = ResourceContextResolver()


def _authorized_signed_file(principal: SignedResourcePrincipal) -> File:
    owner_id = File.objects.filter(id=principal.file_id).values_list("owner_id", flat=True).first()
    if owner_id is None:
        raise ResourceNotFoundError()
    context = context_resolver.resolve_file(principal.file_id, owner_id)
    authorizer.authorize_signed_resource(principal, context)
    return File.objects.select_related("owner", "parent").get(id=principal.file_id, owner_id=owner_id)


def _stable_file_etag(file_obj: File) -> str:
    payload = f"{file_obj.id}:{file_obj.last_modified_at.isoformat()}:{file_obj.size}:{file_obj.crc}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get_thumbnail_response(request, principal: SignedResourcePrincipal, thumbnail_id: str):
    isInline = validate_key(request.GET, "inline", bool, default=False, converter=param_to_bool)
    file_obj = _authorized_signed_file(principal)
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


def iter_zip_file_dicts(file_rows):
    for file_row in file_rows:
        yield build_zip_file_dict(file_row, file_row["name"])


def get_zip_response(
        request,
        principal: UserPrincipal | SharePrincipal,
        zip_id: str,
        credentials: CredentialSet | None = None,
):
    raw = validate_key(request.GET, "raw", bool, default=False, converter=param_to_bool)
    try:
        user_zip = UserZIP.objects.select_related("owner").get(Q(id=zip_id) | Q(token=zip_id))
    except UserZIP.DoesNotExist as exception:
        raise ResourceNotFoundError() from exception
    if isinstance(principal, UserPrincipal) and user_zip.owner_id != principal.user_id:
        raise ResourceNotFoundError()
    user = user_zip.owner
    num_bots = check_if_bots_exists(user)

    files_qs = user_zip.files.all()
    folders_qs = user_zip.folders.all()
    file_ids = list(files_qs.values_list("id", flat=True))
    folder_ids = list(folders_qs.values_list("id", flat=True))
    if isinstance(principal, UserPrincipal):
        file_rows = list(
            File.objects.filter(owner_id=principal.user_id, id__in=file_ids)
            .annotate(has_active_deletion=Exists(DeletionScope.objects.filter(
                owner_id=principal.user_id,
                root_file_id=OuterRef("pk"),
                state=DeletionScope.State.ACTIVE,
            )))
            .values("id", "owner_id", "parent_id", "state", "trashed_at", "has_active_deletion")
        )
        if len(file_rows) != len(file_ids):
            raise ResourceNotFoundError()
        parent_ids = {str(row["parent_id"]) for row in file_rows}
        context_folder_ids = parent_ids | set(folder_ids)
        folder_contexts = context_resolver.resolve_many(
            (ResourceRef(ResourceType.FOLDER, folder_id) for folder_id in context_folder_ids),
            principal.user_id,
        ) if context_folder_ids else ()
        contexts_by_id = {context.resource_id: context for context in folder_contexts}
        authorizer.authorize_user_file_batch(
            principal,
            ResourceAction.DOWNLOAD,
            (contexts_by_id[parent_id] for parent_id in parent_ids),
            file_rows,
            (contexts_by_id[folder_id] for folder_id in folder_ids),
            credentials,
        )
    else:
        from website.services.share_service import resolve_share

        refs = [ResourceRef(ResourceType.FILE, file_id) for file_id in file_ids]
        refs.extend(ResourceRef(ResourceType.FOLDER, folder_id) for folder_id in folder_ids)
        for ref in refs:
            resolve_share(principal, ResourceAction.DOWNLOAD_SHARE, ref.resource_type, ref.resource_id, credentials)

    files_qs = files_qs.filter(state=ItemState.ACTIVE)
    folders_qs = folders_qs.filter(state=ItemState.ACTIVE)
    files_exists = files_qs.exists()
    if not files_exists and not folders_qs.exists():
        raise ResourcePermissionError("ZIP contains no available files or folders")

    folders = list(folders_qs.values(*FOLDER_VALUE_FIELDS).order_by("id"))

    single_root = not files_exists and len(folders) == 1

    if single_root:
        root_folder = folders[0]
        dict_files = build_flattened_children_values(root_folder, include_root_name=False)
        zip_name = f"{root_folder['name']}.zip"
    else:
        file_rows = files_qs.values(*FILE_VALUE_FIELDS).order_by("id").iterator(chunk_size=1000)

        folder_iterators = (
            build_flattened_children_values(folder_row)
            for folder_row in folders
        )

        dict_files = chain(
            iter_zip_file_dicts(file_rows),
            chain.from_iterable(folder_iterators),
        )

        zip_name = f"{user_zip.name}.zip"

    source = ZipByteSource(dict_files=dict_files, owner=user, num_bots=num_bots, decrypted=not raw)

    return build_streaming_response(
        request=request,
        byte_source=source,
        filename=zip_name,
        content_type="application/zip",
        etag=user_zip.id,
        vary=["x-resource-password"],
    )


def get_zip_entry_response(request, principal: SignedResourcePrincipal):
    isInline = validate_key(request.GET, "inline", bool, default=False, converter=param_to_bool)
    referer = request.headers.get('Referer')

    offset = validate_key(request.GET, "offset", int, converter=int)
    compressed_size = validate_key(request.GET, "compressed_size", int, converter=int)
    uncompressed_size = validate_key(request.GET, "uncompressed_size", int, converter=int)
    compression_method = validate_key(request.GET, "compression_method", int, converter=int)
    filename_b64 = validate_key(request.GET, "filename", str)

    filename = base64.b64decode(filename_b64).decode()
    file_obj = _authorized_signed_file(principal)
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
