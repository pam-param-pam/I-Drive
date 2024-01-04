from django.contrib import admin
from django.template.defaultfilters import filesizeformat

from .models import Fragment, Folder, File
from website.tasks import delete_file_task


@admin.register(Fragment)
class FragmentAdmin(admin.ModelAdmin):
    readonly_fields = ('id', 'sequence', 'readable_size', 'file', 'message_id', 'size')
    list_display = ["sequence", "file", "readable_size", "owner", "folder"]
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


@admin.register(Folder)
class FolderAdmin(admin.ModelAdmin):
    readonly_fields = ('id',)


@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    readonly_fields = ('id', 'm3u8_message_id', 'key', 'streamable', 'ready', "created_at", "size", "encrypted_size")
    actions = ['delete_model']
    ordering = ["created_at"]
    list_display = ["name", "parent", "readable_size", "readable_encrypted_size", "owner", "ready", "created_at"]
    """
    def has_delete_permission(self, request, obj=None):
        # Disable default delete so it's not shown
        return False
    """
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
