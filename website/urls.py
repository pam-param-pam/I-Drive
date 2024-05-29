from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

from website.views.dataViews import get_folder, get_file, get_breadcrumbs, get_usage, search, \
    get_trash, get_fragment, get_fragments_info, get_thumbnail_info
from website.views.itemManagmentViews import rename, move_to_trash, move, \
    delete, folder_password, restore_from_trash, create_folder
from website.views.otherViews import test, index
from website.views.shareViews import get_shares, delete_share, create_share, view_share
from website.views.streamViews import preview
from website.views.uploadViews import create_file, create_preview
from website.views.userViews import change_password, users_me, update_settings

urlpatterns = [
                  path("test", test, name="test"),
                  # path("help", help1, name="help"),
                  # path("test", test, name="help"),
                  # path('generate-keys/', generate_keys, name='generate-keys'),

                  path("api/trash", get_trash, name="trash"),
                  path("api/search", search, name="search"),

                  path("api/file/create", create_file, name="create file"),
                  path("api/file/<file_id>", get_file, name="get file by file id"),
                  path("api/file/preview/<file_id>", preview, name="get preview by file id"),
                  path("api/file/thumbnail/create", create_preview, name="create preview"),
                  path("api/file/thumbnail/<file_id>", get_thumbnail_info, name="create preview"),

                  path('auth/', include('djoser.urls.authtoken')),
                  path('auth/user/me', users_me, name="get current user"),

                  path("api/user/changepassword", change_password, name="change password"),
                  path("api/user/updatesettings", update_settings, name="update settings"),

                  path("api/shares", get_shares, name="get user's shares"),
                  path("api/share/delete", delete_share, name="delete share"),
                  path("api/share/create", create_share, name="create share"),
                  path("api/share/<token>", view_share, name="get share"),
                  path("api/share/<token>/<folder_id>", view_share, name="get folder from share"),

                  path("api/folder/create", create_folder, name="create folder"),
                  path('api/folder/<folder_id>', get_folder, name="get files and folders from a folder id"),
                  path('api/folder/usage/<folder_id>', get_usage, name="get size of all files in that folder to all user's files"),
                  path("api/folder/breadcrumbs/<folder_id>", get_breadcrumbs, name="get root's real content"),
                  path("api/folder/password/<folder_id>", folder_password, name="create folder"),

                  path("api/item/move", move, name="move file/folder"),
                  path("api/item/delete", delete, name="delete file/folder"),
                  path("api/item/moveToTrash", move_to_trash, name="move file/folder to trash"),
                  path("api/item/restore", restore_from_trash, name="move file/folder to trash"),
                  path("api/item/rename", rename, name="rename file/folder"),

                  path('api/fragments/<file_id>/<int:sequence>', get_fragment, name="get fragments"),
                  path('api/fragments/<file_id>', get_fragments_info, name="get fragments"),

                  path('admin', admin.site.urls),
                  path("", index, name="index"),


              ] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
# urlpatterns += [path('silk/', include('silk.urls', namespace='silk'))]
