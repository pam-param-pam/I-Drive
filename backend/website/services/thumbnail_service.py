from dataclasses import dataclass
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from website.queries.display import load_file_display
from website.constants import EventCode, cache
from website.core.Serializers import FileSerializer
from website.core.http.context import RequestContext
from website.core.errors import BadRequestError, ResourceNotFoundError
from website.core.helpers import validate_encryption_fields, validate_key
from website.core.validators.GeneralChecks import IsPositive, IsSnowflake
from website.models import File, Thumbnail
from website.models.mixin_models import DiscordAttachmentMixin
from website.auth.permissions import (
    CredentialSet, ResourceAction, ResourceType, UserPrincipal)
from website.queries.selectors import (check_if_bots_exists, get_discord_author, get_discord_channel)
from website.services import namespace_lock_service
from website.services.derived_state_service import (bump_file_resources, bump_folder_listings)
from website.services import cache_service
from website.services.file_service import lock_files_with_parents, set_thumbnail
from website.websockets.utils import send_event
from website.auth.permissions.engine import permissions


@dataclass(frozen=True)
class ThumbnailMutationResult:
    file_id: str
    resource_version: int
    removed_attachments: tuple[DiscordAttachmentMixin, ...] = ()


def _validated_thumbnail_values(file_obj: File, data: dict) -> dict:
    if file_obj.type not in ("Video", "Raw image", "Image", "Audio"):
        raise BadRequestError(f"Thumbnail is not allowed for file type: {file_obj.type}")

    channel_id = validate_key(data, "channel_id", str, checks=[IsSnowflake])
    author_id = validate_key(data, "message_author_id", str, checks=[IsSnowflake])
    key, iv = validate_encryption_fields(
        file_obj.encryption_method,
        validate_key(data, "key", str, default=None),
        validate_key(data, "iv", str, default=None),
    )
    author = get_discord_author(file_obj.owner_id, author_id)
    values = {
        "file": file_obj,
        "size": validate_key(data, "size", int, checks=[IsPositive]),
        "key": key,
        "iv": iv,
        "channel": get_discord_channel(file_obj.owner_id, channel_id),
        "message_id": validate_key(data, "message_id", str, checks=[IsSnowflake]),
        "attachment_id": validate_key(data, "attachment_id", str, checks=[IsSnowflake]),
        "author": author,
    }
    return values


def _existing_thumbnail_rows(file_obj: File) -> tuple[Thumbnail, ...]:
    return tuple(
        Thumbnail.objects.select_for_update()
        .select_related("channel", "author")
        .filter(file_id=file_obj.id)
    )


class ThumbnailService:
    @staticmethod
    def _cleanup_cache(file_id: str) -> None:
        cache.delete(cache_service.get_thumbnail_key(file_id))

    @staticmethod
    def _cleanup_committed_cache(file_id: str) -> None:
        ThumbnailService._cleanup_cache(file_id)

    @staticmethod
    def add_to_new_file(file_obj: File, data: dict) -> Thumbnail:
        values = _validated_thumbnail_values(file_obj, data)
        thumbnail = Thumbnail.objects.create(**values)
        set_thumbnail(file_obj, thumbnail)
        return thumbnail

    @staticmethod
    def remove_during_content_replacement(file_obj: File) -> tuple[Thumbnail, ...]:
        existing = _existing_thumbnail_rows(file_obj)
        Thumbnail.objects.filter(file_id=file_obj.id).delete()
        set_thumbnail(file_obj)
        if existing:
            transaction.on_commit(
                lambda committed_file_id=str(file_obj.id):
                ThumbnailService._cleanup_committed_cache(committed_file_id)
            )
        return existing

    @staticmethod
    def _remove_missing_thumbnail_attachment(owner_id: int, file_id: str, thumbnail_id: str) -> ThumbnailMutationResult:
        with transaction.atomic():
            namespace_lock_service.lock_owner_scope_shared(owner_id)
            locked = lock_files_with_parents(owner_id, [file_id])
            file_obj = locked.files[str(file_id)]
            deleted, _ = Thumbnail.objects.filter(id=thumbnail_id, file_id=file_obj.id).delete()
            if not deleted:
                raise ResourceNotFoundError()
            set_thumbnail(file_obj)
            bump_file_resources([file_obj.id])
            bump_folder_listings([file_obj.parent_id])
            file_obj.refresh_from_db(fields=["resource_version"])
            result = ThumbnailMutationResult(str(file_obj.id), file_obj.resource_version)
        ThumbnailService._cleanup_cache(result.file_id)
        return result

    @staticmethod
    def _finish(principal: UserPrincipal, result: ThumbnailMutationResult) -> None:
        ThumbnailService._cleanup_cache(result.file_id)
        owner = User.objects.get(id=principal.user_id)
        if result.removed_attachments:
            from website.services import attachment_service

            for attachment in result.removed_attachments:
                attachment_service.delete_remote_single_discord_attachment(owner, attachment)
        file_obj = File.objects.select_related("parent").get(id=result.file_id)
        send_event(RequestContext.from_user(owner.id), file_obj.parent, EventCode.ITEM_UPDATE,
                   FileSerializer.serialize_dict(load_file_display(file_obj.id, file_obj.owner_id)))

    @staticmethod
    def _change(principal: UserPrincipal, file_id: str, replacement: dict | None, must_exist: bool, credentials: CredentialSet | None) -> ThumbnailMutationResult:
        owner_id = principal.user_id
        with transaction.atomic():
            namespace_lock_service.lock_owner_scope_shared(owner_id)
            locked = lock_files_with_parents(owner_id, [file_id])
            file_obj = locked.files[str(file_id)]
            permissions.authorize(ResourceAction.EDIT_METADATA, principal, file_id, credentials,
                resource_type=ResourceType.FILE, locked_hierarchy=locked.hierarchy, locked_files=locked.files,
            )
            check_if_bots_exists(owner_id)
            values = None
            if replacement is not None:
                values = _validated_thumbnail_values(file_obj, replacement)
            old = _existing_thumbnail_rows(file_obj)
            if replacement is None and not old:
                if must_exist:
                    raise ResourceNotFoundError()
                return ThumbnailMutationResult(str(file_obj.id), file_obj.resource_version)

            Thumbnail.objects.filter(file_id=file_obj.id).delete()
            thumbnail = Thumbnail.objects.create(**values) if values is not None else None
            set_thumbnail(file_obj, thumbnail)
            File.objects.filter(id=file_obj.id).update(last_modified_at=timezone.now())
            bump_file_resources([file_obj.id])
            bump_folder_listings([file_obj.parent_id])
            file_obj.refresh_from_db(fields=["resource_version"])
            result = ThumbnailMutationResult(str(file_obj.id), file_obj.resource_version, old)
        ThumbnailService._finish(principal, result)
        return result

    @staticmethod
    def replace(principal: UserPrincipal, file_id: str, data: dict, credentials: CredentialSet | None = None) -> ThumbnailMutationResult:
        return ThumbnailService._change(principal, file_id, data, False, credentials)

    @staticmethod
    def remove(principal: UserPrincipal, file_id: str, must_exist: bool = False, credentials: CredentialSet | None = None) -> ThumbnailMutationResult:
        return ThumbnailService._change(principal, file_id, None, must_exist, credentials)


thumbnail_service = ThumbnailService()
