import datetime

import easy
from django.contrib import admin
from django.urls import reverse

from website.constants import API_BASE_URL, EncryptionMethod
from website.core.crypto.signer import sign_resource
from website.core.errors import DiscordError
from website.models import Fragment, Folder, File, UserSettings, UserPerms, ShareableLink, Thumbnail, UserZIP, MediaPosition, Tag, Webhook, Bot, DiscordSettings, Moment, \
    VideoMetadata, VideoTrack, AudioTrack, SubtitleTrack, Subtitle, Channel, ShareAccess, PerDeviceToken, ShareAccessEvent
from website.models.delete_models import DeletionJob
from website.models.namespace_models import (
    FolderHashWork,
    FolderHeightRepair,
    FolderLockScope,
    NamespaceOperation,
)
from website.models.file_related_models import RawMetadata, PhotoMetadata
from website.models.other_models import Notification, RawExtractionClaim
from website.queries.resource_loader import ResourceLoader
from website.services import attachment_service

from .base import IDriveHistoryAdmin, IDriveModelAdmin


admin.site.index_template = "admin/idrive_index.html"

admin.site.register(UserSettings, IDriveHistoryAdmin)
admin.site.register(UserPerms, IDriveHistoryAdmin)
admin.site.register(DiscordSettings, IDriveHistoryAdmin)

admin.site.register(VideoTrack, IDriveModelAdmin)
admin.site.register(AudioTrack, IDriveModelAdmin)
admin.site.register(SubtitleTrack, IDriveModelAdmin)

admin.site.register(MediaPosition, IDriveModelAdmin)

admin.site.register(RawExtractionClaim, IDriveModelAdmin)


@admin.register(FolderLockScope)
class FolderLockScopeAdmin(IDriveModelAdmin):
    list_display = ("folder", "owner", "created_at", "updated_at")
    list_select_related = ("folder", "owner")
    exclude = ("password",)


@admin.register(FolderHashWork)
class FolderHashWorkAdmin(IDriveModelAdmin):
    list_display = ("folder", "created_at", "updated_at")
    list_select_related = ("folder",)


@admin.register(FolderHeightRepair)
class FolderHeightRepairAdmin(IDriveModelAdmin):
    list_display = ("folder", "created_at", "updated_at")
    list_select_related = ("folder",)


@admin.register(NamespaceOperation)
class NamespaceOperationAdmin(IDriveModelAdmin):
    list_display = ("id", "action", "state", "user_id", "request_id", "progress",
                    "destination_id", "next_attempt_at", "last_error")
    list_filter = ("action", "state")
    search_fields = ("id", "request_context__user_id", "request_context__request_id", "destination_id")
    ordering = ("state", "id")

    @admin.display(description="User ID")
    def user_id(self, obj):
        return obj.request_context["user_id"]

    @admin.display(description="Request ID")
    def request_id(self, obj):
        return obj.request_context["request_id"]

    @admin.display(description="Progress")
    def progress(self, obj):
        return f"{obj.cursor} / {len(obj.refs)}"


@admin.register(Fragment)
class FragmentAdmin(IDriveHistoryAdmin):
    readable_size = ["size"]
    hex = ["crc"]
    readonly_fields = ('fragment_url', 'jump')
    ordering = ["-created_at"]
    list_display = ["sequence", "file_name", "size", "owner", "folder", "created_at"]
    list_select_related = ["file"]
    search_fields = ["file__name", 'file__owner__username', "message_id"]

    @easy.with_tags()
    @easy.smart(short_description="Open fragment by sequence", allow_tags=True)
    def jump(self, obj: Fragment):
        # cursed stuff!
        mapping = {
            frag.sequence: frag.id
            for frag in obj.file.fragments.all()
        }

        base = "/adminwebsite/fragment/"

        return (
            f"<script>var fragMap = {mapping};</script>"
            f'<a href="#" '
            f'onclick="var s = prompt(`Sequence:`); '
            f'if(!s) return false; '
            f'var id = fragMap[s]; '
            f'if(!id) {{ alert(`No fragment with sequence `+s); return false; }} '
            f'window.location = `{base}` + id + `/change/`; '
            f'return false;">Open fragment…</a>'
        )

    @easy.smart(short_description="Owner", admin_order_field="file__owner__username")
    def owner(self, obj: Fragment):
        return obj.file.owner


    @easy.smart(short_description="Folder", admin_order_field="file__parent__name")
    def folder(self, obj: Fragment):
        return f"{obj.file.parent.name}({obj.file.parent.id})"

    @easy.smart(short_description="File name", admin_order_field="file__name")
    def file_name(self, obj: Fragment):
        name = obj.file.name
        if len(name) < 100:
            return name
        return "*File name too long to display*"

    @easy.with_tags()
    @easy.smart(short_description="URL", allow_tags=True)
    def fragment_url(self, obj: Fragment):
        try:
            url = attachment_service.get_attachment_url(obj.file.owner, obj, obj.file.name)
            return f'<a href="{url}" target="_blank">{url}</a><br>'
        except DiscordError as e:
            return f"FAILED TO FETCH URL: {str(e)}"


@admin.register(Folder)
class FolderAdmin(IDriveHistoryAdmin):
    ordering = ["-created_at"]
    list_display = ["name", "owner", "state", "created_at", "is_trashed", "is_locked"]
    search_fields = ["id", "name"]

    @easy.smart(short_description="Is locked", boolean=True)
    def is_locked(self, obj: Folder):
        context = ResourceLoader().resolve_folder(str(obj.id), obj.owner_id)
        return context.is_locked

    @easy.smart(short_description="In trash", boolean=True)
    def is_trashed(self, obj: Folder):
        return obj.trashed_at is not None


@admin.register(File)
class FileAdmin(IDriveHistoryAdmin):
    readable_size = ["size"]
    hex = ["crc"]
    base64 = ["key", "iv"]
    exclude = ('encryption_method', )
    readonly_fields = ('is_locked', 'formatted_encryption_method', 'media_tag')
    ordering = ["-created_at"]
    list_display = ['name', 'parent', 'size', 'owner', 'state', 'type', 'created_at', 'is_trashed', 'is_locked']
    search_fields = ['name', 'id', 'type', 'owner__username']

    @easy.smart(short_description="Locked", boolean=True)
    def is_locked(self, obj: File):
        context = ResourceLoader().resolve_file(str(obj.id), obj.owner_id)
        return context.is_locked

    @easy.smart(short_description="In trash", boolean=True)
    def is_trashed(self, obj: File):
        return obj.trashed_at is not None


    @easy.smart(short_description="Encryption method")
    def formatted_encryption_method(self, obj: File):
        return obj.get_encryption_method().name

    @easy.with_tags()
    @easy.smart(short_description="Preview")
    def media_tag(self, obj: File):
        file_path = f"/files/{obj.id}/stream"
        file_signed = sign_resource(file_path)
        file_url = f"{API_BASE_URL}{file_path}{file_signed}"

        thumb_path = f"/files/{obj.id}/thumbnail/{obj.thumbnail.id}/stream"
        thumb_signed = sign_resource(thumb_path)
        thumb_url = f"{API_BASE_URL}{thumb_path}{thumb_signed}"

        # Video preview
        if obj.type == "Video":
            return (
                f'<video controls style="width:100%; height:auto;" poster="{thumb_url}">'
                f'<source src="{file_url}" type="video/mp4"></video>'
            )

        # Audio preview
        if obj.type == "Audio":
            return (
                '<div style="display:flex; align-items:center;">'
                f'<img src="{thumb_url}" style="width:100px; height:100px; margin-right:10px;">'
                f'<audio controls><source src="{file_url}" type="audio/mpeg"></audio>'
                '</div>'
            )
        if obj.type == "Image":
            return (
                f'<a href="{file_url}" target="_blank" style="display:inline-block;">'
                f'<img src="{file_url}" '
                f'style="max-width:100%; height:auto; width:auto; object-fit:contain; '
                f'border-radius:6px; border:1px solid #ddd;" />'
                f'</a>'
            )
        if obj.type == "Raw image":
            return (
                f'<a href="{thumb_url}" target="_blank" style="display:inline-block;">'
                f'<img src="{thumb_url}" '
                f'style="max-width:100%; height:auto; width:auto; object-fit:contain; '
                f'border-radius:6px; border:1px solid #ddd;" />'
                f'</a>'
            )

        # Otherwise: default link
        return f'<a href="{file_url}" target="_blank">{file_url}</a>'


@admin.register(Thumbnail)
class ThumbnailAdmin(IDriveHistoryAdmin):
    readable_size = ["size"]
    base64 = ["key", "iv"]
    search_fields = ['file__name', 'file__id', 'file__owner__username']
    ordering = ['-created_at']
    list_display = ['file_name', 'owner', 'size', 'created_at']
    readonly_fields = ('thumbnail_media', 'encryption_method')

    @easy.smart(short_description="File name", admin_order_field="file__name")
    def file_name(self, obj: Thumbnail):
        return obj.file.name

    @easy.smart(short_description="Owner", admin_order_field="file__owner__username")
    def owner(self, obj: Thumbnail):
        return obj.file.owner


    @easy.with_tags()
    @easy.smart(short_description="Preview thumbnail", allow_tags=True)
    def thumbnail_media(self, obj: Thumbnail):
        thumb_path = f"/files/{obj.file.id}/thumbnail/{obj.id}/stream"
        thumb_signed = sign_resource(thumb_path)
        thumb_url = f"{API_BASE_URL}{thumb_path}{thumb_signed}"

        return f'<img src="{thumb_url}" style="width:350px; height:auto;">'

    @easy.smart(short_description="Encryption method")
    def encryption_method(self, obj: Thumbnail):
        return EncryptionMethod(obj.file.encryption_method).name


@admin.register(ShareableLink)
class ShareableLinkAdmin(IDriveModelAdmin):
    list_display = ('id', 'resource_link', 'get_type', 'owner', 'is_expired', 'expiration_time', 'created_at')
    readonly_fields = ('resource_link', 'root_id', 'get_type', 'is_expired')

    @easy.with_tags()
    @easy.smart(short_description="Resource")
    def resource_link(self, obj: ShareableLink):
        resource = obj.root
        model = type(resource)
        url = reverse(f"admin:{model._meta.app_label}_{model._meta.model_name}_change", args=[obj.root_id])

        return f'<a href="{url}">{resource.name}</a>'

    @easy.smart(short_description="Expired?", admin_order_field="expiration_time", bool=True)
    def is_expired(self, obj: ShareableLink):
        return obj.is_expired()

@admin.register(UserZIP)
class UserZIPAdmin(IDriveModelAdmin):
    list_display = ("owner_id", "created_at")
    ordering = ["-created_at"]


@admin.register(Tag)
class TagAdmin(IDriveHistoryAdmin):
    list_display = ['name', 'owner', 'amount_of_files']
    search_fields = ('name',)
    readonly_fields = ('file_list',)

    @easy.with_tags()
    @easy.smart(short_description="Files", allow_tags=True)
    def file_list(self, obj: Tag):
        qs = obj.files.all()
        if not qs.exists():
            return "No files"

        rows = []
        for f in qs:
            url = reverse(f"admin:{f._meta.app_label}_file_change", args=[f.id])
            rows.append(f'<a href="{url}">{f.name}</a>')

        return "<br>".join(rows)

    @easy.smart(short_description="File count", admin_order_field="files__count")
    def amount_of_files(self, obj: Tag):
        return obj.files.count()


@admin.register(Channel)
class ChannelAdmin(IDriveModelAdmin):
    search_fields = ('discord_id', 'name')
    list_display = ['name', 'owner', 'discord_id', 'guild_id', 'created_at']


@admin.register(Webhook)
class WebhookAdmin(IDriveModelAdmin):
    search_fields = ('name', 'discord_id')
    list_display = ['name', 'owner', 'created_at']


@admin.register(Bot)
class BotAdmin(IDriveModelAdmin):
    search_fields = ('name', 'discord_id')
    list_display = ['name', 'owner', 'created_at']


@admin.register(Moment)
class MomentAdmin(IDriveModelAdmin):
    readable_size = ["size"]
    base64 = ["key", "iv"]
    search_fields = ('file__name', 'file__owner__username')
    list_display = ['file', 'owner', 'formatted_timestamp', 'size']
    readonly_fields = ('formatted_timestamp', 'moment_preview', 'encryption_method')
    exclude = ['timestamp']

    @easy.with_tags()
    @easy.smart(short_description="Preview", allow_tags=True)
    def moment_preview(self, obj: Moment):
        moment_path = f"/files/{obj.file.id}/moments/{obj.id}/stream"
        moment_signed = sign_resource(moment_path)
        moment_url = f"{API_BASE_URL}{moment_path}{moment_signed}"

        return f'<img src="{moment_url}" style="width:350px; height:auto;">'

    @easy.smart(short_description="Owner", admin_order_field="file__owner__username")
    def owner(self, obj: Moment):
        return obj.file.owner

    @easy.smart(short_description="Timestamp", admin_order_field="timestamp")
    def formatted_timestamp(self, obj: Moment):
        return str(datetime.timedelta(seconds=obj.timestamp))


    @easy.smart(short_description="Encryption method")
    def encryption_method(self, obj: Moment):
        return EncryptionMethod(obj.file.encryption_method).name


@admin.register(VideoMetadata)
class VideoMetadataAdmin(IDriveModelAdmin):
    search_fields = ('file__name', 'file__id')
    list_display = ['file', 'owner', 'created_at']

    @easy.smart(short_description="Owner")
    def owner(self, obj: VideoMetadata):
        return obj.file.owner

@admin.register(RawMetadata)
class RawMetadataAdmin(IDriveModelAdmin):
    search_fields = ('file__name', 'file__id')
    list_display = ['file', 'owner', 'created_at', 'failed_to_process']

    @easy.smart(short_description="Owner")
    def owner(self, obj: RawMetadata):
        return obj.file.owner

@admin.register(PhotoMetadata)
class PhotoMetadataAdmin(IDriveModelAdmin):
    search_fields = ('file__name', 'file__id')
    list_display = ['file', 'owner', 'created_at']

    @easy.smart(short_description="Owner")
    def owner(self, obj: PhotoMetadata):
        return obj.file.owner

@admin.register(Subtitle)
class SubtitleAdmin(IDriveModelAdmin):
    readable_size = ["size"]
    base64 = ["key", "iv"]
    ordering = ['-file__internal_created_at']

    search_fields = ('file__name', 'file__id', 'file__owner__username')
    list_display = ['file_name', 'language', 'owner', 'size']
    readonly_fields = ('encryption_method', 'sub_preview')

    @easy.with_tags()
    @easy.smart(short_description="Subtitle Preview", allow_tags=True)
    def sub_preview(self, obj: Subtitle):
        subtitle_path = f"/files/{obj.file.id}/subtitles/{obj.id}/stream"
        subtitle_signed = sign_resource(subtitle_path)
        subtitle_url = f"{API_BASE_URL}{subtitle_path}{subtitle_signed}&inline=true"

        return f'<a href="{subtitle_url}" target="_blank">Preview Subtitle</a>'


    @easy.smart(short_description="Encryption method")
    def encryption_method(self, obj: Subtitle):
        return EncryptionMethod(obj.file.encryption_method).name

    @easy.smart(short_description="File Name", admin_order_field="file__name")
    def file_name(self, obj: Subtitle):
        return obj.file.name

    @easy.smart(short_description="Owner", admin_order_field="file__owner__username")
    def owner(self, obj: Subtitle):
        return obj.file.owner.username


@admin.register(ShareAccess)
class ShareAccessAdmin(IDriveModelAdmin):
    ordering = ["-access_time"]
    readonly_fields = ('readable_accessed_by',)
    list_display = ['share', 'readable_accessed_by', 'ip', 'user_agent']
    exclude = ['accessed_by']

    @easy.smart(short_description="Accessed by")
    def readable_accessed_by(self, obj: ShareAccess):
        return obj.accessed_by.username if obj.accessed_by else "Unknown (Anonymous)"


@admin.register(ShareAccessEvent)
class ShareAccessEventAdmin(IDriveModelAdmin):
    ordering = ["-timestamp"]
    search_fields = ('event_type', 'metadata')
    list_display = ('readable_accessed_by', 'event_type', 'ip', 'user_agent', 'timestamp')

    @easy.smart(short_description="Accessed by")
    def readable_accessed_by(self, obj: ShareAccessEvent):
        return obj.access.accessed_by.username if obj.access.accessed_by else "Unknown (Anonymous)"

    @easy.smart(short_description="IP")
    def ip(self, obj: ShareAccessEvent):
        return obj.access.ip

    @easy.smart(short_description="User agent")
    def user_agent(self, obj: ShareAccessEvent):
        return obj.access.user_agent

@admin.register(Notification)
class NotificationAdmin(IDriveModelAdmin):
    list_display = ['owner', 'type', 'title', 'message', 'is_read', 'is_deleted']


@admin.register(DeletionJob)
class DeletionJobAdmin(IDriveModelAdmin):
    ordering = ['-created_at']
    list_display = ['id', 'requested_by', 'state', 'last_progress_percentage', 'done_file_items', 'total_file_items', 'done_folder_items', 'total_folder_items', 'heartbeat_at']
    list_filter = ['state']
    list_select_related = ['requested_by']


@admin.register(PerDeviceToken)
class PerDeviceTokenAdmin(IDriveModelAdmin):
    list_display = ['user', 'device_type', 'last_used_at', 'country', 'city']
