from django.contrib import admin
from django.template.defaultfilters import filesizeformat

from .models import Fragment, Folder, File
from website.tasks import delete_files


@admin.register(Fragment)
class FragmentAdmin(admin.ModelAdmin):
    readonly_fields = ('id',)
    #exclude = ['age']



@admin.register(Folder)
class FolderAdmin(admin.ModelAdmin):
    readonly_fields = ('id',)


@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    readonly_fields = ('id', 'm3u8_message_id', 'key', 'streamable', 'ready', "uploaded_at", "size", "encrypted_size")
    actions = ['delete_model']
    ordering = ["uploaded_at"]
    list_display = ["name", "readable_size", "readable_encrypted_size", "owner", "ready", "uploaded_at"]

    def delete_model(self, request, obj):
        if isinstance(obj, File):
            delete_files.delay(request.user.id, request.request_id, obj.id)
        else:
            for real_obj in obj:
                delete_files.delay(request.user.id, request.request_id, real_obj.id)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            delete_files.delay(request.user.id, request.request_id, obj.id)

    def readable_size(self, obj):
        return filesizeformat(obj.size)
    def readable_encrypted_size(self, obj):
        return filesizeformat(obj.encrypted_size)

    readable_size.short_description = 'SIZE'
    readable_encrypted_size.short_description = 'ENCRYPTED SIZE'

