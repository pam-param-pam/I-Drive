from django.contrib import admin
from .models import Fragment, Folder, File


@admin.register(Fragment)
class FragmentAdmin(admin.ModelAdmin):
    readonly_fields = ('id',)


@admin.register(Folder)
class FolderAdmin(admin.ModelAdmin):
    readonly_fields = ('id',)


@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    readonly_fields = ('id',)

