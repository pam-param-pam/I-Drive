import datetime
from typing import Union, List

import easy
from django.contrib import admin
from django.db.models import QuerySet
from django.forms import ModelForm
from django.template.defaultfilters import filesizeformat
from django.urls import reverse
from simple_history.admin import SimpleHistoryAdmin

from .constants import API_BASE_URL, cache, EncryptionMethod
from .core.crypto.signer import sign_resource_id_with_expiry
from .core.dataModels.http import RequestContext
from .discord.Discord import discord
from .models import Fragment, Folder, File, UserSettings, UserPerms, ShareableLink, Thumbnail, UserZIP, VideoPosition, Tag, Webhook, Bot, DiscordSettings, Moment, \
    VideoMetadata, VideoTrack, AudioTrack, SubtitleTrack, Subtitle, Channel, ShareAccess, PerDeviceToken, ShareAccessEvent, AttachmentLinker, FragmentLink
from .models.file_related_models import RawMetadata, ThumbnailLink

from .tasks.deleteTasks import smart_delete_task

admin.site.register(PerDeviceToken)

admin.site.register(UserSettings, SimpleHistoryAdmin)
admin.site.register(UserPerms, SimpleHistoryAdmin)
admin.site.register(DiscordSettings, SimpleHistoryAdmin)

admin.site.register(VideoTrack)
admin.site.register(AudioTrack)
admin.site.register(SubtitleTrack)

admin.site.register(VideoPosition)

admin.site.register(ShareAccessEvent)

admin.site.register(AttachmentLinker)
admin.site.register(FragmentLink)
admin.site.register(ThumbnailLink)


@admin.register(Fragment)
class FragmentAdmin(SimpleHistoryAdmin):
    readonly_fields = ('id', 'channel_id', 'message_id', 'attachment_id', 'sequence', 'offset', 'readable_size',
                       'file', 'created_at', 'size', 'fragment_url', 'object_id', 'content_type', 'crc')
    ordering = ["-created_at"]
    list_display = ["sequence", "file_name", "readable_size", "owner", "folder", "created_at"]
    list_select_related = ["file"]
    search_fields = ["file__name", 'file__owner__username']

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
        url = discord.get_attachment_url(obj.file.owner, obj)
        return f'<a href="{url}" target="_blank">{url}</a><br>'


@admin.register(Folder)
class FolderAdmin(SimpleHistoryAdmin):
    readonly_fields = ('id', 'last_modified_at')
    ordering = ["-created_at"]
    list_display = ["name", "owner", "ready", "created_at", "inTrash", "is_locked"]
    actions = ['move_to_trash', 'restore_from_trash', 'force_delete_model', 'unlock', 'force_ready']
    search_fields = ["id", "name"]

    @easy.smart(short_description="Is locked", admin_order_field="password")
    def is_locked(self, obj: File):
        return obj._is_locked()

    def get_form(self, request, obj=None, **kwargs):
        form = super(SimpleHistoryAdmin, self).get_form(request, obj, **kwargs)
        form.base_fields['name'].widget.attrs['style'] = 'height: 2em;'
        return form

    def force_ready(self, request, queryset: QuerySet[Folder]):
        for real_obj in queryset:
            real_obj.ready = True
            real_obj.save()

    def delete_queryset(self, request, queryset: QuerySet[Folder]):
        ids = []
        for real_obj in queryset:
            ids.append(real_obj.id)

        smart_delete_task.delay(RequestContext.from_user(request.user.id), ids)

    def delete_model(self, request, obj: Union[Folder, List[Folder]]):
        if isinstance(obj, Folder):
            smart_delete_task.delay(RequestContext.from_user(request.user.id), [obj.id])

            obj.force_delete()
        else:
            ids = []

            for real_obj in obj:
                ids.append(real_obj.id)
            smart_delete_task.delay(RequestContext.from_user(request.user.id), ids)

    def force_delete_model(self, request, queryset: QuerySet[Folder]):
        for real_obj in queryset:
            real_obj.force_delete()

    def move_to_trash(self, request, queryset: QuerySet[Folder]):
        for folder in queryset:
            folder.moveToTrash()

    def restore_from_trash(self, request, queryset: QuerySet[Folder]):
        for folder in queryset:
            folder.restoreFromTrash()

    def unlock(self, request, queryset: QuerySet[Folder]):
        for folder in queryset:
            folder.removeLock()

    def save_model(self, request, obj: Folder, form: ModelForm, change: bool):
        cache.delete(obj.id)
        if obj.parent:
            cache.delete(obj.parent.id)

        super().save_model(request, obj, form, change)


@admin.register(File)
class FileAdmin(SimpleHistoryAdmin):
    exclude = ('encryption_method', )
    readonly_fields = ('id', 'size', 'readable_size', 'duration', 'inTrashSince', 'ready', 'is_locked', 'created_at', 'last_modified_at', 'formatted_encryption_method', 'formatted_key', 'formatted_iv', 'frontend_id', 'crc', "media_tag")
    ordering = ["-created_at"]
    list_display = ['name', 'parent', 'readable_size', 'owner', 'ready', 'type', 'created_at',
                    'inTrash', 'is_locked']
    actions = ['move_to_trash', 'restore_from_trash', 'force_ready', 'force_delete_model']
    search_fields = ['name', 'id', 'type', 'owner__username']
    filter_horizontal = ('tags',)

    @easy.smart(short_description="Locked", admin_order_field="parent__password", bool=True)
    def is_locked(self, obj: File):
        return obj._is_locked()

    @easy.smart(short_description="Readable size", admin_order_field="size")
    def readable_size(self, obj: File):
        return filesizeformat(obj.size)

    @easy.smart(short_description="Encryption key (base64)")
    def formatted_key(self, obj: File):
        return obj.get_base64_key()

    @easy.smart(short_description="Encryption IV (base64)")
    def formatted_iv(self, obj: File):
        return obj.get_base64_iv()

    @easy.smart(short_description="Encryption method")
    def formatted_encryption_method(self, obj: File):
        return obj.get_encryption_method().name

    @easy.with_tags()
    @easy.smart(short_description="Preview")
    def media_tag(self, obj: File):
        signed_file_id = sign_resource_id_with_expiry(obj.id)

        # Video preview
        if obj.type == "Video":
            url = f"{API_BASE_URL}/files/{signed_file_id}/stream?inline=True"
            poster_url = f"{API_BASE_URL}/files/thumbnail/{signed_file_id}"
            return (
                f'<video controls style="width:350px; height:auto;" poster="{poster_url}">'
                f'<source src="{url}" type="video/mp4"></video>'
            )

        # Audio preview
        if obj.type == "Audio":
            url = f"{API_BASE_URL}/files/{signed_file_id}/stream?inline=True"
            poster_url = f"{API_BASE_URL}/files/{signed_file_id}/thumbnail/stream"
            return (
                '<div style="display:flex; align-items:center;">'
                f'<img src="{poster_url}" style="width:100px; height:100px; margin-right:10px;">'
                f'<audio controls><source src="{url}" type="audio/mpeg"></audio>'
                '</div>'
            )

        # Otherwise: default link
        url = f"{API_BASE_URL}/files/{signed_file_id}/stream?inline=True"
        return f'<a href="{url}" target="_blank">{url}</a>'

    def get_form(self, request, obj=None, **kwargs):
        form = super(SimpleHistoryAdmin, self).get_form(request, obj, **kwargs)
        form.base_fields['name'].widget.attrs['style'] = 'height: 2em;'
        return form

    def delete_queryset(self, request, queryset: QuerySet[File]):
        ids = []
        for real_obj in queryset:
            ids.append(real_obj.id)

        smart_delete_task.delay(RequestContext.from_user(request.user.id), ids)

    def delete_model(self, request, obj: Union[File, List[File]]):
        if isinstance(obj, File):
            smart_delete_task.delay(RequestContext.from_user(request.user.id), [obj.id])

            obj.force_delete()
        else:
            ids = []

            for real_obj in obj:
                ids.append(real_obj.id)

            smart_delete_task.delay(RequestContext.from_user(request.user.id), ids)

    def force_ready(self, request, queryset: QuerySet[File]):
        for real_obj in queryset:
            real_obj.ready = True
            real_obj.save()

    def force_delete_model(self, request, queryset: QuerySet[File]):
        for real_obj in queryset:
            real_obj.force_delete()

    def move_to_trash(self, request, queryset: QuerySet[File]):
        for file in queryset:
            file.moveToTrash()

    def restore_from_trash(self, request, queryset: QuerySet[File]):
        for file in queryset:
            file.restoreFromTrash()


@admin.register(Thumbnail)
class ThumbnailAdmin(SimpleHistoryAdmin):
    search_fields = ['file__name', 'file__id', 'file__owner__username']
    ordering = ['-created_at']
    list_display = ['file_name', 'owner', 'readable_size', 'created_at']
    readonly_fields = ['created_at', 'channel_id', 'message_id', 'attachment_id', 'size', 'file', 'thumbnail_media', 'encryption_method', 'object_id', 'content_type']

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
        signed_file_id = sign_resource_id_with_expiry(obj.file.id)
        url = f"{API_BASE_URL}/files/{signed_file_id}/thumbnail/stream"
        return f'<img src="{url}" style="width:350px; height:auto;">'

    @easy.smart(short_description="Encryption method")
    def encryption_method(self, obj: Thumbnail):
        return EncryptionMethod(obj.file.encryption_method).name


@admin.register(ShareableLink)
class ShareableLinkAdmin(admin.ModelAdmin):
    list_display = ('token', 'resource_link', 'content_type', 'owner', 'is_expired', 'expiration_time', 'created_at')
    readonly_fields = ('resource_link', 'object_id', 'content_type', 'owner', 'is_expired')

    @easy.with_tags()
    @easy.smart(short_description="Resource")
    def resource_link(self, obj: ShareableLink):

        if not obj.resource:
            return "<RESOURCE DELETED>"

        url = reverse(
            f"admin:{obj.content_type.app_label}_{obj.content_type.model}_change",
            args=[obj.object_id]
        )
        # admin-easy will mark safe due to allow_tags default in smart
        return f'<a href="{url}">{obj.resource.name}</a>'

    @easy.smart(short_description="Expired?", admin_order_field="expiration_time", bool=True)
    def is_expired(self, obj: ShareableLink):
        return obj.is_expired()

@admin.register(UserZIP)
class UserZIPAdmin(admin.ModelAdmin):
    list_display = ("owner_name", "created_at")
    filter_horizontal = ("files", "folders")
    ordering = ["-created_at"]

    @easy.smart(short_description="Owner", admin_order_field="owner__username")
    def owner_name(self, obj: UserZIP):
        return obj.owner.username


@admin.register(Tag)
class TagAdmin(SimpleHistoryAdmin):
    list_display = ['name', 'owner', 'amount_of_files']
    search_fields = ('name',)
    readonly_fields = ('id', 'file_list', 'created_at')

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
    list_display = ['name', 'discord_id', 'guild_id', 'created_at']

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return 'discord_id', 'guild_id', 'owner'
        return ()

@admin.register(Webhook)
class WebhookAdmin(admin.ModelAdmin):
    search_fields = ('name', 'discord_id')
    list_display = ['name', 'owner', 'created_at']

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return 'url', 'owner', 'discord_id', 'guild_id', 'channel'
        return ()

@admin.register(Bot)
class BotAdmin(admin.ModelAdmin):
    search_fields = ('name', 'discord_id')
    list_display = ['name', 'owner', 'created_at']

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return 'token', 'owner', 'discord_id'
        return ()

@admin.register(Moment)
class MomentAdmin(admin.ModelAdmin):
    search_fields = ('file_name', 'file__owner__username')
    list_display = ['file', 'owner', 'formatted_timestamp', 'readable_size']
    readonly_fields = ('channel_id', 'message_id', 'attachment_id', 'content_type', 'object_id', 'file', 'formatted_timestamp', 'readable_size', 'moment_preview', 'encryption_method')
    exclude = ['size', 'timestamp']

    @easy.with_tags()
    @easy.smart(short_description="Preview", allow_tags=True)
    def moment_preview(self, obj: Moment):
        signed_file_id = sign_resource_id_with_expiry(obj.file.id)
        url = f"{API_BASE_URL}/files/{signed_file_id}/moments/{obj.id}/stream"
        return f'<img src="{url}" style="width:350px; height:auto;">'

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


@admin.register(VideoMetadata)
class VideoMetadataAdmin(admin.ModelAdmin):
    search_fields = ('file__name', 'file__id')
    readonly_fields = ('file', 'is_progressive', 'is_fragmented', 'has_moov', 'has_IOD', 'brands', 'mime')


@admin.register(RawMetadata)
class RawMetadataAdmin(admin.ModelAdmin):
    search_fields = ('file__name', 'file__id')
    readonly_fields = ('file', 'camera', 'camera_owner', 'iso', 'shutter', 'aperture', 'focal_length')

@admin.register(Subtitle)
class SubtitleAdmin(admin.ModelAdmin):
    search_fields = ('file__name', 'file__id', 'file__owner__username')
    list_display = ['file_name', 'language', 'owner', 'readable_size']
    readonly_fields = ('file', 'formatted_iv', 'formatted_key', 'channel_id', 'attachment_id', 'message_id', 'content_type', 'object_id', 'readable_size', 'encryption_method', 'sub_preview')
    exclude = ['size']

    @easy.with_tags()
    @easy.smart(short_description="Subtitle Preview", allow_tags=True)
    def sub_preview(self, obj: Subtitle):
        signed_file_id = sign_resource_id_with_expiry(obj.file.id)
        url = f"{API_BASE_URL}/files/{signed_file_id}/subtitles/{obj.id}/stream?inline=True"
        return f'<a href="{url}" target="_blank">Preview Subtitle</a>'

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
    readonly_fields = ('share', 'ip', 'user_agent', 'readable_accessed_by', 'access_time')
    exclude = ['accessed_by']

    @easy.smart(short_description="Accessed by")
    def readable_accessed_by(self, obj: ShareAccess):
        return obj.accessed_by.username if obj.accessed_by else "Unknown (Anonymous)"
