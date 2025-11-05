from django.conf import settings
from django.contrib import admin
from django.http import HttpResponseNotAllowed, HttpResponseNotFound
from django.urls import path as django_path
from django.urls import re_path
from django.views.decorators.csrf import csrf_exempt
from django.views.static import serve

from .views.ZipViews import create_zip_model
from .views.authViews import login_per_device, logout_per_device, register_user, get_qr_session, authenticate_qr_session, get_qr_session_device_info, cancel_pending_qr_session
from .views.dataViews import get_folder_info, get_file_info, get_breadcrumbs, get_usage, search, \
    get_trash, check_password, get_dirs, fetch_additional_info, get_moments, get_tags, get_subtitles, ultra_download_metadata, get_attachment_url_view, get_file_stats, check_attachment_id
from .views.itemManagmentViews import rename, move_to_trash, move, \
    delete, change_folder_password, restore_from_trash, create_folder, reset_folder_password, update_video_position, add_tag, remove_tag, remove_moment, add_moment, change_crc, add_subtitle, \
    remove_subtitle
from .views.shareViews import get_shares, delete_share, create_share, view_share, create_share_zip_model, share_view_stream, share_view_thumbnail, share_view_preview, share_view_subtitle, \
    share_get_subtitles, check_share_password, get_share_visits
from .views.streamViews import stream_preview, stream_thumbnail, stream_file, stream_zip_files, stream_moment, stream_subtitle
from .views.testViews import your_ip, get_discord_state
from .views.uploadViews import create_file, create_or_edit_thumbnail, edit_file
from .views.userViews import change_password, users_me, update_settings, get_discord_settings, add_webhook, delete_webhook, add_bot, \
    delete_bot, \
    update_attachment_name, can_upload, discord_settings_start, reset_discord_settings, list_active_devices, revoke_device, logout_all_devices

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
    path("files/<signed_file_id>/preview/stream", ["GET"], stream_preview, name="stream_preview"),
    path("files/<signed_file_id>/moments/<timestamp>/stream", ["GET"], stream_moment, name="stream_moment"),
    path("files/<signed_file_id>/subtitles/<subtitle_id>/stream", ["GET"], stream_subtitle, name="stream_subtitle"),
    path("files/<signed_file_id>/stream", ["GET"], stream_file, name="stream_subtitle"),

    path("files", ["POST"], create_file, name="create file"),
    path("files/<file_id>", ["PATCH"], edit_file, name="edit file"),
    path("files/<file_id>", ["GET"], get_file_info, name="get file info"),
    path("files/<file_id>/thumbnail", ["POST"], create_or_edit_thumbnail, name="create a thumbnail"),
    path("files/<file_id>/video-position", ["PUT"], update_video_position, name="update video position"),

    path("files/<file_id>/tags", ["POST"], add_tag, name="add a tag"),
    path("files/<file_id>/tags", ["GET"], get_tags, name="get file moments"),
    path("files/<file_id>/tags/<tag_id>", ["DELETE"], remove_tag, name="remove a tag"),
    path("files/<file_id>/moments", ["GET"], get_moments, name="add a moment"),
    path("files/<file_id>/moments", ["POST"], add_moment, name="get all moments"),
    path("files/<file_id>/moments/<timestamp>", ["DELETE"], remove_moment, name="remove a moment"),
    path("files/<file_id>/subtitles", ["POST"], add_subtitle, name="add subtitle"),
    path("files/<file_id>/subtitles", ["GET"], get_subtitles, name="get file subtitles"),
    path("files/<file_id>/subtitles/<subtitle_id>", ["DELETE"], remove_subtitle, name="remove subtitle"),
    path('files/<file_id>/changecrc', ['PATCH'], change_crc, name='change crc'),

    path("folders", ["POST"], create_folder, name="create folder"),
    path('folders/<folder_id>', ["GET"], get_folder_info, name="get files and folders from a folder id"),
    path('folders/<folder_id>/dirs', ["GET"], get_dirs, name="get folders from a folder id"),
    path('folders/<folder_id>/usage', ["GET"], get_usage, name="get size of all files in that folder to all user's files"),
    path("folders/<folder_id>/breadcrumbs", ["GET"], get_breadcrumbs, name="get folder's breadcrumbs"),
    path("folders/<folder_id>/password", ["POST"], change_folder_password, name="change folder password"),
    path("folders/<folder_id>/password/reset", ["POST"], reset_folder_password, name="create folder"),
    path("folders/<folder_id>/stats", ['GET'], get_file_stats, name="get file stats for folder"),

    path("items/move", ["PATCH"], move, name="bulk move items"),
    path("items/moveToTrash", ["PATCH"], move_to_trash, name="bulk move items to trash"),
    path("items/restoreFromTrash", ["PATCH"], restore_from_trash, name="move items to trash"),
    path("items/delete", ["POST"], delete, name="bulk delete items"),
    path("items/zip", ["POST"], create_zip_model, name="create zip model"),

    path('zip/<token>', ['GET'], stream_zip_files),

    path("items/<item_id>/moreinfo", ["GET"], fetch_additional_info, name="fetch more info about an item"),
    path("items/<item_id>/rename", ["PATCH"], rename, name="rename an item"),
    path("items/<item_id>/password", ['GET'], check_password, name="check password"),

    django_path("auth/token/login", login_per_device, name="login"),
    django_path("auth/token/logout", logout_per_device, name="logout"),
    django_path("auth/register", register_user, name="register"),
    django_path('auth/qrcode', get_qr_session, name='get qr code session'),
    django_path('auth/qrcode/<session_id>', authenticate_qr_session, name='authenticate a qr session'),
    django_path('auth/qrcode/get/<session_id>', get_qr_session_device_info, name='get new device info by session id'), #todo
    django_path('auth/qrcode/cancel/<session_id>', cancel_pending_qr_session, name='cancel new device pending session'),

    path('user/me', ['GET'], users_me, name="get current user"),
    path('user/canUpload/<folder_id>', ['GET'], can_upload, name="check if user is allowed to upload"),
    path("user/password", ['PATCH'], change_password, name="change password"),
    path("user/settings", ['PUT'], update_settings, name="update settings"),

    path("user/devices", ['GET'], list_active_devices, name="list active devices"),
    path("user/devices/logout-all", ['POST'], logout_all_devices, name="logouts all devices"),
    path("user/devices/<device_id>", ['DELETE'], revoke_device, name="revoke a device"),

    path("user/discordSettings", ['GET'], get_discord_settings, name="get discord settings"),
    path("user/discordSettings", ['PATCH'], update_attachment_name, name="update upload destination"),
    path("user/discordSettings", ['DELETE'], reset_discord_settings, name="reset discord settings"),
    path("user/discordSettings/autoSetup", ['POST'], discord_settings_start, name="do auto setup"),
    path("user/discordSettings/webhooks", ['POST'], add_webhook, name="add a webhook"),
    path("user/discordSettings/webhooks/<webhook_id>", ['DELETE'], delete_webhook, name="delete a webhook"),
    path("user/discordSettings/bots", ['POST'], add_bot, name="add a bot"),
    path("user/discordSettings/bots/<bot_id>", ['DELETE'], delete_bot, name="delete a bot"),

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
    path("shares/<token>/files/<signed_file_id>/preview/stream", ['GET'], share_view_preview, name="view share file preview"),
    path("shares/<token>/files/<signed_file_id>/subtitles/<subtitle_id>/stream", ['GET'], share_view_subtitle, name="view share file subtitle"),
    path("shares/<token>/password", ['GET'], check_share_password, name="check share password"),

    django_path('admin', admin.site.urls),
    django_path('test', get_discord_state),

    path('ip', ['POST'], your_ip, name='get ip'),
    path('ip', ['GET'], your_ip, name='get ip'),

    path("items/ultraDownload", ['POST'], ultra_download_metadata, name="download metadata for ultra download"),
    path("items/ultraDownload/<attachment_id>", ['GET'], get_attachment_url_view, name="download metadata for ultra download"),
    path("cleanup/<attachment_id>", ['GET'], check_attachment_id, name="check if attachment id is used"),

    re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
    # 75 endpoints
]
# urlpatterns += [path('silk/', include('silk.urls', namespace='silk'))]
