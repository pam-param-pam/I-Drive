from typing import Union, List

from django.contrib import admin
from django.db.models import QuerySet
from django.forms import ModelForm
from django.template.defaultfilters import filesizeformat
from django.utils.html import format_html

from .models import Fragment, Folder, File, UserSettings, UserPerms, ShareableLink, Preview, Thumbnail, UserZIP, VideoPosition, AuditEntry
from .tasks import smart_delete
from .utilities.constants import cache, RAW_IMAGE_EXTENSIONS, API_BASE_URL
from .utilities.other import sign_resource_id_with_expiry

admin.site.register(UserSettings)
admin.site.register(UserPerms)
admin.site.register(VideoPosition)


@admin.register(Fragment)
class FragmentAdmin(admin.ModelAdmin):
    readonly_fields = ('id', 'sequence', 'readable_size', 'file', 'message_id', 'attachment_id', 'size')
    ordering = ["-created_at"]
    list_display = ["sequence", "file_name", "readable_size", "owner", "folder", "created_at"]
    list_select_related = ["file"]
    search_fields = ["file__name"]

    """
    def has_delete_permission(self, request, obj=None):
        # Disable delete
        return False
    """

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

    owner.admin_order_field = "file__owner__username"
    folder.admin_order_field = "file__parent__name"
    readable_size.admin_order_field = "size"
    file_name.admin_order_field = "file__name"


@admin.register(Folder)
class FolderAdmin(admin.ModelAdmin):
    readonly_fields = ('id',)
    ordering = ["-created_at"]
    list_display = ["name", "owner", "ready", "created_at", "inTrash", "is_locked"]
    actions = ['move_to_trash', 'restore_from_trash', 'force_delete_model']
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
        # TODO
        for folder in queryset:
            folder.moveToTrash()

    def restore_from_trash(self, request, queryset: QuerySet[Folder]):
        # TODO

        for folder in queryset:
            folder.restoreFromTrash()

    def save_model(self, request, obj: Folder, form: ModelForm, change: bool):
        cache.delete(obj.id)
        cache.delete(obj.parent.id)
        super().save_model(request, obj, form, change)

    def is_locked(self, obj: File):
        return obj._is_locked()

    is_locked.admin_order_field = 'password'
    is_locked.boolean = True

@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    readonly_fields = ('id', 'formatted_key', 'formatted_iv', 'streamable', 'ready', "created_at", "readable_size", "media_tag")
    ordering = ["-created_at"]
    list_display = ["name", "parent", "readable_size", "owner", "ready",  "created_at",
                    "inTrash", "is_locked"]
    actions = ['move_to_trash', 'restore_from_trash', 'force_ready', 'force_delete_model']
    search_fields = ["name"]

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
            poster_url = f"{API_BASE_URL}/file/thumbnail/{signed_file_id}"  # Example poster URL

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

    formatted_key.short_description = "Encryption key (base64)"
    formatted_iv.short_description = "Encryption iv (base64)"

    media_tag.short_description = 'PREVIEW MEDIA FILE'

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

    readable_size.short_description = 'Size'
    readable_size.admin_order_field = 'size'

    def is_locked(self, obj: File):
        return obj._is_locked()

    is_locked.admin_order_field = 'password'
    is_locked.boolean = True

    def save_model(self, request, obj: File, form: ModelForm, change: bool):
        super().save_model(request, obj, form, change)


@admin.register(Preview)
class PreviewAdmin(admin.ModelAdmin):
    ordering = ["-created_at"]
    list_display = ["file_name", "owner", "readable_size", "readable_encrypted_size", "created_at"]

    def file_name(self, obj: Preview):
        return obj.file.name

    def owner(self, obj: Preview):
        return obj.file.owner

    def readable_size(self, obj: Preview):
        return filesizeformat(obj.size)

    def readable_encrypted_size(self, obj: Preview):
        return filesizeformat(obj.encrypted_size)


@admin.register(Thumbnail)
class ThumbnailAdmin(admin.ModelAdmin):
    ordering = ["-created_at"]
    list_display = ["file_name", "owner", "readable_size", "created_at"]
    readonly_fields = ["thumbnail_media"]

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
