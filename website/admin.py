from django.contrib import admin
from .models import Fragment, Folder, File


@admin.register(Fragment)
class FragmentAdmin(admin.ModelAdmin):
    pass

@admin.register(Folder)
class FolderAdmin(admin.ModelAdmin):
    pass

@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    pass
