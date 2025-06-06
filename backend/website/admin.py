import datetime
from typing import Union, List

from django.contrib import admin
from django.db.models import QuerySet
from django.forms import ModelForm
from django.template.defaultfilters import filesizeformat
from django.urls import reverse
from django.utils.html import format_html
from simple_history.admin import SimpleHistoryAdmin

from .models import Fragment, Folder, File, UserSettings, UserPerms, ShareableLink, Preview, Thumbnail, UserZIP, VideoPosition, AuditEntry, Tag, Webhook, Bot, DiscordSettings, Moment, \
    VideoMetadata, VideoTrack, AudioTrack, SubtitleTrack, Subtitle
from .tasks import smart_delete
from .utilities.Discord import discord
from .utilities.constants import cache, RAW_IMAGE_EXTENSIONS, API_BASE_URL, EncryptionMethod
from .utilities.other import sign_resource_id_with_expiry

admin.site.register(UserSettings, SimpleHistoryAdmin)
admin.site.register(UserPerms, SimpleHistoryAdmin)
admin.site.register(DiscordSettings, SimpleHistoryAdmin)
admin.site.register(VideoPosition)
admin.site.register(VideoTrack)
admin.site.register(AudioTrack)
admin.site.register(SubtitleTrack)


@admin.register(Fragment)
class FragmentAdmin(SimpleHistoryAdmin):
    readonly_fields = ('id', 'message_id', 'attachment_id', 'sequence', 'offset', 'readable_size', 'file', 'created_at', 'size', 'fragment_url')
    ordering = ["-created_at"]
    list_display = ["sequence", "file_name", "readable_size", "owner", "folder", "created_at"]
    list_select_related = ["file"]
    search_fields = ["file__name"]

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
class FolderAdmin(admin.ModelAdmin):
    readonly_fields = ('id',)
    ordering = ["-created_at"]
    list_display = ["name", "owner", "ready", "created_at", "inTrash", "is_locked"]
    actions = ['move_to_trash', 'restore_from_trash', 'force_delete_model', 'unlock']
    search_fields = ["id", "name"]

    def delete_queryset(self, request, queryset: QuerySet[Folder]):
        ids = []
        for real_obj in queryset:
            ids.append(real_obj.id)

        smart_delete.delay(request.user.id, request.request_id, ids)

    def delete_model(self, request, obj: Union[Folder, List[Folder]]):
        if isinstance(obj, File):
            smart_delete.delay(request.user.id, request.request_id, [obj.id])

            obj.force_delete()
        else:
            ids = []

            for real_obj in obj:
                ids.append(real_obj.id)
            smart_delete.delay(request.user.id, request.request_id, ids)

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
    readonly_fields = ('id', 'size', 'readable_size', 'duration', 'inTrashSince', 'ready', 'created_at', 'formatted_encryption_method', 'formatted_key', 'formatted_iv', 'frontend_id', 'crc', "media_tag")
    ordering = ["-created_at"]
    list_display = ['name', 'parent', 'readable_size', 'owner', 'ready', 'created_at',
                    'inTrash', 'is_locked']
    actions = ['move_to_trash', 'restore_from_trash', 'force_ready', 'force_delete_model']
    search_fields = ['name', 'id']
    filter_horizontal = ('tags',)

    def get_form(self, request, obj=None, **kwargs):
        form = super(SimpleHistoryAdmin, self).get_form(request, obj, **kwargs)
        form.base_fields['name'].widget.attrs['style'] = 'height: 2em;'
        return form

    def media_tag(self, obj: File):
        signed_file_id = sign_resource_id_with_expiry(obj.id)

        if obj.extension in RAW_IMAGE_EXTENSIONS:
            url = f"{API_BASE_URL}/api/file/preview/{signed_file_id}"
            return format_html('<img src="{}" style="width: 350px; height: auto;" />', url)

        elif obj.type == "image":
            url = f"{API_BASE_URL}/stream/{signed_file_id}?inline=True"
            return format_html('<img src="{}" style="width: 350px; height: auto;" />', url)

        elif obj.type == "video":
            url = f"{API_BASE_URL}/stream/{signed_file_id}?inline=True"
            poster_url = f"{API_BASE_URL}/file/thumbnail/{signed_file_id}"

            return format_html(
                '<video controls style="width: 350px; height: auto;" poster="{}">'
                '<source src="{}" type="video/mp4">'
                '</video>',
                poster_url,
                url
            )
        elif obj.type == "audio":
            url = f"{API_BASE_URL}/stream/{signed_file_id}?inline=True"
            # poster_url = f"{API_BASE_URL}/file/thumbnail/{signed_file_id}"

            return format_html(
                '<div style="display: flex; align-items: center;">'
                # '<img src="{}" alt="Audio Thumbnail" style="width: 100px; height: 100px; margin-right: 10px;">'
                '<audio controls ">'
                '<source src="{}" type="audio/mpeg">'
                'Your browser does not support the audio element.'
                '</audio>'
                '</div>',
                # poster_url,
                url
            )
        else:
            url = f"{API_BASE_URL}/stream/{signed_file_id}?inline=True"
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

        smart_delete.delay(request.user.id, request.request_id, ids)

    def delete_model(self, request, obj: Union[File, List[File]]):
        if isinstance(obj, File):
            smart_delete.delay(request.user.id, request.request_id, [obj.id])

            obj.force_delete()
        else:
            ids = []

            for real_obj in obj:
                ids.append(real_obj.id)

            smart_delete.delay(request.user.id, request.request_id, ids)

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

    is_locked.admin_order_field = 'password'
    is_locked.boolean = True
    formatted_key.short_description = "Encryption key (base64)"
    formatted_iv.short_description = "Encryption iv (base64)"
    media_tag.short_description = 'PREVIEW MEDIA FILE'
    formatted_encryption_method.short_description = "Encryption method"
    readable_size.admin_order_field = 'size'

@admin.register(Preview)
class PreviewAdmin(SimpleHistoryAdmin):
    ordering = ['-created_at']
    list_display = ['file_name', 'owner', 'readable_size', 'readable_encrypted_size', 'created_at']

    readonly_fields = ['created_at', 'message_id', 'attachment_id', 'size', 'file', 'encryption_method']

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
    ordering = ['-created_at']
    list_display = ['file_name', 'owner', 'readable_size', 'created_at']
    readonly_fields = ['created_at', 'message_id', 'attachment_id', 'size', 'file', 'thumbnail_media', 'encryption_method']

    def file_name(self, obj: Thumbnail):
        return obj.file.name

    def owner(self, obj: Thumbnail):
        return obj.file.owner

    def readable_size(self, obj: Thumbnail):
        return filesizeformat(obj.size)

    def thumbnail_media(self, obj: Thumbnail):
        signed_file_id = sign_resource_id_with_expiry(obj.file.id)
        url = f"{API_BASE_URL}/file/thumbnail/{signed_file_id}"
        return format_html('<img src="{}" style="width: 350px; height: auto;" />', url)

    def encryption_method(self, obj: Subtitle):
        return EncryptionMethod(obj.file.encryption_method).name

    thumbnail_media.short_description = 'PREVIEW THUMBNAIL'


@admin.register(ShareableLink)
class ShareableLinkAdmin(admin.ModelAdmin):
    readonly_fields = ('token',)

    list_display = ('token', 'expiration_time', 'owner', 'content_type', 'object_id', 'is_expired')

    def readable_size(self, obj: ShareableLink):
        return filesizeformat(obj.is_expired)


@admin.register(UserZIP)
class UserZIPAdmin(admin.ModelAdmin):
    list_display = ('owner_name', 'created_at')
    filter_horizontal = ('files', 'folders')
    ordering = ["-created_at"]

    def owner_name(self, obj: UserZIP):
        return obj.owner.username


@admin.register(AuditEntry)
class AuditEntryAdmin(admin.ModelAdmin):
    list_display = ['action', 'user', 'ip', 'user_agent', 'datetime']


@admin.register(Tag)
class TagAdmin(SimpleHistoryAdmin):
    list_display = ['name', 'owner', 'amount_of_files']
    search_fields = ('name',)

    readonly_fields = ('file_list', 'created_at')

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


@admin.register(Webhook)
class WebhookAdmin(admin.ModelAdmin):
    search_fields = ('name', 'discord_id')
    list_display = ['name', 'owner', 'created_at']
    readonly_fields = ('url', 'owner', 'discord_id', 'guild_id', 'channel_id')


@admin.register(Bot)
class BotAdmin(admin.ModelAdmin):
    search_fields = ('name', 'discord_id')
    list_display = ['name', 'owner', 'created_at']
    readonly_fields = ('token', 'owner', 'discord_id', 'disabled', 'reason')


@admin.register(Moment)
class MomentAdmin(admin.ModelAdmin):
    search_fields = ('file_name',)
    list_display = ['file', 'owner', 'formatted_timestamp', 'readable_size']
    readonly_fields = ('message_id', 'attachment_id', 'content_type', 'object_id', 'file', 'formatted_timestamp', 'readable_size', 'preview', 'encryption_method')
    exclude = ['size', 'timestamp']

    def preview(self, obj: Moment):
        signed_file_id = sign_resource_id_with_expiry(obj.file.id)
        url = f"{API_BASE_URL}/file/moment/{signed_file_id}/{obj.timestamp}"
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
    search_fields = ('file__name', 'file__id')
    readonly_fields = ('file', 'iv', 'key', 'attachment_id', 'message_id', 'content_type', 'object_id', 'readable_size', 'encryption_method', 'preview')
    exclude = ['size']

    def preview(self, obj):
        signed_file_id = sign_resource_id_with_expiry(obj.file.id)
        url = f"{API_BASE_URL}/file/subtitle/{signed_file_id}/{obj.id}"
        return format_html('<a href="{}" target="_blank">Preview Subtitle</a>', url)

    preview.short_description = "Subtitle Preview"

    def readable_size(self, obj: Subtitle):
        return filesizeformat(obj.size)

    def encryption_method(self, obj: Subtitle):
        return EncryptionMethod(obj.file.encryption_method).name

    readable_size.short_description = 'Size'
    readable_size.admin_order_field = 'size'
