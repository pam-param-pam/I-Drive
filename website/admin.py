import secrets

from django.contrib import admin
from django.template.defaultfilters import filesizeformat

from .models import Fragment, Folder, File, UserSettings, UserPerms, ShareableLink
from website.tasks import delete_file_task, delete_folder_task


@admin.register(Fragment)
class FragmentAdmin(admin.ModelAdmin):
    readonly_fields = ('id', 'sequence', 'readable_size', 'file', 'message_id', 'size')
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

    actions = ['delete_model']

    def delete_queryset(self, request, queryset):
        if isinstance(queryset, File):
            delete_folder_task.delay(request.user.id, request.request_id, queryset.id)
        else:
            for real_obj in queryset:
                delete_folder_task.delay(request.user.id, request.request_id, real_obj.id)

    def delete_model(self, request, obj):
        if isinstance(obj, File):
            delete_file_task.delay(request.user.id, request.request_id, obj.id)
        else:
            for real_obj in obj:
                delete_file_task.delay(request.user.id, request.request_id, real_obj.id)

@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    readonly_fields = ('id', 'm3u8_message_id', 'key', 'streamable', 'ready', "created_at", "size", "encrypted_size")
    ordering = ["created_at"]
    list_display = ["name", "parent", "readable_size", "readable_encrypted_size", "owner", "ready", "created_at"]
    """
    def has_delete_permission(self, request, obj=None):
        # Disable default delete so it's not shown
        return False
    """

    def delete_queryset(self, request, queryset):
        if isinstance(queryset, File):
            delete_file_task.delay(request.user.id, request.request_id, queryset.id)
        else:
            for real_obj in queryset:
                delete_file_task.delay(request.user.id, request.request_id, real_obj.id)

    def delete_model(self, request, obj):
        if isinstance(obj, File):
            delete_file_task.delay(request.user.id, request.request_id, obj.id)
        else:
            for real_obj in obj:
                delete_file_task.delay(request.user.id, request.request_id, real_obj.id)

    def readable_size(self, obj):
        return filesizeformat(obj.size)

    def readable_encrypted_size(self, obj):
        return filesizeformat(obj.encrypted_size)

    readable_size.short_description = 'SIZE'
    readable_encrypted_size.short_description = 'ENCRYPTED SIZE'


admin.site.register(UserSettings)
admin.site.register(UserPerms)


class ShareableLinkAdmin(admin.ModelAdmin):
    readonly_fields = ('token',)

    list_display = ('token', 'expiration_time', 'owner', 'content_type', 'object_id')

    # Add other configurations as needed


admin.site.register(ShareableLink, ShareableLinkAdmin)
