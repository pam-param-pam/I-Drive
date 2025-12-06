import datetime
from typing import Union, List

from django.contrib import admin
from django.db.models import QuerySet
from django.forms import ModelForm
from django.template.defaultfilters import filesizeformat
from django.urls import reverse
from django.utils.html import format_html
from simple_history.admin import SimpleHistoryAdmin

from .constants import API_BASE_URL, cache, EncryptionMethod
from .core.crypto.signer import sign_resource_id_with_expiry
from .core.dataModels.http import RequestContext
from .discord.Discord import discord
from .models import Fragment, Folder, File, UserSettings, UserPerms, ShareableLink, Preview, Thumbnail, UserZIP, VideoPosition, Tag, Webhook, Bot, DiscordSettings, Moment, \
    VideoMetadata, VideoTrack, AudioTrack, SubtitleTrack, Subtitle, Channel, ShareAccess, PerDeviceToken, ShareAccessEvent
from .tasks.deleteTasks import smart_delete_task

admin.site.register(UserSettings, SimpleHistoryAdmin)
admin.site.register(UserPerms, SimpleHistoryAdmin)
admin.site.register(DiscordSettings, SimpleHistoryAdmin)
admin.site.register(VideoPosition)
admin.site.register(VideoTrack)
admin.site.register(AudioTrack)
admin.site.register(SubtitleTrack)
admin.site.register(PerDeviceToken)
admin.site.register(ShareAccessEvent)


@admin.register(Fragment)
class FragmentAdmin(SimpleHistoryAdmin):
    readonly_fields = ('id', 'channel_id', 'message_id', 'attachment_id', 'sequence', 'offset', 'readable_size', 'file', 'created_at', 'size', 'fragment_url')
    ordering = ["-created_at"]
    list_display = ["sequence", "file_name", "readable_size", "owner", "folder", "created_at"]
    list_select_related = ["file"]
    search_fields = ["file__name", 'file__owner__username']

    def owner(self, obj: Fragment):
        return obj.file.owner

    def folder(self, obj: Fragment):
        return f"{obj.file.parent.name}({obj.file.parent.id})"

    def readable_size(self, obj: Fragment):
        return filesizeformat(obj.size)

    def file_name(self, obj: Fragment):
        file_name = obj.file.name
        if len(file_name) < 100:
            return file_name
        return "*File name to long to display*"

    def fragment_url(self, obj: Fragment):
        url = discord.get_attachment_url(obj.file.owner, obj)
        return format_html(f'<a href="{url}" target="_blank">{url}</a><br>')

    owner.admin_order_field = "file__owner__username"
    folder.admin_order_field = "file__parent__name"
    readable_size.admin_order_field = "size"
    file_name.admin_order_field = "file__name"


@admin.register(Folder)
class FolderAdmin(SimpleHistoryAdmin):
    readonly_fields = ('id', 'last_modified_at')
    ordering = ["-created_at"]
    list_display = ["name", "owner", "ready", "created_at", "inTrash", "is_locked"]
    actions = ['move_to_trash', 'restore_from_trash', 'force_delete_model', 'unlock', 'force_ready']
    search_fields = ["id", "name"]

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
        if isinstance(obj, File):
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

    def is_locked(self, obj: File):
        return obj._is_locked()

    is_locked.admin_order_field = 'password'
    is_locked.boolean = True


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

    def get_form(self, request, obj=None, **kwargs):
        form = super(SimpleHistoryAdmin, self).get_form(request, obj, **kwargs)
        form.base_fields['name'].widget.attrs['style'] = 'height: 2em;'
        return form

    def is_locked(self, obj: File):
        return obj.parent.is_locked

    def media_tag(self, obj: File):
        signed_file_id = sign_resource_id_with_expiry(obj.id)

        if obj.type == "Raw image":
            url = f"{API_BASE_URL}/files/{signed_file_id}/preview/stream"
            return format_html('<img src="{}" style="width: 350px; height: auto;" />', url)

        elif obj.type == "Image":
            url = f"{API_BASE_URL}/files/{signed_file_id}/stream?inline=True"
            return format_html('<img src="{}" style="width: 350px; height: auto;" />', url)

        elif obj.type == "Video":
            url = f"{API_BASE_URL}/files/{signed_file_id}/stream?inline=True"
            poster_url = f"{API_BASE_URL}/files/thumbnail/{signed_file_id}"

            return format_html(
                '<video controls style="width: 350px; height: auto;" poster="{}">'
                '<source src="{}" type="video/mp4">'
                '</video>',
                poster_url,
                url
            )
        elif obj.type == "Audio":
            url = f"{API_BASE_URL}/files/{signed_file_id}/stream?inline=True"
            poster_url = f"{API_BASE_URL}/files/{signed_file_id}/thumbnail/stream"

            return format_html(
                '<div style="display: flex; align-items: center;">'
                '<img src="{}" alt="Audio Thumbnail" style="width: 100px; height: 100px; margin-right: 10px;">'
                '<audio controls ">'
                '<source src="{}" type="audio/mpeg">'
                'Your browser does not support the audio element.'
                '</audio>'
                '</div>',
                poster_url,
                url
            )
        else:
            url = f"{API_BASE_URL}/files/{signed_file_id}/stream?inline=True"
            return format_html(f'<a href="{url}" target="_blank">{url}</a>')

    def formatted_key(self, obj: File):
        return obj.get_base64_key()

    def formatted_iv(self, obj: File):
        return obj.get_base64_iv()

    def formatted_encryption_method(self, obj: File):
        return obj.get_encryption_method().name

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

    def readable_size(self, obj: File):
        return filesizeformat(obj.size)

    def is_locked(self, obj: File):
        return obj._is_locked()

    is_locked.admin_order_field = 'parent__password'
    is_locked.boolean = True
    formatted_key.short_description = "Encryption key (base64)"
    formatted_iv.short_description = "Encryption iv (base64)"
    media_tag.short_description = 'PREVIEW MEDIA FILE'
    formatted_encryption_method.short_description = "Encryption method"
    readable_size.admin_order_field = 'size'

@admin.register(Preview)
class PreviewAdmin(SimpleHistoryAdmin):
    ordering = ['-created_at']
    search_fields = ['file__name', 'file__id', 'file__owner__username']
    list_display = ['file_name', 'owner', 'readable_size', 'readable_encrypted_size', 'created_at']
    readonly_fields = ['created_at', 'channel_id', 'message_id', 'attachment_id', 'size', 'file', 'encryption_method']

    def file_name(self, obj: Preview):
        return obj.file.name

    def owner(self, obj: Preview):
        return obj.file.owner

    def readable_size(self, obj: Preview):
        return filesizeformat(obj.size)

    def readable_encrypted_size(self, obj: Preview):
        return filesizeformat(obj.encrypted_size)

    def encryption_method(self, obj: Subtitle):
        return EncryptionMethod(obj.file.encryption_method).name

@admin.register(Thumbnail)
class ThumbnailAdmin(SimpleHistoryAdmin):
    search_fields = ['file__name', 'file__id', 'file__owner__username']
    ordering = ['-created_at']
    list_display = ['file_name', 'owner', 'readable_size', 'created_at']
    readonly_fields = ['created_at', 'channel_id', 'message_id', 'attachment_id', 'size', 'file', 'thumbnail_media', 'encryption_method', 'object_id', 'content_type']

    def file_name(self, obj: Thumbnail):
        return obj.file.name

    def owner(self, obj: Thumbnail):
        return obj.file.owner

    def readable_size(self, obj: Thumbnail):
        return filesizeformat(obj.size)

    def thumbnail_media(self, obj: Thumbnail):
        signed_file_id = sign_resource_id_with_expiry(obj.file.id)
        url = f"{API_BASE_URL}/files/{signed_file_id}/thumbnail/stream"
        return format_html('<img src="{}" style="width: 350px; height: auto;" />', url)

    def encryption_method(self, obj: Subtitle):
        return EncryptionMethod(obj.file.encryption_method).name

    thumbnail_media.short_description = 'PREVIEW THUMBNAIL'


@admin.register(ShareableLink)
class ShareableLinkAdmin(admin.ModelAdmin):
    list_display = ('token', 'resource_link', 'expiration_time', 'created_at', 'owner', 'content_type', 'is_expired')
    readonly_fields = ('resource_link', 'object_id', 'content_type', 'owner', 'is_expired')

    def resource_name(self, obj: ShareableLink):
        if obj.resource:
            return str(obj.resource.name)
        else:
            return "<RESOURCE DELETED>"

    resource_name.short_description = 'Name'

    def resource_link(self, obj: ShareableLink):
        url = reverse('admin:%s_%s_change' % (
            obj.content_type.app_label,
            obj.content_type.model
        ), args=[obj.object_id])
        return format_html('<a href="{}">' + self.resource_name(obj) + '</a>', url)

    def is_expired(self, obj: ShareableLink):
        return obj.is_expired()

    resource_link.short_description = 'Resource'
    is_expired.admin_order_field = 'expiration_time'
    is_expired.boolean = True

@admin.register(UserZIP)
class UserZIPAdmin(admin.ModelAdmin):
    list_display = ('owner_name', 'created_at')
    filter_horizontal = ('files', 'folders')
    ordering = ["-created_at"]

    def owner_name(self, obj: UserZIP):
        return obj.owner.username


@admin.register(Tag)
class TagAdmin(SimpleHistoryAdmin):
    list_display = ['name', 'owner', 'amount_of_files']
    search_fields = ('name',)

    readonly_fields = ('id', 'file_list', 'created_at')

    def all_files(self, obj: Tag):
        return obj.files.all()

    def amount_of_files(self, obj: Tag):
        return len(self.all_files(obj))

    def file_list(self, obj: Tag):
        files = self.all_files(obj)
        if files:
            return format_html(
                "<br>".join([format_html('<a href="{}">{}</a>', reverse('admin:%s_file_change' % file._meta.app_label, args=[file.id]), file.name) for file in files])
            )
        return "No files"

    file_list.short_description = "Files"

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
    readonly_fields = ('channel_id', 'message_id', 'attachment_id', 'content_type', 'object_id', 'file', 'formatted_timestamp', 'readable_size', 'preview', 'encryption_method')
    exclude = ['size', 'timestamp']

    def preview(self, obj: Moment):
        signed_file_id = sign_resource_id_with_expiry(obj.file.id)
        url = f"{API_BASE_URL}/files/{signed_file_id}/moment/{obj.timestamp}/stream"
        return format_html('<img src="{}" style="width: 350px; height: auto;" />', url)

    def owner(self, obj: Moment):
        return obj.file.owner

    def formatted_timestamp(self, obj: Moment):
        a = datetime.timedelta(seconds=obj.timestamp)
        return str(a)

    def readable_size(self, obj: Moment):
        return filesizeformat(obj.size)

    def encryption_method(self, obj: Subtitle):
        return EncryptionMethod(obj.file.encryption_method).name

    readable_size.short_description = 'Size'
    readable_size.admin_order_field = 'size'

    formatted_timestamp.short_description = 'Timestamp'
    formatted_timestamp.admin_order_field = 'timestamp'


@admin.register(VideoMetadata)
class VideoMetadataAdmin(admin.ModelAdmin):
    search_fields = ('file__name', 'file__id')
    readonly_fields = ('file', 'is_progressive', 'is_fragmented', 'has_moov', 'has_IOD', 'brands', 'mime')

@admin.register(Subtitle)
class SubtitleAdmin(admin.ModelAdmin):
    search_fields = ('file__name', 'file__id', 'file__owner__username')
    list_display = ['file_name', 'language', 'owner', 'readable_size']
    readonly_fields = ('file', 'formatted_iv', 'formatted_key', 'channel_id', 'attachment_id', 'message_id', 'content_type', 'object_id', 'readable_size', 'encryption_method', 'preview')
    exclude = ['size']

    def preview(self, obj):
        signed_file_id = sign_resource_id_with_expiry(obj.file.id)
        url = f"{API_BASE_URL}/files/{signed_file_id}/subtitles/{obj.id}/stream"
        return format_html('<a href="{}" target="_blank">Preview Subtitle</a>', url)

    preview.short_description = "Subtitle Preview"

    def readable_size(self, obj: Subtitle):
        return filesizeformat(obj.size)

    def encryption_method(self, obj: Subtitle):
        return EncryptionMethod(obj.file.encryption_method).name

    def file_name(self, obj):
        return obj.file.name

    def owner(self, obj):
        return obj.file.owner.username

    def formatted_key(self, obj: File):
        return obj.get_base64_key()

    def formatted_iv(self, obj: File):
        return obj.get_base64_iv()

    file_name.admin_order_field = 'file__name'
    file_name.short_description = 'File Name'

    owner.admin_order_field = 'file__owner'
    owner.short_description = 'Owner'

    readable_size.short_description = 'Size'
    readable_size.admin_order_field = 'size'

@admin.register(ShareAccess)
class ShareAccessAdmin(admin.ModelAdmin):
    readonly_fields = ('share', 'ip', 'user_agent', 'readable_accessed_by', 'access_time')
    exclude = ['accessed_by']

    def readable_accessed_by(self, obj: ShareAccess):
        if obj.accessed_by:
            return obj.accessed_by.username
        else:
            return "Unknown (Anonymous)"

    readable_accessed_by.short_description = "Accessed by"
