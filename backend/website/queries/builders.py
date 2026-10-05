from website.queries.display import load_file_display
from website.queries.resource_loader import ResourceLoader
import time
from typing import Dict
from typing import List, Iterable

from rest_framework.exceptions import ValidationError

from website.core.Serializers import ShareFolderSerializer, ShareFileSerializer, WebhookSerializer, BotSerializer, ShareAccessEventSerializer
from website.core.helpers import normalize_blocked_until
from website.discord.Discord import discord
from website.models import Folder, File, Channel, Webhook, Bot, ShareAccessEvent
from website.queries.hierarchy import get_folder_chain
from website.auth.permissions import ResourceRef, ResourceType


def build_breadcrumbs(folder_obj: Folder) -> List[dict]:
    breadcrumbs = []
    folder_obj.refresh_from_db()
    ancestors = get_folder_chain(str(folder_obj.id))
    contexts = ResourceLoader().resolve_many(
        (ResourceRef(ResourceType.FOLDER, ancestor.id) for ancestor in ancestors),
        folder_obj.owner_id,
    )
    lock_from_by_id = {
        context.resource_id: context.effective_lock_scope_id for context in contexts
    }
    for ancestor in ancestors:
        lock_from = lock_from_by_id[str(ancestor.id)]
        data = {"name": ancestor.name, "id": ancestor.id, "lockFrom": lock_from}
        breadcrumbs.append(data)

    return breadcrumbs


def build_share_resource_dict(resource_in_share: Folder | File) -> Dict:
    if isinstance(resource_in_share, Folder):
        resource_dict = ShareFolderSerializer.serialize_object(resource_in_share)
    else:
        resource_dict = ShareFileSerializer.serialize_dict(load_file_display(resource_in_share.id, resource_in_share.owner_id))

    return resource_dict


def build_share_folder_content(folder_obj: Folder, children) -> Dict:
    """Format the authorizer's checked listing without another visibility query."""
    rows = [ShareFileSerializer.serialize_dict(item) if isinstance(item, dict)
            else ShareFolderSerializer.serialize_object(item) for item in children]
    folder_dict = build_share_resource_dict(folder_obj)
    folder_dict["children"] = rows
    return folder_dict


def _add_credential_status(data, cred):
    if cred:
        data["is_blocked"] = bool(
            cred.blocked_until and cred.blocked_until > time.time()
        )
        data["blocked_until"] = normalize_blocked_until(cred.blocked_until)
        data["block_reason"] = cred.block_reason
        data["discord_error_code"] = cred.discord_error_code
    else:
        data["is_blocked"] = False

    return data

def build_discord_settings(user) -> dict:
    settings = user.discordsettings
    webhooks = Webhook.objects.filter(owner=user).select_related("channel").order_by('created_at')
    bots = Bot.objects.filter(owner=user).order_by('created_at')
    channels_count = Channel.objects.filter(owner=user).count()

    if settings.auto_setup_complete:
        state = discord.get_user_state(user)
        credential_map = state.get_all_credentials()
    else:
        credential_map = {}

    webhook_dicts = []
    for webhook in webhooks:
        data = WebhookSerializer.serialize_object(webhook)
        cred = credential_map.get(webhook.url)

        webhook_dicts.append(_add_credential_status(data, cred))

    bots_dicts = []
    for bot in bots:
        data = BotSerializer.serialize_object(bot)
        cred = credential_map.get(bot.token)

        bots_dicts.append(_add_credential_status(data, cred))

    can_add_bots_or_webhooks = bool(settings.guild_id and channels_count > 0)

    return {
        "webhooks": webhook_dicts,
        "bots": bots_dicts,
        "guild_id": settings.guild_id,
        "attachment_name": settings.attachment_name,
        "can_add_bots_or_webhooks": can_add_bots_or_webhooks,
        "auto_setup_complete": settings.auto_setup_complete,
    }


def create_share_events(events: Iterable[ShareAccessEvent]):
    serialized = ShareAccessEventSerializer.serialize_objects(events)

    file_ids = {
        e.metadata.get("file_id")
        for e in events
        if e.metadata and "file_id" in e.metadata
    }

    folder_ids = {
        e.metadata.get("folder_id")
        for e in events
        if e.metadata and "folder_id" in e.metadata
    }

    files = {
        f.id: f.name
        for f in File.objects.filter(id__in=file_ids).only("id", "name")
    }

    folders = {
        f.id: f.name
        for f in Folder.objects.filter(id__in=folder_ids).only("id", "name")
    }

    for event_dict in serialized:
        metadata = event_dict.get("metadata") or {}

        file_id = metadata.get("file_id")
        if file_id and file_id in files:
            metadata["file_name"] = files[file_id]

        folder_id = metadata.get("folder_id")
        if folder_id and folder_id in folders:
            metadata["folder_name"] = folders[folder_id]

    return serialized


def build_file_path(file: File, max_folder_id=None) -> str:
    folder = file.parent

    if folder is None:
        if max_folder_id is not None:
            raise ValidationError("folder_id is not an ancestor of this file.")

        return file.name

    folder_parts = [{"id": item.id, "name": item.name} for item in get_folder_chain(str(folder.id))]

    if max_folder_id is not None:
        max_folder_id = str(max_folder_id)

        try:
            max_folder_index = next(
                index
                for index, folder_part in enumerate(folder_parts)
                if str(folder_part["id"]) == max_folder_id
            )
        except StopIteration:
            raise ValidationError("folder_id is not an ancestor of this file.")

        # include max_folder_id itself
        folder_parts = folder_parts[max_folder_index:]

    folder_names = [folder_part["name"] for folder_part in folder_parts]

    return "/".join([*folder_names, file.name])
