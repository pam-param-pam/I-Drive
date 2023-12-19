from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include

from website import views



urlpatterns = [
        path("", views.index, name="index"),
        path("upload", views.upload_file, name="upload"),
        path("download/<file_id>", views.download, name="download"),
        path("stream/<file_id>/key", views.streamkey, name="stream key"),
        path("stream/<file_id>", views.get_m3u8, name="get m3u8 playlist"),

        path("folder/<folder_id>", views.test, name="get files and folders from a folder id"),

        path("createfolder/<folder_name>", views.test, name="create folder"),

        path("movefolder/<folder_id>/<parent_folder_id>", views.test, name="move folder"),
        path("movefile/<file_id>/<parent_folder_id>", views.test, name="move file"),

        path("deletefile/<file_id>", views.delete_file, name="delete file"),
        path("deletefolder/<folder_name>", views.test, name="delete folder"),

        path("changefilename/<file_id>", views.test, name="change file name"),
        path("changefoldername/<folder_id>", views.test, name="change folder name"),

        # this will create a temporary share url to a file accessible to everyone
        path("share/<file_id>", views.test, name="share file"),

        # this will create a 1 time only link, that will make the first logged-in user be able to access this file/folder(see, download)
        path("addviewer/<id>", views.test, name="add viewer"),

        # this will create a 1 time only link, that will make the first logged-in user be able to maintain this file/folder(see, download, edit name, move, share)
        path("addmaintainer/<id>", views.test, name="add maintainer"),


] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
