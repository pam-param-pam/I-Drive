from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include, re_path

from website.views.dataViews import users_me, get_folder, get_file, get_breadcrumbs, get_usage, update_settings
from website.views.itemManagmentViews import rename, move_to_trash, move, create_folder, \
    delete, folder_password
from website.views.otherViews import test, index, help1
from website.views.shareViews import get_shares, delete_share, create_share, view_share
from website.views.streamViews import stream_file, download_file, preview  # ,\
    #stream_test, stream_file_test, stream_test
from website.views.uploadViews import create_file

urlpatterns = [
                  path("test/<file_id>", test, name="test"),
                  path("help", help1, name="help"),

                  #path("stream", stream_test, name="stream"),
                  #path("stream2", stream_test2, name="stream"),

                  #path("stream_file", stream_file_test, name="stream"),

                  path("", index, name="index"),


                  path("api/file/create", create_file, name="create file"),
                  path("api/file/<file_id>", get_file, name="get file by file id"),
                  path("api/file/download/<file_id>", download_file, name="download"),
                  #path("api/file/preview/<file_id>", get_file_preview, name="get file preview by file id"),
                  path("api/file/stream/<file_id>", stream_file, name="stream larger files"),
                  path("api/file/preview/<file_id>", preview, name="help"),

                  path('auth/', include('djoser.urls.authtoken')),
                  #path('auth/logout/', auth_views.LogoutView.as_view(), name='logout'),

                  path('auth/user/me', users_me, name="get current user"),


                  path("api/user/updatesettings", update_settings, name="update settings"),

                  path('admin', admin.site.urls),


                  path("api/shares", get_shares, name="get user's shares"),
                  path("api/deleteshare", delete_share, name="create share"),
                  path("api/createshare", create_share, name="delete share"),
                  path("api/share/<token>", view_share, name="get share"),


                  re_path(r'^api/folder/(?P<folder_id>\w+)/$', get_folder, name="get files and folders from a folder id"),
                  re_path(r'^api/folder/usage/(?P<folder_id>\w+)/$', get_usage, name="get size of all files in that folder to all user's files"),
                  path("api/folder/breadcrumbs/<folder_id>", get_breadcrumbs, name="get root's real content"),
                  path("api/folder/create", create_folder, name="create folder"),
                  path("api/folder/password/<folder_id>", folder_password, name="create folder"),

                  path("api/item/move", move, name="move file/folder"),
                  path("api/item/delete", delete, name="delete file/folder"),
                  path("api/item/moveToTrash", move_to_trash, name="move file/folder to trash"),
                  path("api/item/rename", rename, name="rename file/folder"),


                  #path("api/upload", upload_file, name="upload"),
                  #path("api/search/<query>", views.search, name="get m3u8 playlist"),
                  #path("api/stream_key/<file_id>", stream_key, name="stream key"),
                  #path("api/stream/<file_id>", get_m3u8, name="get m3u8 playlist"),
                  #path('api/fragments/<file_id>', get_fragment_urls, name="check token"),
                  #path("api/stream/fragment/<fragment_id>", stream_fragment, name="stream fragment"),
                  #path("api/getfolders", get_folder_tree, name="get files and folders from a folder id"),
                  #path("api/getroot", get_root, name="get root's content"),

              ] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
urlpatterns += [path('silk/', include('silk.urls', namespace='silk'))]
