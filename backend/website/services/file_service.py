from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, Type

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from website.config import MAX_FILES_IN_FOLDER
from website.constants import EventCode, MAX_DISCORD_MESSAGE_SIZE
from website.core.Serializers import FileSerializer
from website.core.http.context import RequestContext
from website.core.converters import chop_long_file_name, parse_unix_milliseconds
from website.core.errors import BadRequestError, ResourceNotFoundError
from website.core.helpers import (
    get_file_extension, get_file_type, validate_crc,
    validate_encryption_fields, validate_ids_as_list, validate_key,
    validate_value)
from website.core.validators.GeneralChecks import (
    IsPositive, IsSnowflake, IsValidItemName, Max, MaxLength, NotEmpty,
    NotNegative)
from website.models import (
    AudioTrack, DeletionScope, File, Fragment, MediaPosition,
    Moment, Subtitle, SubtitleTrack, Tag, VideoMetadata,
    VideoMetadataTrackMixin, VideoTrack)
from website.models.file_related_models import PhotoMetadata, RawMetadata
from website.models.other_models import RawExtractionClaim
from website.models.mixin_models import DiscordAttachmentMixin, ItemState
from website.auth.permissions import (
    CredentialSet, ResourceAction, ResourceType,
    UserPrincipal)
from website.queries.selectors import (check_if_bots_exists, get_discord_author, get_discord_channel)
from website.services import namespace_lock_service
from website.services.derived_state_service import (
    apply_counter_deltas, bump_file_resources, bump_folder_listings,
    dirty_hashes, merge_delta)
from website.services.hierarchy_service import LockedHierarchy, lock_folder_chains
from website.services.derived_state_service import change_file_stats, merge_file_stats, apply_file_stats_deltas
from website.websockets.utils import group_and_send_event, send_event
from website.auth.permissions.authorizer import authorizer
from website.queries.resource_loader import ResourceLoader


@dataclass(frozen=True)
class FileCommandResult:
    file_id: str
    resource_version: int
    operation_id: str | None = None


@dataclass(frozen=True)
class FileCreateResult:
    file_id: str
    resource_version: int
    created: bool


@dataclass(frozen=True)
class LockedFiles:
    files: dict[str, File]
    hierarchy: LockedHierarchy


def lock_files_with_parents(
    owner_id: int,
    file_ids: Iterable[str],
    extra_folder_ids: Iterable[str] = (),
) -> LockedFiles:
    owner_id = int(owner_id)
    ids = {str(file_id) for file_id in file_ids}
    snapshot = {
        str(file_id): str(parent_id)
        for file_id, parent_id in File.objects.filter(owner_id=owner_id, id__in=ids).values_list("id", "parent_id")
    }
    if len(snapshot) != len(ids):
        raise ResourceNotFoundError()

    hierarchy = lock_folder_chains(owner_id, {*snapshot.values(), *{str(value) for value in extra_folder_ids}})
    file_objects = list(File.objects.select_for_update().filter(owner_id=owner_id, id__in=ids).order_by("id"))
    if len(file_objects) != len(ids):
        raise ResourceNotFoundError()

    files = {str(file_obj.id): file_obj for file_obj in file_objects}
    if any(str(file_obj.parent_id) != snapshot[str(file_obj.id)] for file_obj in file_objects):
        raise BadRequestError("File hierarchy changed concurrently; retry the request")
    return LockedFiles(files, hierarchy)


def adjust_relation_count(file_obj: File, field: str, delta: int) -> None:
    if field not in {"fragment_count", "subs_count"}:
        raise ValueError("Unsupported file relation count")
    File.objects.filter(pk=file_obj.pk).update(**{field: F(field) + delta})
    setattr(file_obj, field, getattr(file_obj, field) + delta)


def set_relation_state(file_obj: File, **values) -> None:
    allowed = {"fragment_count", "subs_count", "thumbnail_cache_id",
               "has_photo_metadata", "has_raw_metadata", "has_video_metadata"}
    if set(values) - allowed:
        raise ValueError("Unsupported file relation state")
    File.objects.filter(pk=file_obj.pk).update(**values)
    for field, value in values.items():
        setattr(file_obj, field, value)


def set_thumbnail(file_obj: File, thumbnail=None) -> None:
    set_relation_state(
        file_obj,
        thumbnail_cache_id=str(thumbnail.pk) if thumbnail is not None else None,
    )


def _authorize_file(
    principal: UserPrincipal,
    file_id: str,
    action: ResourceAction,
    credentials: CredentialSet | None,
) -> tuple[LockedFiles, File]:
    """Lock and authorize one file inside the caller's transaction."""
    owner_id = principal.user_id
    namespace_lock_service.lock_owner_scope_shared(owner_id)
    locked = lock_files_with_parents(owner_id, [file_id])
    file_obj = locked.files[str(file_id)]
    authorizer.require_item(
        principal, action, file_id, credentials, resource_type=ResourceType.FILE,
        locked_hierarchy=locked.hierarchy, locked_files=locked.files,
    )
    return locked, file_obj


def _delete_removed_attachments(user: User, attachments) -> None:
    from website.services import attachment_service

    for attachment in attachments:
        attachment_service.delete_remote_single_discord_attachment(user, attachment)


def _remove_related_attachment(
    principal: UserPrincipal,
    file_id: str,
    attachment_id: str,
    model: Type[Moment] | Type[Subtitle] | Type[Fragment],
    credentials: CredentialSet | None,
) -> FileCommandResult:
    with transaction.atomic():
        _, file_obj = _authorize_file(principal, file_id, ResourceAction.EDIT_METADATA, credentials)
        attachment = model.objects.select_for_update().select_related("channel", "author").get(
            id=attachment_id, file_id=file_obj.id,
        )
        attachment.delete()
        if model is Subtitle:
            adjust_relation_count(file_obj, "subs_count", -1)
        elif model is Fragment:
            adjust_relation_count(file_obj, "fragment_count", -1)
        bump_file_resources([file_obj.id])
        bump_folder_listings([file_obj.parent_id])
        file_obj.refresh_from_db(fields=["resource_version"])
        result = FileCommandResult(str(file_obj.id), file_obj.resource_version)
    _delete_removed_attachments(User.objects.get(id=principal.user_id), (attachment,))
    return result


def _change_trash_state(
    principal: UserPrincipal,
    file_ids: list[str],
    restore: bool,
    credentials: CredentialSet | None,
) -> list[FileCommandResult]:
    owner_id = principal.user_id
    action = ResourceAction.RESTORE if restore else ResourceAction.TRASH
    with transaction.atomic():
        namespace_lock_service.lock_owner_scope_shared(owner_id)
        locked = lock_files_with_parents(owner_id, file_ids)
        authorizer.require_items(
            principal, action, file_ids=file_ids, credentials=credentials,
            locked_hierarchy=locked.hierarchy, locked_files=locked.files,
        )

        return _change_trash_state_locked(owner_id, locked, restore)


def _change_trash_state_locked(owner_id, locked, restore):
    namespace_lock_service._require_transaction()
    direction = 1 if restore else -1
    deltas: dict[str, dict[str, int]] = {}
    dirty_ids: set[str] = set()
    parent_ids: set[str] = set()
    for file_obj in locked.files.values():
        chain = locked.hierarchy.chain(str(file_obj.parent_id))
        dirty_ids.update(chain)
        parent_ids.add(str(file_obj.parent_id))
        merge_delta(deltas, chain, visible_descendant_file_count=direction,
                    visible_descendant_file_size=direction * file_obj.size)

    files = File.objects.filter(id__in=locked.files, owner_id=owner_id)
    now = timezone.now()
    updated = files.update(trashed_at=None if restore else now, last_modified_at=now,
                           resource_version=F("resource_version") + 1)
    if updated != len(locked.files):
        raise BadRequestError("File selection changed during the command")

    apply_counter_deltas(deltas)
    dirty_hashes(dirty_ids)
    bump_folder_listings(parent_ids)
    event = EventCode.ITEM_RESTORE_FROM_TRASH if restore else EventCode.ITEM_MOVE_TO_TRASH
    for file_obj in locked.files.values():
        file_obj.trashed_at = None if restore else now
        file_obj.last_modified_at = now
        file_obj.resource_version += 1
    group_and_send_event(RequestContext.from_user(owner_id), event, list(locked.files.values()))
    refreshed = File.objects.filter(id__in=locked.files).values_list("id", "resource_version")
    return [FileCommandResult(str(file_id), version) for file_id, version in refreshed]


def _attachment_identity(owner_id: int, data: dict) -> dict:
    channel_id = validate_key(data, "channel_id", str, checks=[IsSnowflake])
    message_id = validate_key(data, "message_id", str, checks=[IsSnowflake])
    attachment_id = validate_key(data, "attachment_id", str, checks=[IsSnowflake])
    author_id = validate_key(data, "message_author_id", str, checks=[IsSnowflake])
    author = get_discord_author(owner_id, author_id)

    return {
        "channel": get_discord_channel(owner_id, channel_id),
        "message_id": message_id,
        "attachment_id": attachment_id,
        "author": author,
    }


def _create_fragment(file_obj: File, data: dict) -> Fragment:
    values = _attachment_identity(file_obj.owner_id, data)
    values.update({
        "file": file_obj,
        "sequence": validate_key(data, "fragment_sequence", int, checks=[IsPositive]),
        "size": validate_key(
            data, "fragment_size", int,
            checks=[IsPositive, Max(MAX_DISCORD_MESSAGE_SIZE)],
        ),
        "offset": validate_key(data, "offset", int, checks=[NotNegative]),
        "crc": validate_key(data, "crc", int, checks=[MaxLength(10), NotNegative]),
    })

    result = Fragment.objects.create(**values)
    adjust_relation_count(file_obj, "fragment_count", 1)
    return result


def _create_subtitle(file_obj: File, data: dict) -> Subtitle:
    if file_obj.type != "Video":
        raise BadRequestError(f"Subtitles are not allowed for file type: {file_obj.type}")

    values = _attachment_identity(file_obj.owner_id, data)
    key, iv = validate_encryption_fields(
        file_obj.encryption_method,
        validate_key(data, "key", str, default=None),
        validate_key(data, "iv", str, default=None),
    )
    values.update({
        "file": file_obj,
        "language": validate_key(data, "language", str, checks=[NotEmpty, MaxLength(20)]),
        "forced": validate_key(data, "is_forced", bool),
        "size": validate_key(data, "size", int, checks=[IsPositive]),
        "key": key,
        "iv": iv,
    })
    result = Subtitle.objects.create(**values)
    adjust_relation_count(file_obj, "subs_count", 1)
    return result


def _create_tracks(metadata: dict, track_type: str, model_class: Type[VideoMetadataTrackMixin], video_metadata: VideoMetadata) -> None:
    tracks = validate_key(metadata, track_type, list)
    for index, track in enumerate(tracks):
        values = {
            "video_metadata": video_metadata,
            "bitrate": validate_key(track, "bitrate", (int, float), checks=[IsPositive], default=None),
            "codec": validate_key(track, "codec", str, checks=[MaxLength(100)]),
            "size": validate_key(track, "size", (int, float), checks=[NotNegative]),
            "duration": validate_key(track, "duration", (int, float), checks=[NotNegative]),
            "language": validate_key(track, "language", str, default=None, checks=[MaxLength(100)]),
            "track_number": index + 1,
        }
        if track_type == "video_tracks":
            values.update({
                "height": validate_key(track, "height", int, checks=[IsPositive]),
                "width": validate_key(track, "width", int, checks=[IsPositive]),
                "fps": validate_key(track, "fps", int, checks=[IsPositive]),
            })
        elif track_type == "audio_tracks":
            values.update({
                "name": validate_key(track, "name", str, checks=[MaxLength(100)]),
                "channel_count": validate_key(track, "channel_count", int, checks=[IsPositive]),
                "sample_rate": validate_key(track, "sample_rate", int, checks=[NotNegative]),
                "sample_size": validate_key(track, "sample_size", int, checks=[IsPositive]),
            })
        else:
            values["name"] = validate_key(track, "name", str, checks=[MaxLength(100)])
        model_class.objects.create(**values)


def _create_video_metadata(file_obj: File, metadata: dict) -> VideoMetadata:
    if file_obj.type != "Video":
        raise BadRequestError(f"Video metadata is not allowed for file type: {file_obj.type}")
    result = VideoMetadata.objects.create(
        file=file_obj,
        is_fragmented=validate_key(metadata, "is_fragmented", bool),
        is_progressive=validate_key(metadata, "is_progressive", bool),
        has_moov=validate_key(metadata, "has_moov", bool),
        has_IOD=validate_key(metadata, "has_IOD", bool),
        brands=validate_key(metadata, "brands", str, checks=[NotEmpty, MaxLength(100)]),
        mime=validate_key(metadata, "mime", str, checks=[NotEmpty, MaxLength(100)]),
    )
    set_relation_state(file_obj, has_video_metadata=True)
    _create_tracks(metadata, "video_tracks", VideoTrack, result)
    _create_tracks(metadata, "audio_tracks", AudioTrack, result)
    _create_tracks(metadata, "subtitle_tracks", SubtitleTrack, result)
    return result


def _create_raw_metadata(file_obj: File, metadata: dict) -> RawMetadata:
    if file_obj.type != "Raw image":
        raise BadRequestError(f"Raw metadata is not allowed for file type: {file_obj.type}")
    result = RawMetadata.objects.create(
        file=file_obj,
        camera=validate_key(metadata, "camera", str, checks=[NotEmpty, MaxLength(50)]),
        camera_owner=validate_key(metadata, "camera_owner", str, default="", checks=[MaxLength(50)]),
        iso=validate_key(metadata, "iso", str, checks=[NotEmpty, MaxLength(50)]),
        shutter=validate_key(metadata, "shutter", str, checks=[NotEmpty, MaxLength(50)]),
        aperture=validate_key(metadata, "aperture", str, checks=[NotEmpty, MaxLength(50)]),
        focal_length=validate_key(metadata, "focal_length", str, checks=[NotEmpty, MaxLength(50)]),
    )
    set_relation_state(file_obj, has_raw_metadata=True)
    return result


def _create_photo_metadata(file_obj: File, metadata: dict) -> PhotoMetadata:
    if file_obj.type != "Image":
        raise BadRequestError(f"Photo metadata is not allowed for file type: {file_obj.type}")
    result = PhotoMetadata.objects.create(
        file=file_obj,
        height=validate_key(metadata, "height", int, checks=[IsPositive]),
        width=validate_key(metadata, "width", int, checks=[IsPositive]),
    )
    set_relation_state(file_obj, has_photo_metadata=True)
    return result


class FileService:
    @staticmethod
    def remove_fragment(principal, file_id, fragment_id, credentials=None):
        return _remove_related_attachment(principal, file_id, fragment_id, Fragment, credentials)

    @staticmethod
    def remove_metadata(principal, file_id, model, credentials=None):
        fields = {PhotoMetadata: "has_photo_metadata", RawMetadata: "has_raw_metadata",
                  VideoMetadata: "has_video_metadata"}
        if model not in fields:
            raise ValueError("Unsupported metadata model")
        with transaction.atomic():
            _, file_obj = _authorize_file(principal, file_id, ResourceAction.EDIT_METADATA, credentials)
            model.objects.filter(file_id=file_obj.pk).delete()
            set_relation_state(file_obj, **{fields[model]: False})
            bump_file_resources([file_obj.pk])
            bump_folder_listings([file_obj.parent_id])

    @staticmethod
    def complete_raw_image_extraction(
        owner_id: int,
        file_id: str,
        claim_attempts: int,
        metadata: dict,
        thumbnail: dict | None = None,
        failed: bool = False,
    ) -> bool:
        """Commit a claimed raw-image result and its cache versions together."""
        from website.services.thumbnail_service import thumbnail_service

        if failed == (thumbnail is not None):
            raise BadRequestError("Raw extraction requires a thumbnail on success and none on failure")
        with transaction.atomic():
            namespace_lock_service.lock_owner_scope_shared(owner_id)
            locked = lock_files_with_parents(owner_id, [file_id])
            file_obj = locked.files[str(file_id)]
            claim = RawExtractionClaim.objects.select_for_update().filter(file_id=file_id).first()
            if claim is None or claim.attempts != claim_attempts:
                return False
            if claim.state != RawExtractionClaim.State.RUNNING and not failed:
                return False
            context = ResourceLoader().resolve_file(
                file_id, owner_id, locked.hierarchy, locked.files,
            )
            if context.is_deleting or context.is_trashed or file_obj.state != ItemState.ACTIVE:
                return False
            if file_obj.type != "Raw image":
                return False
            if file_obj.has_raw_metadata or file_obj.thumbnail_cache_id:
                RawExtractionClaim.objects.filter(file_id=file_id).delete()
                return False

            if thumbnail is not None:
                thumbnail_service.add_to_new_file(file_obj, thumbnail)
            raw_metadata = _create_raw_metadata(file_obj, metadata)
            if failed:
                raw_metadata.failed_to_process = True
                raw_metadata.save(update_fields=["failed_to_process"])
            File.objects.filter(id=file_id).update(last_modified_at=timezone.now())
            bump_file_resources([file_id])
            bump_folder_listings([file_obj.parent_id])
            RawExtractionClaim.objects.filter(file_id=file_id).delete()

            def notify_after_commit():
                updated = File.objects.select_related("parent").get(id=file_id)
                send_event(
                    RequestContext.from_user(owner_id), updated.parent,
                    EventCode.ITEM_UPDATE, FileSerializer.serialize_object(updated),
                )

            transaction.on_commit(lambda: thumbnail_service._cleanup_committed_cache(file_id), robust=True)
            transaction.on_commit(notify_after_commit, robust=True)
            return True

    @staticmethod
    def create(principal: UserPrincipal, parent_id: str, name: str, size: int, frontend_id: str, encryption_method: int, crc: int,
               fragments: list[dict], key_b64: str | None = None, iv_b64: str | None = None, created_at=None, thumbnail: dict | None = None,
               video_metadata: dict | None = None, raw_metadata: dict | None = None, photo_metadata: dict | None = None,
               subtitles: list[dict] | None = None, credentials: CredentialSet | None = None) -> FileCreateResult:
        from website.services.thumbnail_service import thumbnail_service

        name = validate_value(name, str, checks=[IsValidItemName])
        size = validate_value(size, int, checks=[NotNegative])
        fragments = validate_value(fragments, list)
        validate_crc(size, crc)
        key, iv = validate_encryption_fields(encryption_method, key_b64, iv_b64)
        fragment_sizes = [
            validate_key(fragment, "fragment_size", int, checks=[IsPositive, Max(MAX_DISCORD_MESSAGE_SIZE)])
            for fragment in fragments
        ]
        if sum(fragment_sizes) != size:
            raise BadRequestError(f"Attachment sizes ({sum(fragment_sizes)}) do not match declared file size ({size}).")

        owner_id = principal.user_id
        extension = get_file_extension(name)
        file_type = get_file_type(extension)
        with transaction.atomic():
            namespace_lock_service.lock_owner_scope_shared(owner_id)
            locked = lock_files_with_parents(owner_id, [], [parent_id])
            parent = locked.hierarchy.folders[str(parent_id)]
            authorizer.require_item(
                principal, ResourceAction.CREATE_CHILD, str(parent.id), credentials,
                resource_type=ResourceType.FOLDER, locked_hierarchy=locked.hierarchy,
            )

            existing = File.objects.select_for_update().filter(frontend_id=frontend_id).first()
            if existing:
                if existing.owner_id != owner_id:
                    raise ResourceNotFoundError()
                return FileCreateResult(str(existing.id), existing.resource_version, False)
            if parent.files.count() >= MAX_FILES_IN_FOLDER:
                raise BadRequestError(f"Too many files in folder. Max = {MAX_FILES_IN_FOLDER}")

            file_obj = File.objects.create(
                owner_id=owner_id,
                parent_id=parent.id,
                name=name,
                extension=extension,
                type=file_type,
                size=size,
                frontend_id=frontend_id,
                encryption_method=encryption_method,
                crc=crc,
                key=key,
                iv=iv,
            )
            if created_at is not None:
                File.objects.filter(id=file_obj.id).update(created_at=created_at)
                file_obj.created_at = created_at

            for fragment in fragments:
                _create_fragment(file_obj, fragment)
            if thumbnail is not None:
                thumbnail_service.add_to_new_file(file_obj, thumbnail)
            if video_metadata is not None:
                _create_video_metadata(file_obj, video_metadata)
            if raw_metadata is not None:
                _create_raw_metadata(file_obj, raw_metadata)
            if photo_metadata is not None:
                _create_photo_metadata(file_obj, photo_metadata)
            for subtitle in subtitles or ():
                _create_subtitle(file_obj, subtitle)

            chain = locked.hierarchy.chain(str(parent.id))
            deltas: dict[str, dict[str, int]] = {}
            merge_delta(
                deltas,
                chain,
                physical_descendant_file_count=1,
                physical_descendant_file_size=size,
                visible_descendant_file_count=1,
                visible_descendant_file_size=size,
            )
            apply_counter_deltas(deltas)
            change_file_stats(chain, file_obj.type, count=1, size=size)
            dirty_hashes(chain)
            bump_folder_listings([parent.id])
            send_event(RequestContext.from_user(owner_id), parent, EventCode.ITEM_CREATE,
                       FileSerializer.serialize_object(file_obj))
            return FileCreateResult(str(file_obj.id), file_obj.resource_version, True)

    @staticmethod
    def _create_single_file(principal: UserPrincipal, data: dict, credentials: CredentialSet | None) -> File | None:
        name = validate_key(data, "name", str, checks=[IsValidItemName], converter=chop_long_file_name)
        parent_id = validate_key(data, "parent_id", str, checks=[NotEmpty])
        size = validate_key(data, "size", int, checks=[NotNegative])
        frontend_id = validate_key(data, "frontend_id", str, checks=[MaxLength(40), NotEmpty])
        encryption_method = validate_key(data, "encryption_method", int, checks=[MaxLength(1)])
        crc = validate_key(data, "crc", int, checks=[MaxLength(10), NotNegative])
        fragments = validate_key(data, "fragments", list)
        key_b64 = validate_key(data, "key", str, default=None)
        iv_b64 = validate_key(data, "iv", str, default=None)
        validate_crc(size, crc)

        result = FileService.create(
            principal,
            parent_id,
            name=name,
            size=size,
            frontend_id=frontend_id,
            encryption_method=encryption_method,
            crc=crc,
            fragments=fragments,
            key_b64=key_b64,
            iv_b64=iv_b64,
            created_at=parse_unix_milliseconds(validate_key(data, "created_at", int, default=None)),
            thumbnail=validate_key(data, "thumbnail", dict, default=None),
            video_metadata=validate_key(data, "videoMetadata", dict, default=None),
            raw_metadata=validate_key(data, "rawMetadata", dict, default=None),
            photo_metadata=validate_key(data, "photoMetadata", dict, default=None),
            subtitles=validate_key(data, "subtitles", list, default=[]),
            credentials=credentials,
        )
        if not result.created:
            return None
        return File.objects.select_related("parent", "owner").get(id=result.file_id)

    @staticmethod
    def create_files(principal: UserPrincipal, files_data: list[dict], credentials: CredentialSet | None = None) -> list[File]:
        user = User.objects.get(id=principal.user_id)
        check_if_bots_exists(user)
        validate_ids_as_list(files_data, max_length=100)

        files = []
        for data in files_data:
            file_obj = FileService._create_single_file(principal, data, credentials)
            if file_obj is not None:
                files.append(file_obj)

        return files

    @staticmethod
    def replace_content(principal: UserPrincipal, file_id: str, file_data: dict | None, credentials: CredentialSet | None = None) -> FileCommandResult:
        from website.services.thumbnail_service import thumbnail_service

        attachment = None
        crc = 0
        key_b64 = None
        iv_b64 = None
        if file_data:
            attachment = validate_key(file_data, "attachment", dict)
            crc = validate_key(file_data, "crc", int, checks=[MaxLength(10), NotNegative])
            key_b64 = validate_key(file_data, "key", str)
            iv_b64 = validate_key(file_data, "iv", str)
            validate_crc(validate_key(attachment, "fragment_size", int), crc)

        owner_id = principal.user_id
        new_size = 0
        if attachment is not None:
            new_size = validate_key(attachment, "fragment_size", int, checks=[IsPositive, Max(MAX_DISCORD_MESSAGE_SIZE)])
        validate_crc(new_size, crc)

        with transaction.atomic():
            locked, file_obj = _authorize_file(principal, file_id, ResourceAction.EDIT_CONTENT, credentials)
            check_if_bots_exists(owner_id)
            if file_obj.type not in ("Text", "Code", "Database", "Other"):
                raise BadRequestError("You can only edit text files!")

            if attachment is None:
                key, iv = file_obj.key, file_obj.iv
            else:
                key, iv = validate_encryption_fields(file_obj.encryption_method, key_b64, iv_b64)

            removed: tuple[DiscordAttachmentMixin, ...] = tuple([
                *Fragment.objects.select_for_update().select_related("channel", "author").filter(file_id=file_obj.id),
                *thumbnail_service.remove_during_content_replacement(file_obj),
                *Moment.objects.select_for_update().select_related("channel", "author").filter(file_id=file_obj.id),
                *Subtitle.objects.select_for_update().select_related("channel", "author").filter(file_id=file_obj.id),
            ])
            if sum(isinstance(value, Fragment) for value in removed) > 1:
                raise BadRequestError("You cannot edit a file that has more than one fragment!")

            Fragment.objects.filter(file_id=file_obj.id).delete()
            Moment.objects.filter(file_id=file_obj.id).delete()
            Subtitle.objects.filter(file_id=file_obj.id).delete()
            VideoMetadata.objects.filter(file_id=file_obj.id).delete()
            RawMetadata.objects.filter(file_id=file_obj.id).delete()
            PhotoMetadata.objects.filter(file_id=file_obj.id).delete()
            MediaPosition.objects.filter(file_id=file_obj.id).delete()
            set_relation_state(file_obj, fragment_count=0, subs_count=0,
                               has_photo_metadata=False, has_raw_metadata=False, has_video_metadata=False)

            if attachment is not None:
                _create_fragment(file_obj, attachment)
            now = timezone.now()
            File.objects.filter(id=file_obj.id).update(size=new_size, crc=crc, key=key, iv=iv, last_modified_at=now)
            chain = locked.hierarchy.chain(str(file_obj.parent_id))
            difference = new_size - file_obj.size
            deltas: dict[str, dict[str, int]] = {}
            merge_delta(
                deltas,
                chain,
                physical_descendant_file_size=difference,
                visible_descendant_file_size=difference,
            )
            apply_counter_deltas(deltas)
            change_file_stats(chain, file_obj.type, size=difference)
            dirty_hashes(chain)
            bump_file_resources([file_obj.id])
            bump_folder_listings([file_obj.parent_id])
            file_obj.refresh_from_db(fields=["resource_version"])
            result = FileCommandResult(str(file_obj.id), file_obj.resource_version)
            send_event(RequestContext.from_user(owner_id), locked.hierarchy.folders[str(file_obj.parent_id)],
                       EventCode.ITEM_UPDATE, FileSerializer.serialize_object(file_obj))

        user = User.objects.get(id=owner_id)
        _delete_removed_attachments(user, removed)
        return result

    @staticmethod
    def rename(principal: UserPrincipal, file_id: str, name: str, credentials: CredentialSet | None = None) -> FileCommandResult:
        # what about file metadata which is no longer compatible with new file type?
        name = validate_value(name, str, checks=[IsValidItemName])
        owner_id = principal.user_id
        with transaction.atomic():
            locked, file_obj = _authorize_file(principal, file_id, ResourceAction.RENAME, credentials)

            extension = get_file_extension(name)
            File.objects.filter(id=file_obj.id).update(
                name=name,
                extension=extension,
                type=get_file_type(extension),
                last_modified_at=timezone.now(),
            )
            chain = locked.hierarchy.chain(str(file_obj.parent_id))
            stats = {}
            merge_file_stats(stats, chain, {file_obj.type: {"count": 1, "size": file_obj.size}}, -1)
            merge_file_stats(stats, chain, {get_file_type(extension): {"count": 1, "size": file_obj.size}})
            apply_file_stats_deltas(stats)
            dirty_hashes(chain)
            bump_file_resources([file_obj.id])
            bump_folder_listings([file_obj.parent_id])
            file_obj.refresh_from_db(fields=["resource_version"])
            send_event(RequestContext.from_user(owner_id), locked.hierarchy.folders[str(file_obj.parent_id)],
                       EventCode.ITEM_UPDATE, FileSerializer.serialize_object(file_obj))
            return FileCommandResult(str(file_obj.id), file_obj.resource_version)

    @staticmethod
    def change_size(principal: UserPrincipal, file_id: str, size: int, crc: int | None = None, credentials: CredentialSet | None = None) -> FileCommandResult:
        size = validate_value(size, int, checks=[NotNegative])
        owner_id = principal.user_id
        with transaction.atomic():
            locked, file_obj = _authorize_file(principal, file_id, ResourceAction.EDIT_CONTENT, credentials)
            difference = size - file_obj.size
            File.objects.filter(id=file_obj.id).update(size=size, crc=crc, last_modified_at=timezone.now())

            chain = locked.hierarchy.chain(str(file_obj.parent_id))
            deltas: dict[str, dict[str, int]] = {}
            merge_delta(
                deltas,
                chain,
                physical_descendant_file_size=difference,
                visible_descendant_file_size=difference,
            )
            apply_counter_deltas(deltas)
            change_file_stats(chain, file_obj.type, size=difference)
            dirty_hashes(chain)
            bump_file_resources([file_obj.id])
            bump_folder_listings([file_obj.parent_id])
            file_obj.refresh_from_db(fields=["resource_version"])
            send_event(RequestContext.from_user(owner_id), locked.hierarchy.folders[str(file_obj.parent_id)],
                       EventCode.ITEM_UPDATE, FileSerializer.serialize_object(file_obj))
            return FileCommandResult(str(file_obj.id), file_obj.resource_version)

    @staticmethod
    def move(principal: UserPrincipal, file_ids: list[str], destination_id: str, credentials: CredentialSet | None = None) -> list[FileCommandResult]:
        validate_ids_as_list(file_ids, max_length=10000, child_type=str)
        owner_id = principal.user_id
        with transaction.atomic():
            namespace_lock_service.lock_owner_scope_shared(owner_id)
            locked = lock_files_with_parents(owner_id, file_ids, [destination_id])
            destination = locked.hierarchy.folders[str(destination_id)]
            authorizer.require_move_items(
                principal, destination_id, file_ids=file_ids, credentials=credentials,
                locked_hierarchy=locked.hierarchy, locked_files=locked.files,
            )

            return FileService._move_locked(owner_id, locked, destination)

    @staticmethod
    def _move_locked(owner_id, locked, destination):
        namespace_lock_service._require_transaction()
        moving = [file_obj for file_obj in locked.files.values() if str(file_obj.parent_id) != str(destination.id)]
        if not moving:
            return [FileCommandResult(str(file_obj.id), file_obj.resource_version) for file_obj in locked.files.values()]
        if destination.files.count() + len(moving) > MAX_FILES_IN_FOLDER:
            raise BadRequestError(f"Too many files in folder. Max = {MAX_FILES_IN_FOLDER}")

        deltas: dict[str, dict[str, int]] = {}
        old_parent_ids: set[str] = set()
        new_chain = locked.hierarchy.chain(str(destination.id))
        dirty_ids: set[str] = set(new_chain)
        for file_obj in moving:
            old_chain = locked.hierarchy.chain(str(file_obj.parent_id))
            old_parent_ids.add(str(file_obj.parent_id))
            dirty_ids.update(old_chain)
            merge_delta(
                deltas,
                old_chain,
                physical_descendant_file_count=-1,
                physical_descendant_file_size=-file_obj.size,
                visible_descendant_file_count=-1,
                visible_descendant_file_size=-file_obj.size,
            )
            merge_delta(
                deltas,
                new_chain,
                physical_descendant_file_count=1,
                physical_descendant_file_size=file_obj.size,
                visible_descendant_file_count=1,
                visible_descendant_file_size=file_obj.size,
            )

        stats = {}
        for file_obj in moving:
            contribution = {file_obj.type: {"count": 1, "size": file_obj.size}}
            merge_file_stats(stats, locked.hierarchy.chain(str(file_obj.parent_id)), contribution, -1)
            merge_file_stats(stats, new_chain, contribution)
        moving_ids = [file_obj.id for file_obj in moving]
        moving_by_parent: dict[str, list[File]] = defaultdict(list)
        for file_obj in moving:
            moving_by_parent[str(file_obj.parent_id)].append(file_obj)
        File.objects.filter(id__in=moving_ids).update(parent_id=destination.id, last_modified_at=timezone.now())
        apply_counter_deltas(deltas)
        apply_file_stats_deltas(stats)
        dirty_hashes(dirty_ids)
        bump_file_resources(moving_ids)
        bump_folder_listings({*old_parent_ids, str(destination.id)})
        for old_parent_id, files in moving_by_parent.items():
            for start in range(0, len(files), 250):
                batch = files[start:start + 250]
                send_event(RequestContext.from_user(owner_id), locked.hierarchy.folders[old_parent_id],
                           EventCode.ITEM_MOVE_OUT, [str(file_obj.id) for file_obj in batch])
                for file_obj in batch:
                    file_obj.parent = destination
                    file_obj.resource_version += 1
                send_event(RequestContext.from_user(owner_id), destination, EventCode.ITEM_MOVE_IN,
                           FileSerializer.serialize_many(batch))
        refreshed = File.objects.filter(id__in=locked.files).values_list("id", "resource_version")
        return [FileCommandResult(str(file_id), version) for file_id, version in refreshed]

    @staticmethod
    def trash(principal: UserPrincipal, file_ids: list[str], credentials: CredentialSet | None = None) -> list[FileCommandResult]:
        return _change_trash_state(principal, file_ids, False, credentials)

    @staticmethod
    def restore(principal: UserPrincipal, file_ids: list[str], credentials: CredentialSet | None = None) -> list[FileCommandResult]:
        return _change_trash_state(principal, file_ids, True, credentials)

    @staticmethod
    def request_deletion(principal: UserPrincipal, file_ids: list[str], credentials: CredentialSet | None = None) -> list[FileCommandResult]:
        owner_id = principal.user_id
        with transaction.atomic():
            namespace_lock_service.lock_owner_scope_exclusive(owner_id)
            locked = lock_files_with_parents(owner_id, file_ids)
            authorizer.require_items(
                principal, ResourceAction.REQUEST_DELETE, file_ids=file_ids,
                credentials=credentials, locked_hierarchy=locked.hierarchy, locked_files=locked.files,
            )
            deltas: dict[str, dict[str, int]] = {}
            dirty_ids: set[str] = set()
            parent_ids: set[str] = set()
            results: list[FileCommandResult] = []
            now = timezone.now()
            for file_obj in locked.files.values():
                # REQUEST_DELETE already rejects inherited trash.
                visible = file_obj.trashed_at is None
                scope = DeletionScope.objects.create(
                    owner_id=owner_id,
                    root_file_id=file_obj.id,
                    physical_file_count=1,
                    physical_file_size=file_obj.size,
                    visible_file_count=1 if visible else 0,
                    visible_file_size=file_obj.size if visible else 0,
                )
                if visible:
                    chain = locked.hierarchy.chain(str(file_obj.parent_id))
                    dirty_ids.update(chain)
                    merge_delta(deltas, chain, visible_descendant_file_count=-1, visible_descendant_file_size=-file_obj.size)
                parent_ids.add(str(file_obj.parent_id))
                results.append(FileCommandResult(str(file_obj.id), file_obj.resource_version + 1, str(scope.id)))

            File.objects.filter(id__in=locked.files).update(state=ItemState.DELETING, state_changed_at=now)
            apply_counter_deltas(deltas)
            dirty_hashes(dirty_ids)
            bump_file_resources(locked.files)
            bump_folder_listings(parent_ids)
            send_event(RequestContext.from_user(owner_id), None, EventCode.ITEM_DELETE, list(locked.files))
            return results

    @staticmethod
    def update_media_position(
        principal: UserPrincipal,
        file_id: str,
        position: int,
        credentials: CredentialSet | None = None,
    ) -> MediaPosition:
        position = validate_value(position, int, checks=[NotNegative])
        with transaction.atomic():
            _, file_obj = _authorize_file(principal, file_id, ResourceAction.EDIT_METADATA, credentials)
            media_position, _ = MediaPosition.objects.update_or_create(file_id=file_obj.id, defaults={"timestamp": position})
            bump_file_resources([file_obj.id])
            bump_folder_listings([file_obj.parent_id])
            return media_position

    @staticmethod
    def add_tag(
        principal: UserPrincipal,
        file_id: str,
        tag_name: str,
        credentials: CredentialSet | None = None,
    ) -> Tag:
        tag_name = validate_value(tag_name, str, checks=[NotEmpty, MaxLength(20)])
        owner_id = principal.user_id
        with transaction.atomic():
            _, file_obj = _authorize_file(principal, file_id, ResourceAction.EDIT_METADATA, credentials)
            tag, _ = Tag.objects.get_or_create(owner_id=owner_id, name=tag_name)
            file_obj.tags.add(tag)
            bump_file_resources([file_obj.id])
            bump_folder_listings([file_obj.parent_id])
            return tag

    @staticmethod
    def remove_tag(
        principal: UserPrincipal,
        file_id: str,
        tag_id: str,
        credentials: CredentialSet | None = None,
    ) -> FileCommandResult:
        owner_id = principal.user_id
        with transaction.atomic():
            _, file_obj = _authorize_file(principal, file_id, ResourceAction.EDIT_METADATA, credentials)
            try:
                tag = file_obj.tags.get(id=tag_id, owner_id=owner_id)
            except Tag.DoesNotExist as exception:
                raise ResourceNotFoundError() from exception
            file_obj.tags.remove(tag)
            bump_file_resources([file_obj.id])
            bump_folder_listings([file_obj.parent_id])
            file_obj.refresh_from_db(fields=["resource_version"])
            return FileCommandResult(str(file_obj.id), file_obj.resource_version)

    @staticmethod
    def add_moment(
        principal: UserPrincipal,
        file_id: str,
        data: dict,
        credentials: CredentialSet | None = None,
    ) -> Moment:
        owner_id = principal.user_id
        with transaction.atomic():
            _, file_obj = _authorize_file(principal, file_id, ResourceAction.EDIT_METADATA, credentials)
            if file_obj.type != "Video":
                raise BadRequestError("Moments are only allowed for video files")
            values = _attachment_identity(owner_id, data)
            key, iv = validate_encryption_fields(
                file_obj.encryption_method,
                validate_key(data, "key", str, default=None),
                validate_key(data, "iv", str, default=None),
            )
            values.update({
                "file": file_obj,
                "timestamp": validate_key(data, "timestamp", int, checks=[NotNegative]),
                "size": validate_key(data, "size", int, checks=[IsPositive]),
                "key": key,
                "iv": iv,
            })
            moment = Moment.objects.create(**values)
            bump_file_resources([file_obj.id])
            bump_folder_listings([file_obj.parent_id])
            return moment

    @staticmethod
    def remove_moment(
        principal: UserPrincipal,
        file_id: str,
        moment_id: str,
        credentials: CredentialSet | None = None,
    ) -> FileCommandResult:
        return _remove_related_attachment(principal, file_id, moment_id, Moment, credentials)

    @staticmethod
    def create_subtitle(
        principal: UserPrincipal,
        file_id: str,
        data: dict,
        credentials: CredentialSet | None = None,
    ) -> Subtitle:
        with transaction.atomic():
            _, file_obj = _authorize_file(principal, file_id, ResourceAction.EDIT_METADATA, credentials)
            subtitle = _create_subtitle(file_obj, data)
            bump_file_resources([file_obj.id])
            bump_folder_listings([file_obj.parent_id])
            return subtitle

    @staticmethod
    def rename_subtitle(
        principal: UserPrincipal,
        file_id: str,
        subtitle_id: str,
        language: str,
        credentials: CredentialSet | None = None,
    ) -> FileCommandResult:
        language = validate_value(language, str, checks=[NotEmpty, MaxLength(20)])
        with transaction.atomic():
            _, file_obj = _authorize_file(principal, file_id, ResourceAction.EDIT_METADATA, credentials)
            updated = Subtitle.objects.filter(id=subtitle_id, file_id=file_obj.id).update(language=language)
            if not updated:
                raise ResourceNotFoundError()
            bump_file_resources([file_obj.id])
            bump_folder_listings([file_obj.parent_id])
            file_obj.refresh_from_db(fields=["resource_version"])
            return FileCommandResult(str(file_obj.id), file_obj.resource_version)

    @staticmethod
    def remove_subtitle(
        principal: UserPrincipal,
        file_id: str,
        subtitle_id: str,
        credentials: CredentialSet | None = None,
    ) -> FileCommandResult:
        return _remove_related_attachment(principal, file_id, subtitle_id, Subtitle, credentials)

    @staticmethod
    def _mark_remote_missing_attachment(owner_id: int, file_id: str, fragment_id: str) -> FileCommandResult:
        with transaction.atomic():
            namespace_lock_service.lock_owner_scope_shared(owner_id)
            locked = lock_files_with_parents(owner_id, [file_id])
            file_obj = locked.files[str(file_id)]
            if not Fragment.objects.select_for_update().filter(id=fragment_id, file_id=file_obj.id).exists():
                raise ResourceNotFoundError()
            File.objects.filter(id=file_obj.id).update(state=ItemState.REMOTE_MISSING, state_changed_at=timezone.now())
            dirty_hashes(locked.hierarchy.chain(str(file_obj.parent_id)))
            bump_file_resources([file_obj.id])
            bump_folder_listings([file_obj.parent_id])
            file_obj.refresh_from_db(fields=["resource_version"])
            send_event(RequestContext.from_user(owner_id), locked.hierarchy.folders[str(file_obj.parent_id)], EventCode.ITEM_MOVE_OUT, [str(file_obj.id)])
            return FileCommandResult(str(file_obj.id), file_obj.resource_version)

    @staticmethod
    def _remove_missing_related_attachment(
        owner_id: int,
        file_id: str,
        resource: Moment | Subtitle,
    ) -> FileCommandResult:
        with transaction.atomic():
            namespace_lock_service.lock_owner_scope_shared(owner_id)
            locked = lock_files_with_parents(owner_id, [file_id])
            file_obj = locked.files[str(file_id)]
            deleted, _ = type(resource).objects.filter(id=resource.id, file_id=file_obj.id).delete()
            if not deleted:
                raise ResourceNotFoundError()
            if isinstance(resource, Subtitle):
                adjust_relation_count(file_obj, "subs_count", -1)
            bump_file_resources([file_obj.id])
            bump_folder_listings([file_obj.parent_id])
            file_obj.refresh_from_db(fields=["resource_version"])
            return FileCommandResult(str(file_obj.id), file_obj.resource_version)


file_service = FileService()
