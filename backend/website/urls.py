from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path
from djoser.views import TokenCreateView

from website.views.ZipViews import create_zip_model, get_zip_info
from website.views.dataViews import get_folder_info, get_file_info, get_breadcrumbs, get_usage, search, \
    get_trash, get_fragment, get_fragments_info, get_thumbnail_info, check_password, get_dirs, fetch_additional_info, get_secrets
from website.views.itemManagmentViews import rename, move_to_trash, move, \
    delete, folder_password, restore_from_trash, create_folder, reset_folder_password
from website.views.otherViews import index, generate_keys, test
from website.views.shareViews import get_shares, delete_share, create_share, view_share
from website.views.streamViews import get_preview
from website.views.uploadViews import create_file, create_thumbnail
from website.views.userViews import change_password, users_me, update_settings, MyTokenDestroyView

urlpatterns = [
                  #path("test", test, name="test"),
                  path("test", test, name="test"),

                  path('generate-keys', generate_keys, name='generate-keys'),
                  path("api/zip/<token>", get_zip_info, name="get zip model info"),
                  path("api/zip", create_zip_model, name="create zip model"),

                  path("api/trash", get_trash, name="trash"),
                  path("api/search", search, name="search"),

                  path("api/file/create", create_file, name="create file"),
                  path("api/file/<file_id>", get_file_info, name="get file by file id"),
                  path("api/file/preview/<file_id>", get_preview, name="get preview by file id"),
                  path("api/file/thumbnail/create", create_thumbnail, name="create preview"),
                  path("api/file/thumbnail/<file_id>", get_thumbnail_info, name="create preview"),
                  path("api/file/secrets/<file_id>", get_secrets, name="gets encryption key and iv"),

                  path("auth/token/login", TokenCreateView.as_view(), name="login"),
                  path("auth/token/logout", MyTokenDestroyView.as_view(), name="logout"),
                  path('auth/user/me', users_me, name="get current user"),

                  path("api/user/changepassword", change_password, name="change password"),
                  path("api/user/updatesettings", update_settings, name="update settings"),

                  path("api/shares", get_shares, name="get user's shares"),
                  path("api/share/delete", delete_share, name="delete share"),
                  path("api/share/create", create_share, name="create share"),
                  path("api/share/<token>", view_share, name="get share"),
                  path("api/share/<token>/<folder_id>", view_share, name="get folder from share"),

                  path("api/folder/create", create_folder, name="create folder"),
                  path('api/folder/<folder_id>', get_folder_info, name="get files and folders from a folder id"),
                  path('api/folder/dirs/<folder_id>', get_dirs, name="get folders from a folder id"),
                  path('api/folder/usage/<folder_id>', get_usage, name="get size of all files in that folder to all user's files"),
                  path("api/folder/breadcrumbs/<folder_id>", get_breadcrumbs, name="get root's real content"),
                  path("api/folder/password/<folder_id>", folder_password, name="create folder"),
                  path("api/folder/password/reset/<folder_id>", reset_folder_password, name="create folder"),
                  path("api/folder/moreinfo/<folder_id>", fetch_additional_info, name="fetch more info about a folder"),

                  path("api/item/move", move, name="move file/folder"),
                  path("api/item/delete", delete, name="delete file/folder"),
                  path("api/item/moveToTrash", move_to_trash, name="move file/folder to trash"),
                  path("api/item/restoreFromTrash", restore_from_trash, name="move file/folder to trash"),
                  path("api/item/rename", rename, name="rename file/folder"),

                  path('api/fragments/<file_id>/<int:sequence>', get_fragment, name="get fragments"),
                  path('api/fragments/<file_id>', get_fragments_info, name="get fragments"),

                  path("api/resource/password/<resource_id>", check_password, name="check password"),

                  path('admin', admin.site.urls),
                  path("", index, name="index"),


              ] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
# urlpatterns += [path('silk/', include('silk.urls', namespace='silk'))]
