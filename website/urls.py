from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

from website import views

urlpatterns = [
                  path("test", views.test, name="download"),

                  path('auth/', include('djoser.urls.authtoken')),
                  path('auth/users/me', views.users_me, name="get current user"),

                  path("", views.index, name="index"),
                  path('admin', admin.site.urls),
                  path("api/upload", views.upload_file, name="upload"),
                  path("api/download/<file>", views.download, name="download"),
                  path("api/stream_key/<file_id>", views.stream_key, name="stream key"),
                  path("api/stream/<file_id>", views.get_m3u8, name="get m3u8 playlist"),

                  path("api/search/<query>", views.search, name="get m3u8 playlist"),

                  path("api/folder/<folder_id>", views.get_folder, name="get files and folders from a folder id"),
                  path("api/getfolders", views.get_folder_tree, name="get files and folders from a folder id"),
                  path("api/getroot", views.get_root, name="get root's content"),
                  path("api/breadcrumbs/<folder_id>", views.get_breadcrumbs, name="get root's real content"),

                  path("api/updatesettings", views.update_settings, name="update settings"),

                  path("api/createfolder", views.create_folder, name="create folder"),

                  path("api/move", views.move, name="move file/folder"),

                  path("api/delete", views.delete, name="delete file/folder"),
                  path("api/usage", views.usage, name="get total size of all files"),

                  path("api/rename", views.rename, name="rename file/folder"),

                  # this will create a temporary share url to a file accessible to everyone
                  path("api/share/<file_id>", views.test, name="share file"),

                  # this will create a 1 time only link, that will make the first logged-in user be able to access this file/folder(see, download)
                  path("api/addviewer/<id>", views.test, name="add viewer"),

                  # this will create a 1 time only link, that will make the first logged-in user be able to maintain this file/folder(see, download, edit name, move, share)
                  path("api/addmaintainer/<id>", views.test, name="add maintainer"),

              ] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
