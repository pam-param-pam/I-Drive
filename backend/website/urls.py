from django.conf import settings
from django.contrib import admin
from django.urls import path, re_path
from django.views.static import serve
from djoser.views import TokenCreateView

from .views.ZipViews import create_zip_model
from .views.dataViews import get_folder_info, get_file_info, get_breadcrumbs, get_usage, search, \
    get_trash, check_password, get_dirs, fetch_additional_info, get_secrets
from .views.itemManagmentViews import rename, move_to_trash, move, \
    delete, folder_password, restore_from_trash, create_folder, reset_folder_password, update_video_position, add_tag, remove_tag
from .views.shareViews import get_shares, delete_share, create_share, view_share, create_share_zip_model, share_view_stream, share_view_thumbnail, share_view_preview
from .views.streamViews import get_preview, get_thumbnail, stream_file, stream_zip_files
from .views.testViews import get_folder_password
from .views.uploadViews import create_file, create_thumbnail
from .views.userViews import change_password, users_me, update_settings, MyTokenDestroyView, register_user, get_discord_settings, add_webhook, delete_webhook, add_bot, delete_bot, \
    update_upload_destination, enable_bot, can_upload

urlpatterns = [

    path("zip", create_zip_model, name="create zip model"),
    path('stream/<signed_file_id>', stream_file, name="stream file"),
    path('zip/<token>', stream_zip_files),
    path("trash", get_trash, name="trash"),
    path("search", search, name="search"),

    path("file/create", create_file, name="create file"),
    path("file/<file_id>", get_file_info, name="get file by file id"),
    path("file/preview/<signed_file_id>", get_preview, name="get preview by file id"),

    path("file/thumbnail/create", create_thumbnail, name="create thumbnail"),
    path("file/thumbnail/<signed_file_id>", get_thumbnail, name="get thumbnail by file id"),

    path("file/secrets/<file_id>", get_secrets, name="gets encryption key and iv"),

    path("file/video/position", update_video_position, name="update video position"),

    path("file/tag/add", add_tag, name="add a tag"),
    path("file/tag/remove", remove_tag, name="remove a tag"),

    path("auth/token/login", TokenCreateView.as_view(), name="login"),
    path("auth/register", register_user, name="register"),
    path("auth/token/logout", MyTokenDestroyView.as_view(), name="logout"),

    path('user/me', users_me, name="get current user"),
    path('user/canUpload', can_upload, name="check if user is allowed to upload"),
    path("user/changepassword", change_password, name="change password"),
    path("user/updatesettings", update_settings, name="update settings"),
    path("user/discordSettings", get_discord_settings, name="get discord settings"),
    path("user/discordSettings/webhook/add", add_webhook, name="add a webhook"),
    path("user/discordSettings/webhook/delete", delete_webhook, name="delete a webhook"),
    path("user/discordSettings/bot/add", add_bot, name="add a bot"),
    path("user/discordSettings/bot/delete", delete_bot, name="delete a bot"),
    path("user/discordSettings/bot/enable", enable_bot, name="enable a bot"),
    path("user/updateDiscordSettings", update_upload_destination, name="update upload destination"),

    path("shares", get_shares, name="get user's shares"),
    path("share/delete", delete_share, name="delete share"),
    path("share/create", create_share, name="create share"),
    path("share/zip/<token>", create_share_zip_model, name="create zip for share"),
    path("share/stream/<token>/<file_id>", share_view_stream, name="view share file stream"),
    path("share/thumbnail/<token>/<file_id>", share_view_thumbnail, name="view share file thumbnail"),
    path("share/preview/<token>/<file_id>", share_view_preview, name="view share file preview"),

    re_path(r'^share/(?P<token>[^/]+)(/(?P<folder_id>[^/]+))?$', view_share, name='view_share'),

    path("folder/create", create_folder, name="create folder"),
    path('folder/<folder_id>', get_folder_info, name="get files and folders from a folder id"),
    path('folder/dirs/<folder_id>', get_dirs, name="get folders from a folder id"),
    path('folder/usage/<folder_id>', get_usage, name="get size of all files in that folder to all user's files"),
    path("folder/breadcrumbs/<folder_id>", get_breadcrumbs, name="get root's real content"),
    path("folder/password/<folder_id>", folder_password, name="create folder"),
    path("folder/password/reset/<folder_id>", reset_folder_password, name="create folder"),
    path("folder/moreinfo/<folder_id>", fetch_additional_info, name="fetch more info about a folder"),

    path("item/move", move, name="move file/folder"),
    path("item/delete", delete, name="delete file/folder"),
    path("item/moveToTrash", move_to_trash, name="move file/folder to trash"),
    path("item/restoreFromTrash", restore_from_trash, name="move file/folder to trash"),
    path("item/rename", rename, name="rename file/folder"),

    path("resource/password/<resource_id>", check_password, name="check password"),

    path('admin', admin.site.urls),

    path('test/<file_id>', get_folder_password),
    # path('download-test/', download_large_file, name='download_test'),

    re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),

]
# urlpatterns += [path('silk/', include('silk.urls', namespace='silk'))]
