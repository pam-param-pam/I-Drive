from django.conf import settings
from django.contrib import admin
from django.http import HttpResponseNotAllowed, HttpResponseNotFound
from django.urls import path as django_path
from django.urls import re_path
from django.views.decorators.csrf import csrf_exempt
from django.views.static import serve

from .views.ZipViews import create_zip_model
from .views.authViews import login_per_device_view, logout_per_device_view, register_user_view, get_qr_session_view, authenticate_qr_session_view, get_qr_session_device_info_view, \
    cancel_pending_qr_session_view, change_password_view, healthcheck_view
from .views.dataViews import get_folder_info, get_file_info, get_breadcrumbs, get_usage, search, \
    get_trash, check_password, get_dirs, fetch_additional_info, get_moments, get_tags, get_subtitles, ultra_download_metadata, get_attachment_url_view, get_file_stats, check_attachment_id, \
    check_message_id, get_fragment_for_crc
from .views.itemManagmentViews import rename_view, move_to_trash, move, \
    delete, change_folder_password_view, restore_from_trash, create_folder_view, reset_folder_password_view, update_video_position_view, add_tag_view, remove_tag_view, remove_moment_view, \
    add_moment_view, change_file_crc_view, add_subtitle_view, remove_subtitle_view, rename_subtitle_view, change_fragment_crc_view
from .views.shareViews import get_shares, delete_share, create_share, view_share, create_share_zip_model, share_view_stream, share_view_thumbnail, share_view_subtitle, \
    share_get_subtitles, check_share_password, get_share_visits
from .views.streamViews import stream_thumbnail, stream_file, stream_zip_files, stream_moment, stream_subtitle
from .views.testViews import get_discord_state
from .views.uploadViews import create_file_view, create_or_edit_thumbnail_view, edit_file_view, create_linker
from .views.userViews import users_me, update_settings, get_discord_settings_view, add_webhook_view, delete_webhook_view, add_bot_view, \
    delete_bot_view, update_attachment_name_view, can_upload, discord_settings_start_view, reset_discord_settings_view, list_active_devices_view, revoke_device_view, logout_all_devices_view

_route_registry = {}
_registered_routes = set()


def method_dispatcher(route):
    def view(request, *args, **kwargs):
        methods_map = _route_registry.get(route, {})
        handler = methods_map.get(request.method)
        if not handler:
            return HttpResponseNotAllowed(methods_map.keys())

        wrapped_handler = handler
        return wrapped_handler(request, *args, **kwargs)

    return csrf_exempt(view)


def path(route, methods, view_func, **kwargs):
    methods = [m.upper() for m in methods]

    if route not in _route_registry:
        _route_registry[route] = {}

    for method in methods:
        if method in _route_registry[route]:
            raise ValueError(f"Duplicate method {method} for route {route}")
        _route_registry[route][method] = view_func

    if route not in _registered_routes:
        _registered_routes.add(route)
        return django_path(route, method_dispatcher(route), **kwargs)

    return django_path(
        f"__dummy_noop_for_{route}__",
        lambda request, *args, **kwargs: HttpResponseNotFound([]),
    )


urlpatterns = [
    path("trash", ["GET"], get_trash, name="trash"),
    path("search", ["GET"], search, name="search"),

    path("files/<signed_file_id>/thumbnail/stream", ["GET"], stream_thumbnail, name="stream_thumbnail"),
    path("files/<signed_file_id>/moments/<moment_id>/stream", ["GET"], stream_moment, name="stream_moment"),
    path("files/<signed_file_id>/subtitles/<subtitle_id>/stream", ["GET"], stream_subtitle, name="stream_subtitle"),
    path("files/<signed_file_id>/stream", ["GET"], stream_file, name="stream_subtitle"),

    path("files", ["POST"], create_file_view, name="create file"),
    path("files/<file_id>", ["PATCH"], edit_file_view, name="edit file"),
    path("files/<file_id>", ["GET"], get_file_info, name="get file info"),
    path("files/<file_id>/thumbnail", ["POST"], create_or_edit_thumbnail_view, name="create a thumbnail"),
    path("files/<file_id>/video-position", ["PUT"], update_video_position_view, name="update video position"),

    path("files/<file_id>/tags", ["POST"], add_tag_view, name="add a tag"),
    path("files/<file_id>/tags", ["GET"], get_tags, name="get file moments"),
    path("files/<file_id>/tags/<tag_id>", ["DELETE"], remove_tag_view, name="remove a tag"),
    path("files/<file_id>/moments", ["GET"], get_moments, name="add a moment"),
    path("files/<file_id>/moments", ["POST"], add_moment_view, name="get all moments"),
    path("files/<file_id>/moments/<moment_id>", ["DELETE"], remove_moment_view, name="remove a moment"),
    path("files/<file_id>/subtitles", ["POST"], add_subtitle_view, name="add subtitle"),
    path("files/<file_id>/subtitles", ["GET"], get_subtitles, name="get file subtitles"),
    path("files/<file_id>/subtitles/<subtitle_id>", ["PATCH"], rename_subtitle_view, name="rename subtitle"),
    path("files/<file_id>/subtitles/<subtitle_id>", ["DELETE"], remove_subtitle_view, name="remove subtitle"),
    path('files/<file_id>/changecrc', ['PATCH'], change_file_crc_view, name='change crc'),

    path("folders", ["POST"], create_folder_view, name="create folder"),
    path('folders/<folder_id>', ["GET"], get_folder_info, name="get files and folders from a folder id"),
    path('folders/<folder_id>/dirs', ["GET"], get_dirs, name="get folders from a folder id"),
    path('folders/<folder_id>/usage', ["GET"], get_usage, name="get size of all files in that folder to all user's files"),
    path("folders/<folder_id>/breadcrumbs", ["GET"], get_breadcrumbs, name="get folder's breadcrumbs"),
    path("folders/<folder_id>/password", ["POST"], change_folder_password_view, name="change folder password"),
    path("folders/<folder_id>/password/reset", ["POST"], reset_folder_password_view, name="create folder"),
    path("folders/<folder_id>/stats", ['GET'], get_file_stats, name="get file stats for folder"),

    path("items/move", ["PATCH"], move, name="bulk move items"),
    path("items/moveToTrash", ["PATCH"], move_to_trash, name="bulk move items to trash"),
    path("items/restoreFromTrash", ["PATCH"], restore_from_trash, name="move items to trash"),
    path("items/delete", ["POST"], delete, name="bulk delete items"),
    path("items/zip", ["POST"], create_zip_model, name="create zip model"),

    path("items/<item_id>/moreinfo", ["GET"], fetch_additional_info, name="fetch more info about an item"),
    path("items/<item_id>/rename", ["PATCH"], rename_view, name="rename an item"),
    path("items/<item_id>/password", ['GET'], check_password, name="check password"),
    path("items/ultraDownload/items/<item_id>", ['POST'], ultra_download_metadata, name="download metadata for ultra download, user supplies ids"),
    path("items/ultraDownload/attachments/<attachment_id>", ['GET'], get_attachment_url_view, name="download metadata for ultra download"),
    path('zip/<token>', ['GET'], stream_zip_files),

    django_path("auth/token/login", login_per_device_view, name="login"),
    django_path("auth/token/logout", logout_per_device_view, name="logout"),
    django_path("auth/register", register_user_view, name="register"),
    django_path('auth/qrcode', get_qr_session_view, name='get qr code session'),
    django_path('auth/qrcode/<session_id>', authenticate_qr_session_view, name='authenticate a qr session'),
    django_path('auth/qrcode/get/<session_id>', get_qr_session_device_info_view, name='get new device info by session id'),
    django_path('auth/qrcode/cancel/<session_id>', cancel_pending_qr_session_view, name='cancel new device pending session'),
    django_path("auth/password", change_password_view, name="change password"),

    path('user/me', ['GET'], users_me, name="get current user"),
    path('user/canUpload/<folder_id>', ['GET'], can_upload, name="check if user is allowed to upload"),
    path("user/settings", ['PUT'], update_settings, name="update settings"),

    path("user/devices", ['GET'], list_active_devices_view, name="list active devices"),
    path("user/devices/logout-all", ['POST'], logout_all_devices_view, name="logouts all devices"),
    path("user/devices/<device_id>", ['DELETE'], revoke_device_view, name="revoke a device"),

    path("user/discordSettings", ['GET'], get_discord_settings_view, name="get discord settings"),
    path("user/discordSettings", ['PATCH'], update_attachment_name_view, name="update upload destination"),
    path("user/discordSettings", ['DELETE'], reset_discord_settings_view, name="reset discord settings"),
    path("user/discordSettings/autoSetup", ['POST'], discord_settings_start_view, name="do auto setup"),
    path("user/discordSettings/webhooks", ['POST'], add_webhook_view, name="add a webhook"),
    path("user/discordSettings/webhooks/<webhook_id>", ['DELETE'], delete_webhook_view, name="delete a webhook"),
    path("user/discordSettings/bots", ['POST'], add_bot_view, name="add a bot"),
    path("user/discordSettings/bots/<bot_id>", ['DELETE'], delete_bot_view, name="delete a bot"),

    path("shares", ['GET'], get_shares, name="get user's shares"),
    path("shares", ['POST'], create_share, name="create share"),
    path("shares/<token>/visits", ['GET'], get_share_visits, name="get share visits"),
    path("shares/<token>", ['DELETE'], delete_share, name="delete share"),
    path('shares/<token>', ['GET'], view_share, name='view_share'),
    path('shares/<token>/folders/<folder_id>', ['GET'], view_share, name='view_share'),
    path("shares/<token>/files/<file_id>/subtitles", ['GET'], share_get_subtitles, name="view share file all subtitles"),
    path("shares/<token>/zip", ['POST'], create_share_zip_model, name="create zip for share"),
    path("shares/<token>/files/<signed_file_id>/stream", ['GET'], share_view_stream, name="view share file stream"),
    path("shares/<token>/files/<signed_file_id>/thumbnail/stream", ['GET'], share_view_thumbnail, name="view share file thumbnail"),
    path("shares/<token>/files/<signed_file_id>/subtitles/<subtitle_id>/stream", ['GET'], share_view_subtitle, name="view share file subtitle"),
    path("shares/<token>/password", ['GET'], check_share_password, name="check share password"),

    django_path('admin', admin.site.urls),
    django_path('test', get_discord_state),

    path('healthcheck/', ['GET'], healthcheck_view, name='check health of the backend server'),

    path("fixcrc/fragments", ['GET'], get_fragment_for_crc, name="check if attachment id is used"),
    path('fixcrc/fragments/<fragment_id>', ['PATCH'], change_fragment_crc_view, name='change crc'),

    path("cleanup/<attachment_id>", ['GET'], check_attachment_id, name="check if attachment id is used"),
    path("cleanup/<check_message_id>", ['GET'], check_message_id, name="check if message id is used"),

    path("linker", ['POST'], create_linker, name="create_linker"),


    re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
    # 85 endpoints
]
# urlpatterns += [path('silk/', include('silk.urls', namespace='silk'))]
