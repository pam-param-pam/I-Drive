import datetime
import json
import time
import uuid

from django.contrib.auth import authenticate
from django.contrib.auth import user_logged_in, user_logged_out
from django.contrib.auth.models import User
from django.db import transaction

from ..constants import TOKEN_EXPIRY_DAYS, QR_CODE_SESSION_EXPIRY, cache, EventCode
from ..core.Serializers import DeviceTokenSerializer
from ..core.dataModels.http import RequestContext
from ..core.deviceControl.DeviceControlState import DeviceControlState
from ..core.errors import BadRequestError, UsernameTakenError, ResourceNotFoundError, ResourcePermissionError
from ..core.helpers import get_ip
from ..core.http.utils import get_device_metadata
from ..models import PerDeviceToken, UserPerms, UserSettings, Folder, DiscordSettings
from ..tasks.queueTasks import queue_ws_event
from ..websockets.utils import send_event


def _create_token_internal(user: User, device_info: dict) -> tuple[str, PerDeviceToken]:
    raw_token, token_instance = PerDeviceToken.objects.create_token(
        user=user,
        device_name=device_info["device_name"],
        device_id=device_info["device_id"],
        expires=datetime.timedelta(days=TOKEN_EXPIRY_DAYS),
        ip_address=device_info["ip"],
        user_agent=device_info["user_agent"],
        country=device_info["country"],
        city=device_info["city"],
        device_type=device_info["device_type"]
    )

    return raw_token, token_instance


def _create_token(request, user: User) -> tuple[str, PerDeviceToken]:
    """Injects device metadata and creates a new token for it"""
    metadata = get_device_metadata(request)
    return _create_token_internal(user, metadata)


def authenticate_qr_session(user: User, session_id) -> None:
    key = f"qr_session:{session_id}"
    session_json = cache.get(key)

    if not session_json:
        raise ResourceNotFoundError("Invalid or expired session")

    session_data = json.loads(session_json)

    desktop_user = user
    raw_token, token_obj = _create_token_internal(desktop_user, session_data)

    cache.delete(key)

    auth_data = {"auth_token": raw_token, "device_id": token_obj.device_id}

    queue_ws_event.delay(
        'qrcode',
        {
            'type': 'approve_session',
            'session_id': session_id,
            'message': auth_data
        }
    )

def cancel_pending_qr_session(session_id: str) -> None:
    key = f"qr_session:{session_id}"
    session_json = cache.get(key)

    if not session_json:
        raise ResourceNotFoundError("Invalid or expired session")

    queue_ws_event.delay(
        'qrcode',
        {
            'type': 'cancel_pending_session',
            'session_id': session_id,
        }
    )

def get_qr_session_device_info(user: User, session_id: str) -> dict:
    key = f"qr_session:{session_id}"
    session_json = cache.get(key)

    if not session_json:
        raise ResourceNotFoundError("Invalid or expired session")

    session_data = json.loads(session_json)

    # send info that the session is now in pending state
    queue_ws_event.delay(
        'qrcode',
        {
            'type': 'pending_session',
            'session_id': session_id,
            'username': user.username
        }
    )
    return session_data

def create_qr_session(request) -> tuple[str, int]:
    ip, _ = get_ip(request)
    metadata = get_device_metadata(request)

    existing_session_id = cache.get(f"qr_ip:{ip}")
    if existing_session_id:
        cache.delete(f"qr_session:{existing_session_id}")

    # Create new session
    session_id = str(uuid.uuid4())
    expire_at = int(time.time()) + QR_CODE_SESSION_EXPIRY

    session_data = {
        **metadata,
        "authenticated": False,
        "expire_at": expire_at,
        "ip": ip,
    }

    cache.set(f"qr_session:{session_id}", json.dumps(session_data),
              timeout=QR_CODE_SESSION_EXPIRY)

    cache.set(f"qr_ip:{ip}", session_id, timeout=QR_CODE_SESSION_EXPIRY)

    return session_id, expire_at


def _revoke_device(user: User, device_id: str) -> None:
    # prevent races to delete
    with transaction.atomic():
        token = (
            PerDeviceToken.objects
            .select_for_update()
            .filter(user=user, device_id=device_id)
            .first()
        )
        if not token:
            return

        DeviceControlState.clear_all(token.device_id)
        token.delete()


def _logout_websockets(user: User, device_id: str = None) -> None:
    """Sends a closing event on websocket and then closes it. If device_id is None, it closes every websocket for user"""
    context = RequestContext.from_user(user.id)
    send_event(context, None, EventCode.FORCE_LOGOUT, {"device_id": device_id})
    queue_ws_event.delay(
        'user',
        {
            "type": "logout",
            "context": context,
            "device_id": device_id,
        }
    )

def login_device(request, username: str, password: str) -> tuple[str, PerDeviceToken]:
    user = authenticate(request, username=username, password=password)
    if not user:
        raise BadRequestError('Invalid credentials')

    raw_token, token_obj = _create_token(request, user)

    user_logged_in.send(sender=user.__class__, request=request, user=user)
    send_event(RequestContext.from_user(user.id), None, EventCode.NEW_DEVICE_LOG_IN, DeviceTokenSerializer().serialize_object(token_obj))

    return raw_token, token_obj

def logout_all_devices_for_user(request, user) -> None:
    for device in PerDeviceToken.objects.filter(user=user):
        logout_device(request, user, device.device_id)

def logout_device(request, user: User, device_id: str) -> None:
    _logout_websockets(user=user, device_id=device_id)
    _revoke_device(user, device_id)
    user_logged_out.send(sender=user.__class__, request=request, user=user)


def register_user(request, username: str, password: str) -> tuple[str, PerDeviceToken]:
    if User.objects.filter(username=username):
        raise UsernameTakenError()

    create_new_user(username, password, is_staff=False)
    return login_device(request, username, password)

def change_password(request, user: User, current_password: str, new_password: str) -> tuple[str, PerDeviceToken]:
    if not user.check_password(current_password):
        raise ResourcePermissionError("Password is incorrect!")

    user.set_password(new_password)
    user.save()

    logout_all_devices_for_user(request, user)
    raw_token, token_obj = login_device(request, user.username, new_password)
    return raw_token, token_obj


def create_new_user(username: str, password: str, is_staff: bool):
    with transaction.atomic():
        user = User.objects.create_user(username=username, password=password, is_staff=is_staff)
        UserPerms._create_user_perms(user=user)
        UserSettings._create_user_settings(user=user)
        Folder._create_user_root(user=user)
        DiscordSettings._create_user_discord_settings(user=user)
