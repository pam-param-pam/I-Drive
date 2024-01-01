from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

from website import views

urlpatterns = [
                  path("test", views.test, name="download"),

                  path('auth/', include('djoser.urls.authtoken')),
                  path("", views.index, name="index"),
                  path('admin', admin.site.urls),
                  path("upload", views.upload_file, name="upload"),
                  path("download/<file>", views.download, name="download"),
                  path("stream/<file_id>/key", views.stream_key, name="stream key"),
                  path("stream/<file_id>", views.get_m3u8, name="get m3u8 playlist"),

                  path("search/<query>", views.search, name="get m3u8 playlist"),

                  path("folder/<folder_id>", views.get_folder, name="get files and folders from a folder id"),
                  path("getfolders", views.get_folder_tree, name="get files and folders from a folder id"),

                  path("createfolder", views.create_folder, name="create folder"),

                  path("movefolder", views.movefolder, name="move folder"),
                  path("movefile", views.movefile, name="move file"),

                  path("deletefile", views.delete_file, name="delete file"),
                  path("deletefolder", views.delete_folder, name="delete folder"),

                  path("changefilename", views.change_file_name, name="change file name"),
                  path("changefoldername", views.change_folder_name, name="change folder name"),

                  # this will create a temporary share url to a file accessible to everyone
                  path("share/<file_id>", views.test, name="share file"),

                  # this will create a 1 time only link, that will make the first logged-in user be able to access this file/folder(see, download)
                  path("addviewer/<id>", views.test, name="add viewer"),

                  # this will create a 1 time only link, that will make the first logged-in user be able to maintain this file/folder(see, download, edit name, move, share)
                  path("addmaintainer/<id>", views.test, name="add maintainer"),

              ] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
