from website.queries.resource_loader import ResourceLoader
import datetime
from typing import Union, List

import easy
from django.contrib import admin
from django.db.models import QuerySet
from django.template.defaultfilters import filesizeformat
from django.urls import reverse
from simple_history.admin import SimpleHistoryAdmin

from website.services import attachment_service
from website.auth.permissions import CredentialSet, PrincipalFactory
from website.constants import API_BASE_URL, EncryptionMethod
from website.core.crypto.signer import sign_resource
from website.core.errors import DiscordError
from website.models import Fragment, Folder, File, UserSettings, UserPerms, ShareableLink, Thumbnail, UserZIP, MediaPosition, Tag, Webhook, Bot, DiscordSettings, Moment, \
    VideoMetadata, VideoTrack, AudioTrack, SubtitleTrack, Subtitle, Channel, ShareAccess, PerDeviceToken, ShareAccessEvent
from website.models.delete_models import DeletionFileWorkItem, DeletionFolderWorkItem
from website.models.namespace_models import (
    DeletionScope,
    FolderHashWork,
    FolderHeightRepair,
    FolderLockScope,
    NamespaceOperation,
)
from website.models.file_related_models import RawMetadata, PhotoMetadata
from website.models.other_models import Notification, RawExtractionClaim
from website.services import namespace_service, auth_service, thumbnail_service


def _request_admin_deletion(request, objects):
    principal = PrincipalFactory.from_authenticated_request(request)
    namespace_service.request_deletion(
        principal,
        [str(obj.id) for obj in objects],
        CredentialSet.empty(),
    )

admin.site.index_template = "admin/idrive_index.html"

admin.site.register(UserSettings, SimpleHistoryAdmin)
admin.site.register(UserPerms, SimpleHistoryAdmin)
admin.site.register(DiscordSettings, SimpleHistoryAdmin)

admin.site.register(VideoTrack)
admin.site.register(AudioTrack)
admin.site.register(SubtitleTrack)

admin.site.register(MediaPosition)

admin.site.register(RawExtractionClaim)


class InternalNamespaceAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        model = obj or self.model
        return tuple(field.name for field in model._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(FolderLockScope)
class FolderLockScopeAdmin(InternalNamespaceAdmin):
    list_display = ("folder", "owner", "created_at", "updated_at")
    list_select_related = ("folder", "owner")
    exclude = ("password",)


@admin.register(FolderHashWork)
class FolderHashWorkAdmin(InternalNamespaceAdmin):
    list_display = ("folder", "created_at", "updated_at")
    list_select_related = ("folder",)


@admin.register(FolderHeightRepair)
class FolderHeightRepairAdmin(InternalNamespaceAdmin):
    list_display = ("folder", "created_at", "updated_at")
    list_select_related = ("folder",)


@admin.register(NamespaceOperation)
class NamespaceOperationAdmin(InternalNamespaceAdmin):
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
class FragmentAdmin(SimpleHistoryAdmin):
    def delete_model(self, request, obj):
        from website.services.file_service import FileService

        FileService.remove_fragment(PrincipalFactory.from_authenticated_request(request),
                                    str(obj.file_id), str(obj.pk), CredentialSet.empty())

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            self.delete_model(request, obj)

    readonly_fields = ('id', 'channel', 'message_id', 'attachment_id', 'sequence', 'offset', 'readable_size',
                       'file', 'created_at', 'size', 'fragment_url', 'author', 'crc', 'crc_hex', 'jump')
    ordering = ["-created_at"]
    list_display = ["sequence", "file_name", "readable_size", "owner", "folder", "created_at"]
    list_select_related = ["file"]
    search_fields = ["file__name", 'file__owner__username', "message_id"]

    def has_add_permission(self, request):
        return False

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

    @easy.smart(short_description="Size", admin_order_field="size")
    def readable_size(self, obj: Fragment):
        return filesizeformat(obj.size)

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

    @easy.smart(short_description="CRC HEX", allow_tags=True)
    def crc_hex(self, obj: Fragment):
        return f"{obj.crc:08X}"

@admin.register(Folder)
class FolderAdmin(SimpleHistoryAdmin):
    readonly_fields = ('id', 'last_modified_at', 'parent', 'trashed_at', 'physical_file_stats')
    ordering = ["-created_at"]
    list_display = ["name", "owner", "state", "created_at", "is_trashed", "is_locked"]
    search_fields = ["id", "name"]

    def has_add_permission(self, request):
        return False

    @easy.smart(short_description="Is locked", boolean=True)
    def is_locked(self, obj: Folder):
        context = ResourceLoader().resolve_folder(str(obj.id), obj.owner_id)
        return context.is_locked

    @easy.smart(short_description="In trash", boolean=True)
    def is_trashed(self, obj: Folder):
        return obj.trashed_at is not None

    def get_form(self, request, obj=None, **kwargs):
        form = super(SimpleHistoryAdmin, self).get_form(request, obj, **kwargs)
        form.base_fields['name'].widget.attrs['style'] = 'height: 2em;'
        return form

    def delete_queryset(self, request, queryset: QuerySet[Folder]):
        _request_admin_deletion(request, list(queryset))

    def delete_model(self, request, obj: Union[Folder, List[Folder]]):
        if isinstance(obj, Folder):
            _request_admin_deletion(request, [obj])
        else:
            _request_admin_deletion(request, obj)

@admin.register(File)
class FileAdmin(SimpleHistoryAdmin):
    exclude = ('encryption_method', )
    readonly_fields = ('id', 'parent', 'size', 'type', 'extension', 'owner', 'readable_size', 'state', 'is_locked', 'created_at',
                       'last_modified_at', 'formatted_encryption_method', 'formatted_key', 'formatted_iv', 'frontend_id', 'crc', "media_tag", "iv_hex", "key_hex",
                       'fragment_count', 'subs_count', 'thumbnail_cache_id',
                       'has_photo_metadata', 'has_raw_metadata', 'has_video_metadata')
    ordering = ["-created_at"]
    list_display = ['name', 'parent', 'readable_size', 'owner', 'state', 'type', 'created_at',
                    'is_trashed', 'is_locked']
    actions = ['force_delete_model']
    search_fields = ['name', 'id', 'type', 'owner__username']
    filter_horizontal = ('tags',)

    def has_add_permission(self, request):
        return False

    @easy.smart(short_description="Locked", boolean=True)
    def is_locked(self, obj: File):
        context = ResourceLoader().resolve_file(str(obj.id), obj.owner_id)
        return context.is_locked

    @easy.smart(short_description="In trash", boolean=True)
    def is_trashed(self, obj: File):
        return obj.trashed_at is not None

    @easy.smart(short_description="Readable size", admin_order_field="size")
    def readable_size(self, obj: File):
        return filesizeformat(obj.size)

    @easy.smart(short_description="Encryption key (base64)")
    def formatted_key(self, obj: File):
        return obj.get_base64_key()

    @easy.smart(short_description="Encryption IV (base64)")
    def formatted_iv(self, obj: File):
        return obj.get_base64_iv()

    @easy.smart(short_description="Encryption key (HEX)")
    def key_hex(self, obj: File):
        return obj.key.hex()

    @easy.smart(short_description="Encryption IV (HEX)")
    def iv_hex(self, obj: File):
        return obj.iv.hex()

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

    def get_form(self, request, obj=None, **kwargs):
        form = super(SimpleHistoryAdmin, self).get_form(request, obj, **kwargs)
        form.base_fields['name'].widget.attrs['style'] = 'height: 2em;'
        return form

    def delete_queryset(self, request, queryset: QuerySet[File]):
        _request_admin_deletion(request, list(queryset))

    def delete_model(self, request, obj: Union[File, List[File]]):
        if isinstance(obj, File):
            _request_admin_deletion(request, [obj])
        else:
            _request_admin_deletion(request, obj)

    def force_delete_model(self, request, queryset: QuerySet[File]):
        for real_obj in queryset:
            real_obj.delete()

@admin.register(Thumbnail)
class ThumbnailAdmin(SimpleHistoryAdmin):
    search_fields = ['file__name', 'file__id', 'file__owner__username']
    ordering = ['-created_at']
    list_display = ['file_name', 'owner', 'readable_size', 'created_at']
    readonly_fields = ['created_at', 'channel', 'message_id', 'attachment_id', 'size', 'file', 'thumbnail_media', 'encryption_method', 'author']

    def delete_queryset(self, request, queryset: QuerySet[Thumbnail]):
        for thumb in queryset:
            thumbnail_service.thumbnail_service.remove(thumb.file.owner_id, str(thumb.file_id))

    def delete_model(self, request, obj: Union[Thumbnail, List[Thumbnail]]):
        if isinstance(obj, Thumbnail):
            thumbnail_service.thumbnail_service.remove(obj.file.owner_id, str(obj.file_id))
        else:
            for thumb in obj:
                thumbnail_service.thumbnail_service.remove(thumb.file.owner_id, str(thumb.file_id))

    def has_add_permission(self, request):
        return False

    @easy.smart(short_description="File name", admin_order_field="file__name")
    def file_name(self, obj: Thumbnail):
        return obj.file.name

    @easy.smart(short_description="Owner", admin_order_field="file__owner__username")
    def owner(self, obj: Thumbnail):
        return obj.file.owner

    @easy.smart(short_description="Size", admin_order_field="size")
    def readable_size(self, obj: Thumbnail):
        return filesizeformat(obj.size)

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
class ShareableLinkAdmin(admin.ModelAdmin):
    list_display = ('id', 'resource_link', 'get_type', 'owner', 'is_expired', 'expiration_time', 'created_at')
    readonly_fields = ('token', 'password', 'root_folder', 'root_file', 'resource_link', 'root_id', 'get_type', 'owner', 'is_expired', 'expiration_time', 'created_at')

    def has_add_permission(self, request):
        return False

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
class UserZIPAdmin(admin.ModelAdmin):
    list_display = ("owner_id", "created_at")
    ordering = ["-created_at"]

    def has_add_permission(self, request):
        return False

@admin.register(Tag)
class TagAdmin(SimpleHistoryAdmin):
    list_display = ['name', 'owner', 'amount_of_files']
    search_fields = ('name',)
    readonly_fields = ('id', 'file_list', 'created_at')

    def has_add_permission(self, request):
        return False

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
class ChannelAdmin(admin.ModelAdmin):
    search_fields = ('discord_id', 'name')
    list_display = ['name', 'owner', 'discord_id', 'guild_id', 'created_at']

    def has_add_permission(self, request):
        return False

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return 'discord_id', 'guild_id', 'owner'
        return ()

@admin.register(Webhook)
class WebhookAdmin(admin.ModelAdmin):
    search_fields = ('name', 'discord_id')
    list_display = ['name', 'owner', 'created_at']

    def has_add_permission(self, request):
        return False

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return 'url', 'owner', 'discord_id', 'guild_id', 'channel'
        return ()

@admin.register(Bot)
class BotAdmin(admin.ModelAdmin):
    search_fields = ('name', 'discord_id')
    list_display = ['name', 'owner', 'created_at']

    def has_add_permission(self, request):
        return False

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return 'token', 'owner', 'discord_id'
        return ()

@admin.register(Moment)
class MomentAdmin(admin.ModelAdmin):
    search_fields = ('file__name', 'file__owner__username')
    list_display = ['file', 'owner', 'formatted_timestamp', 'readable_size']
    readonly_fields = ('channel', 'message_id', 'attachment_id', 'author', 'file', 'formatted_timestamp', 'readable_size', 'moment_preview', 'encryption_method')
    exclude = ['size', 'timestamp']

    def has_add_permission(self, request):
        return False

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

    @easy.smart(short_description="Size", admin_order_field="size")
    def readable_size(self, obj: Moment):
        return filesizeformat(obj.size)

    @easy.smart(short_description="Encryption method")
    def encryption_method(self, obj: Moment):
        return EncryptionMethod(obj.file.encryption_method).name


class FileMetadataAdmin(admin.ModelAdmin):
    def delete_model(self, request, obj):
        from website.services.file_service import FileService

        FileService.remove_metadata(PrincipalFactory.from_authenticated_request(request),
                                    str(obj.file_id), type(obj), CredentialSet.empty())

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            self.delete_model(request, obj)


@admin.register(VideoMetadata)
class VideoMetadataAdmin(FileMetadataAdmin):
    search_fields = ('file__name', 'file__id')
    readonly_fields = ('file', 'is_progressive', 'is_fragmented', 'has_moov', 'has_IOD', 'brands', 'mime')
    list_display = ['file', 'owner', 'created_at']

    def has_add_permission(self, request):
        return False

    @easy.smart(short_description="Owner")
    def owner(self, obj: RawMetadata):
        return obj.file.owner

@admin.register(RawMetadata)
class RawMetadataAdmin(FileMetadataAdmin):
    search_fields = ('file__name', 'file__id')
    list_display = ['file', 'owner', 'created_at', 'failed_to_process']
    readonly_fields = ('file', 'camera', 'camera_owner', 'iso', 'shutter', 'aperture', 'focal_length')

    def has_add_permission(self, request):
        return False

    @easy.smart(short_description="Owner")
    def owner(self, obj: RawMetadata):
        return obj.file.owner

@admin.register(PhotoMetadata)
class PhotoMetadataAdmin(FileMetadataAdmin):
    search_fields = ('file__name', 'file__id')
    list_display = ['file', 'owner', 'created_at']

    readonly_fields = ('file',)

    def has_add_permission(self, request):
        return False

    @easy.smart(short_description="Owner")
    def owner(self, obj: RawMetadata):
        return obj.file.owner

@admin.register(Subtitle)
class SubtitleAdmin(admin.ModelAdmin):
    ordering = ['-file__internal_created_at']

    search_fields = ('file__name', 'file__id', 'file__owner__username')
    list_display = ['file_name', 'language', 'owner', 'readable_size']
    readonly_fields = ('file', 'formatted_iv', 'formatted_key', 'channel', 'attachment_id', 'message_id', 'author', 'readable_size', 'encryption_method', 'sub_preview')
    exclude = ['size']

    def delete_model(self, request, obj):
        from website.services.file_service import FileService

        FileService.remove_subtitle(PrincipalFactory.from_authenticated_request(request),
                                    str(obj.file_id), str(obj.pk), CredentialSet.empty())

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            self.delete_model(request, obj)

    def has_add_permission(self, request):
        return False

    @easy.with_tags()
    @easy.smart(short_description="Subtitle Preview", allow_tags=True)
    def sub_preview(self, obj: Subtitle):
        subtitle_path = f"/files/{obj.file.id}/subtitles/{obj.id}/stream"
        subtitle_signed = sign_resource(subtitle_path)
        subtitle_url = f"{API_BASE_URL}{subtitle_path}{subtitle_signed}&inline=true"

        return f'<a href="{subtitle_url}" target="_blank">Preview Subtitle</a>'

    @easy.smart(short_description="Size", admin_order_field="size")
    def readable_size(self, obj: Subtitle):
        return filesizeformat(obj.size)

    @easy.smart(short_description="Encryption method")
    def encryption_method(self, obj: Subtitle):
        return EncryptionMethod(obj.file.encryption_method).name

    @easy.smart(short_description="File Name", admin_order_field="file__name")
    def file_name(self, obj: Subtitle):
        return obj.file.name

    @easy.smart(short_description="Owner", admin_order_field="file__owner__username")
    def owner(self, obj: Subtitle):
        return obj.file.owner.username

    @easy.smart(short_description="Encryption key (base64)")
    def formatted_key(self, obj: Subtitle):
        return obj.get_base64_key()

    @easy.smart(short_description="Encryption iv (base64)")
    def formatted_iv(self, obj: Subtitle):
        return obj.get_base64_iv()


@admin.register(ShareAccess)
class ShareAccessAdmin(admin.ModelAdmin):
    ordering = ["-access_time"]
    readonly_fields = ('share', 'id', 'ip', 'user_agent', 'readable_accessed_by', 'access_time')
    list_display = ['share', 'readable_accessed_by', 'ip', 'user_agent']
    exclude = ['accessed_by']

    def has_add_permission(self, request):
        return False

    @easy.smart(short_description="Accessed by")
    def readable_accessed_by(self, obj: ShareAccess):
        return obj.accessed_by.username if obj.accessed_by else "Unknown (Anonymous)"


@admin.register(ShareAccessEvent)
class ShareAccessEventAdmin(admin.ModelAdmin):
    ordering = ["-timestamp"]
    search_fields = ('event_type', 'metadata')
    list_display = ('readable_accessed_by', 'event_type', 'ip', 'user_agent', 'timestamp')

    def has_add_permission(self, request):
        return False

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
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['owner', 'type', 'title', 'message', 'is_read', 'is_deleted']
    actions = ['mark_as_read', 'mark_as_unread']

    def has_add_permission(self, request):
        return False

    def mark_as_read(self, request, queryset: QuerySet[Notification]):
        for notif in queryset:
            notif.mark_as_read()

    def mark_as_unread(self, request, queryset: QuerySet[Notification]):
        for notif in queryset:
            notif.mark_as_unread()


@admin.register(DeletionFileWorkItem)
class DeletionFileWorkItemAdmin(admin.ModelAdmin):
    list_display = ['file', 'scope', 'state', 'attempts', 'claimed_at', 'finished_at']
    list_select_related = ['file', 'scope']
    readonly_fields = [field.name for field in DeletionFileWorkItem._meta.fields]

    def has_add_permission(self, request):
        return False

@admin.register(DeletionFolderWorkItem)
class DeletionFolderWorkItemAdmin(admin.ModelAdmin):
    list_display = ['folder', 'scope', 'state', 'attempts', 'expansion_complete', 'claimed_at', 'finished_at']
    list_select_related = ['folder', 'scope']
    readonly_fields = [field.name for field in DeletionFolderWorkItem._meta.fields]

    def has_add_permission(self, request):
        return False

@admin.register(DeletionScope)
class DeletionScopeAdmin(admin.ModelAdmin):
    ordering = ['-created_at']
    list_display = ['id', 'owner', 'root_folder', 'root_file', 'state', 'created_at', 'completed_at']
    list_filter = ['state']
    list_select_related = ['owner', 'root_folder', 'root_file']
    readonly_fields = [field.name for field in DeletionScope._meta.fields]

    def has_add_permission(self, request):
        return False


@admin.register(PerDeviceToken)
class PerDeviceTokenAdmin(admin.ModelAdmin):
    actions = ['revoke']
    list_display = ['user', 'device_type', 'last_used_at', 'country', 'city']
    readonly_fields = ('user', 'token_hash', 'last_used_at', 'ip_address', 'user_agent', 'country', 'city', 'device_type')

    def has_add_permission(self, request):
        return False

    def revoke(self, request, queryset):
        for token in queryset:
            auth_service.logout_device(request, user=token.user, device_id=token.device_id)
