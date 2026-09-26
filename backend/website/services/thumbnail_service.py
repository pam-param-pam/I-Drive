from dataclasses import dataclass
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from website.constants import EventCode, cache
from website.core.Serializers import FileSerializer
from website.core.dataModels.http import RequestContext
from website.core.errors import BadRequestError, ResourceNotFoundError
from website.core.helpers import validate_encryption_fields, validate_key
from website.core.validators.GeneralChecks import IsPositive, IsSnowflake
from website.models import File, Thumbnail
from website.models.mixin_models import DiscordAttachmentMixin
from website.auth.permissions import (
    Authorizer, ContextSet, CredentialSet, ResourceAction,
    ResourceContextResolver, UserPrincipal)
from website.queries.selectors import (check_if_bots_exists, get_discord_author, get_discord_channel)
from website.services import namespace_lock_service
from website.services.derived_state_service import (bump_file_resources, bump_folder_listings)
from website.services.namespace_command_support import (FileCommandContext, lock_files_and_parents)
from website.services import cache_service
from website.websockets.utils import send_event


authorizer = Authorizer()
context_resolver = ResourceContextResolver()


@dataclass(frozen=True)
class ThumbnailMutationResult:
    file_id: str
    resource_version: int
    removed_attachments: tuple[DiscordAttachmentMixin, ...] = ()


def _validated_thumbnail_values(command_context: FileCommandContext, file_id: str, data: dict) -> dict:
    file_obj = command_context.require_locked_file(file_id)
    if file_obj.type not in ("Video", "Raw image", "Image", "Audio"):
        raise BadRequestError(f"Thumbnail is not allowed for file type: {file_obj.type}")

    channel_id = validate_key(data, "channel_id", str, checks=[IsSnowflake])
    author_id = validate_key(data, "message_author_id", str, checks=[IsSnowflake])
    key, iv = validate_encryption_fields(
        file_obj.encryption_method,
        validate_key(data, "key", str, default=None),
        validate_key(data, "iv", str, default=None),
    )
    author = get_discord_author(command_context.owner_id, author_id)
    values = {
        "file": file_obj,
        "size": validate_key(data, "size", int, checks=[IsPositive]),
        "key": key,
        "iv": iv,
        "channel": get_discord_channel(command_context.owner_id, channel_id),
        "message_id": validate_key(data, "message_id", str, checks=[IsSnowflake]),
        "attachment_id": validate_key(data, "attachment_id", str, checks=[IsSnowflake]),
        "content_type": ContentType.objects.get_for_model(author),
        "object_id": author.discord_id,
    }
    return values


def _existing_thumbnail_rows(file_obj: File) -> tuple[Thumbnail, ...]:
    return tuple(
        Thumbnail.objects.select_for_update()
        .select_related("channel", "content_type")
        .filter(file_id=file_obj.id)
    )


class ThumbnailService:
    @staticmethod
    def _cleanup_cache(file_id: str, resource_version: int) -> None:
        cache.delete_many([
            cache_service.get_thumbnail_key(file_id),
            cache_service.get_thumbnail_key(file_id, resource_version - 1),
        ])

    @staticmethod
    def _cleanup_committed_cache(file_id: str) -> None:
        resource_version = File.objects.filter(id=file_id).values_list("resource_version", flat=True).first()
        if resource_version is not None:
            ThumbnailService._cleanup_cache(file_id, resource_version)

    @staticmethod
    def add_to_new_file(command_context: FileCommandContext, file_id: str, data: dict) -> Thumbnail:
        values = _validated_thumbnail_values(command_context, file_id, data)
        return Thumbnail.objects.create(**values)

    @staticmethod
    def remove_during_content_replacement(command_context: FileCommandContext, file_id: str) -> tuple[Thumbnail, ...]:
        file_obj = command_context.require_locked_file(file_id)
        existing = _existing_thumbnail_rows(file_obj)
        Thumbnail.objects.filter(file_id=file_obj.id).delete()
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
            command_context = lock_files_and_parents(owner_id, [file_id])
            file_obj = command_context.require_locked_file(file_id)
            deleted, _ = Thumbnail.objects.filter(id=thumbnail_id, file_id=file_obj.id).delete()
            if not deleted:
                raise ResourceNotFoundError()
            bump_file_resources([file_obj.id])
            bump_folder_listings([file_obj.parent_id])
            file_obj.refresh_from_db(fields=["resource_version"])
            result = ThumbnailMutationResult(str(file_obj.id), file_obj.resource_version)
        ThumbnailService._cleanup_cache(result.file_id, result.resource_version)
        return result

    @staticmethod
    def _finish(principal: UserPrincipal, result: ThumbnailMutationResult) -> None:
        ThumbnailService._cleanup_cache(result.file_id, result.resource_version)
        owner = User.objects.get(id=principal.user_id)
        if result.removed_attachments:
            from website.services import attachment_service

            for attachment in result.removed_attachments:
                attachment_service.delete_remote_single_discord_attachment(owner, attachment)
        file_obj = File.objects.select_related("parent").get(id=result.file_id)
        send_event(RequestContext.from_user(owner.id), file_obj.parent, EventCode.ITEM_UPDATE,
                   FileSerializer.serialize_object(file_obj))

    @staticmethod
    def _change(principal: UserPrincipal, file_id: str, replacement: dict | None, must_exist: bool, credentials: CredentialSet | None) -> ThumbnailMutationResult:
        owner_id = principal.user_id
        with transaction.atomic():
            namespace_lock_service.lock_owner_scope_shared(owner_id)
            command_context = lock_files_and_parents(owner_id, [file_id])
            file_obj = command_context.require_locked_file(file_id)
            context = context_resolver.resolve_file(file_id, owner_id, command_context.hierarchy)
            authorizer.authorize_user_action(
                principal, ResourceAction.EDIT_METADATA, ContextSet((context,)), credentials,
            )
            check_if_bots_exists(owner_id)
            values = None
            if replacement is not None:
                values = _validated_thumbnail_values(command_context, file_id, replacement)
            old = _existing_thumbnail_rows(file_obj)
            if replacement is None and not old:
                if must_exist:
                    raise ResourceNotFoundError()
                return ThumbnailMutationResult(str(file_obj.id), file_obj.resource_version)

            Thumbnail.objects.filter(file_id=file_obj.id).delete()
            if values is not None:
                Thumbnail.objects.create(**values)
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
