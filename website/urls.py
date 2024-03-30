from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include, re_path

from website.views.dataViews import users_me, get_shares, view_share, get_folder, get_file, get_breadcrumbs, get_usage, update_settings
from website.views.fileManagmentViews import rename, move_to_trash, move, create_folder, delete_share, create_share, \
    delete
from website.views.otherViews import test, index
from website.views.streamViews import get_fragment_urls, download, get_file_preview
from website.views.uploadViews import create_file

urlpatterns = [
                  path("test/<folder_id>", test, name="download"),
                  path("api/createfile", create_file, name="create file"),

                  path("api/file/preview/<file_id>", get_file_preview, name="get file preview by file id"),

                  path('auth/', include('djoser.urls.authtoken')),
                  path('auth/users/me', users_me, name="get current user"),
                  path('api/fragments/<file_id>', get_fragment_urls, name="check token"),
                  #path("api/stream/fragment/<fragment_id>", stream_fragment, name="stream fragment"),

                  path("", index, name="index"),
                  path('admin', admin.site.urls),
                  #path("api/upload", upload_file, name="upload"),
                  path("api/download/<file_id>", download, name="download"),
                  #path("api/stream_key/<file_id>", stream_key, name="stream key"),
                  #path("api/stream/<file_id>", get_m3u8, name="get m3u8 playlist"),

                  path("api/shares", get_shares, name="get user's shares"),

                  path("api/deleteshare", delete_share, name="create share"),
                  path("api/createshare", create_share, name="delete share"),
                  path("api/share/<token>", view_share, name="get share"),

                  # path("api/search/<query>", views.search, name="get m3u8 playlist"),

                  re_path(r'^api/folder/(?P<folder_id>\w+)/$', get_folder, name="get files and folders from a folder id"),
                  path("api/file/<file_id>", get_file, name="get file by file id"),

                  #path("api/getfolders", get_folder_tree, name="get files and folders from a folder id"),
                  #path("api/getroot", get_root, name="get root's content"),
                  path("api/breadcrumbs/<folder_id>", get_breadcrumbs, name="get root's real content"),

                  path("api/updatesettings", update_settings, name="update settings"),

                  path("api/createfolder", create_folder, name="create folder"),

                  path("api/move", move, name="move file/folder"),
                  path("api/delete", delete, name="delete file/folder"),

                  path("api/moveToTrash", move_to_trash, name="move file/folder to trash"),
                  path("api/usage/<folder_id>", get_usage, name="get total size of all files"),

                  path("api/rename", rename, name="rename file/folder"),

              ] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
