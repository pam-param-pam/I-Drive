
from django.contrib import admin
from django.core.cache import caches
from django.template.defaultfilters import filesizeformat
from django.utils import timezone

from .models import Fragment, Folder, File, UserSettings, UserPerms, ShareableLink, Preview
from .utilities.constants import cache


@admin.register(Fragment)
class FragmentAdmin(admin.ModelAdmin):
    readonly_fields = ('id', 'sequence', 'readable_size', 'file', 'message_id', 'attachment_id', 'size')
    ordering = ["-created_at"]
    list_display = ["sequence", "file_name", "readable_size", "owner", "folder", "created_at"]
    list_select_related = ["file"]
    """
    def has_delete_permission(self, request, obj=None):
        # Disable delete
        return False
    """

    def owner(self, obj):
        return obj.file.owner

    def folder(self, obj):
        return f"{obj.file.parent.name}({obj.file.parent.id})"

    def readable_size(self, obj):
        return filesizeformat(obj.size)

    def file_name(self, obj):
        a = obj.file.name

        if len(a) < 100:
            return a
        return "*File name to long to display*"


@admin.register(Folder)
class FolderAdmin(admin.ModelAdmin):
    readonly_fields = ('id',)
    ordering = ["-created_at"]
    list_display = ["name", "owner", "created_at", "inTrash"]
    actions = ['move_to_trash', 'restore_from_trash']

    def delete_queryset(self, request, queryset):
        for folder in queryset:
            folder.force_delete()

    # override of default django method(in obj page)
    def delete_model(self, request, obj):
        if isinstance(obj, Folder):
            obj.force_delete()
        else:
            for real_obj in obj:
                real_obj.force_delete()

    def move_to_trash(self, request, queryset):
        for folder in queryset:
            folder.moveToTrash()

    def restore_from_trash(self, request, queryset):
        for folder in queryset:
            folder.restoreFromTrash()

    def save_model(self, request, obj, form, change):
        cache.delete(obj.id)
        cache.delete(obj.parent.id)
        super().save_model(request, obj, form, change)

@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    readonly_fields = ('id', 'key', 'streamable', 'ready', "created_at", "size", "encrypted_size")
    ordering = ["-created_at"]
    list_display = ["name", "parent", "readable_size", "readable_encrypted_size", "owner", "ready", "created_at",
                    "inTrash"]
    actions = ['move_to_trash', 'restore_from_trash', 'force_ready']



    def delete_queryset(self, request, queryset):
        for real_obj in queryset:
            real_obj.force_delete()

    def force_ready(self, request, queryset):
        for real_obj in queryset:
            real_obj.ready = True
            cache.delete(real_obj.id)
            cache.delete(real_obj.parent.id)
            real_obj.save()

    def delete_model(self, request, obj):
        if isinstance(obj, File):

            obj.force_delete()
        else:
            for real_obj in obj:

                real_obj.force_delete()

    def move_to_trash(self, request, queryset):
        for file in queryset:
            file.moveToTrash()

    def restore_from_trash(self, request, queryset):
        for file in queryset:
            file.restoreFromTrash()

    def readable_size(self, obj):
        return filesizeformat(obj.size)

    def readable_encrypted_size(self, obj):
        return filesizeformat(obj.encrypted_size)

    readable_size.short_description = 'SIZE'
    readable_encrypted_size.short_description = 'ENCRYPTED SIZE'

    def save_model(self, request, obj, form, change):

        print(change)
        super().save_model(request, obj, form, change)
admin.site.register(UserSettings)
admin.site.register(UserPerms)

@admin.register(Preview)
class PreviewAdmin(admin.ModelAdmin):
    ordering = ["-created_at"]
    list_display = ["file_name", "owner", "readable_size", "readable_encrypted_size", "created_at"]

    def file_name(self, obj):
        return obj.file.name

    def owner(self, obj):
        return obj.file.owner

    def readable_size(self, obj):
        return filesizeformat(obj.size)

    def readable_encrypted_size(self, obj):
        return filesizeformat(obj.encrypted_size)
"""
admin.site.register(Thumbnail)
"""

class ShareableLinkAdmin(admin.ModelAdmin):
    readonly_fields = ('token',)

    list_display = ('token', 'expiration_time', 'owner', 'content_type', 'object_id')

    # Add other configurations as needed


admin.site.register(ShareableLink, ShareableLinkAdmin)
