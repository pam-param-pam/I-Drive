import hashlib
import json
import threading
import traceback
from abc import abstractmethod
from datetime import timedelta
from typing import Optional

from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer
from django.core.cache import cache
from django.utils import timezone

from .constants import EventCode, QR_CODE_SESSION_EXPIRY
from .core.dataModels.http import RequestContext
from .core.dataModels.websocket import WebsocketEvent, WebsocketLogoutEvent
from .core.deviceControl.DeviceControlState import DeviceControlState
from .core.errors import DeviceControlBadStateError
from .core.websocket.utils import send_event
from .models import PerDeviceToken
from .tasks.otherTasks import send_message
from .core.Serializers import DeviceTokenSerializer


class RateLimitedWebsocketConsumer(WebsocketConsumer):
    connection_limit = 5        # how many new connections allowed
    connection_window = 30       # seconds

    message_limit = 60          # messages allowed
    message_window = 60          # seconds

    @abstractmethod
    def authorize(self) -> tuple[bool, bool, str]:
        raise NotImplementedError("authorize() must be implemented in subclass.")

    @abstractmethod
    def get_group_name(self) -> str:
        raise NotImplementedError("get_group_name() must be implemented in subclass.")

    def on_message(self, text_data, bytes_data):
        pass

    def on_disconnect(self, close_code):
        pass

    def on_accept(self):
        pass

    def get_cache(self):
        return cache

    def get_rate_limit_id(self) -> str:
        return self.scope["client"][0]

    def _check_rate_limit(self, key_prefix, limit, window_seconds):
        cache = self.get_cache()
        ident = self.get_rate_limit_id()
        key = f"ws-{key_prefix}-{ident}"

        entry = cache.get(key, {"count": 0, "timestamp": timezone.now()})

        now = timezone.now()

        # reset window if expired
        if now - entry["timestamp"] > timedelta(seconds=window_seconds):
            entry = {"count": 0, "timestamp": now}

        entry["count"] += 1
        cache.set(key, entry, window_seconds)

        return entry["count"] <= limit

    def reject(self, code, reason):
        self.close(code)
        return

    def connect(self):
        if not self._check_rate_limit("connect", self.connection_limit, self.connection_window):
            return self.reject(code=4408, reason="Too many connection attempts")

        authorized, is_standard_protocol, token = self.authorize()

        if authorized is False:
            return self.reject(code=4401, reason="Unauthorized")

        if is_standard_protocol:
            self.accept()
        else:
            self.accept(token)
        async_to_sync(self.channel_layer.group_add)(self.get_group_name(), self.channel_name)
        self.on_accept()

    def disconnect(self, close_code):
        async_to_sync(self.channel_layer.group_discard)(self.get_group_name(), self.channel_name)
        self.on_disconnect(close_code)

    def send_error(self, error_code):
        self.send_json({'is_encrypted': False, 'event': {'op_code': EventCode.WEBSOCKET_ERROR.value, 'data': [{'error_code': error_code}]}})

    def receive(self, text_data=None, bytes_data=None):
        """DO NOT OVERRIDE THIS FUNCTION TO HANDLE MESSAGES.
        USE on_message() INSTEAD!"""
        # 1) Rate-limit per-message
        if not self._check_rate_limit("msg", self.message_limit, self.message_window):
            self.send_error('rate_limit_exceeded')
            return

        # 2) Pass to subclass handler
        try:
            self.on_message(text_data, bytes_data)
        except Exception:
            traceback.print_exc()
            self.send_error('internal_websocket_error')

    def send_json(self, data: dict):
        self.send(json.dumps(data))

    def get_token_key(self) -> tuple[str, bool]:
        headers = dict(self.scope.get("headers", []))
        token_key = None
        is_standard_protocol = False

        # Try Authorization: Bearer <token>
        auth_header = headers.get(b'authorization')
        if auth_header:
            try:
                auth_str = auth_header.decode('utf-8')
                if auth_str.lower().startswith('bearer '):
                    token_key = auth_str[7:].strip()
                    is_standard_protocol = True
            except Exception:
                pass

        # Fallback to Sec-WebSocket-Protocol
        if token_key is None:
            try:
                token_key = headers[b'sec-websocket-protocol'].decode('utf-8').strip()
                is_standard_protocol = False
            except Exception:
                token_key = None

        return token_key, is_standard_protocol


class UserConsumer(RateLimitedWebsocketConsumer):
    connection_limit = 15        # how many new connections allowed

    message_limit = 101  # todo
    message_window = 60

    def __init__(self, *args, **kwargs):
        super().__init__(args, kwargs)
        self.token_obj = None
        self.device_id = None
        self.user = None
        self.token = None

    def get_token(self, raw_token) -> Optional[PerDeviceToken]:
        if not raw_token:
            return None

        token = PerDeviceToken.objects.get_token_from_raw_token(raw_token=raw_token)
        return token

    def get_group_name(self) -> str:
        return "user"

    def authorize(self) -> tuple[bool, bool, str]:
        token_key, is_standard_protocol = self.get_token_key()

        token = self.get_token(token_key)
        if not token:
            return False, is_standard_protocol, token_key

        self.user = token.user
        self.token_obj = token
        self.device_id = self.token_obj.device_id
        return token.user.is_authenticated, is_standard_protocol, token_key

    def on_message(self, text_data=None, bytes_data=None):
        json_data = json.loads(text_data)
        op_code = json_data.get('op_code')

        if op_code == EventCode.DEVICE_CONTROL_REQUEST.value:
            self.handle_device_control_request(json_data)

        elif op_code == EventCode.DEVICE_CONTROL_STATUS.value:
            self.send_device_control_status()

        elif op_code == EventCode.DEVICE_CONTROL_REPLY.value:
            self.handle_device_control_reply(json_data)

        elif op_code == EventCode.DEVICE_CONTROL_COMMAND.value:
            self.handle_device_control_command(json_data)

    def on_accept(self):
        master_device_id = DeviceControlState.slave_has_pending(self.device_id)
        if master_device_id:
            self.send_device_control_pending(self.device_id)

        self.send_device_control_status()

    def send_event(self, event: WebsocketEvent):
        if self.user.id == event['context']['user_id'] and (not self.device_id or not event['context'].get('device_id') or self.device_id == event['context'].get('device_id')):
            self.send(json.dumps(event['ws_payload']))

    def logout(self, event: WebsocketLogoutEvent):
        if self.user.id == event['context']['user_id']:
            if event['token_hash']:  # specific connection to close
                token_hash = hashlib.sha256(self.token.encode()).hexdigest()
                if token_hash == event['token_hash']:
                    self.close()
            else:  # close all connections
                self.close()

    def get_context(self, device_id: str) -> RequestContext:
        context = RequestContext.from_user(self.user.id)
        context.device_id = device_id
        return context

    def handle_device_control_request(self, json_data: dict) -> None:
        slave_device_id = json_data['message']['device_id']
        DeviceControlState.create_pending(master_id=self.device_id, slave_id=slave_device_id)
        self.send_device_control_status(device_id=self.device_id)
        self.send_device_control_pending(slave_device_id)

    def handle_device_control_command(self, json_data: dict) -> None:
        if not DeviceControlState.master_has_active(master_id=self.device_id):
            raise DeviceControlBadStateError("not_active_master")

        slave_id = DeviceControlState.get_active_slave_for_master(master_id=self.device_id)

        context = self.get_context(slave_id)
        send_event(context, None, EventCode.DEVICE_CONTROL_COMMAND, json_data['message'])

    def send_device_control_pending(self, slave_device_id: str) -> None:
        """Sends a pending request from this device(master) to slave device"""
        context = self.get_context(slave_device_id)
        device = DeviceTokenSerializer().serialize_object(self.token_obj)
        expiry = DeviceControlState.get_status(slave_device_id)["expiry"]
        send_event(context, None, EventCode.DEVICE_CONTROL_REQUEST, {"master_device": device, "expiry": expiry})

    def send_device_control_status(self, device_id=None) -> None:
        """Sends current device control status to this device"""
        if not device_id:
            device_id = self.device_id
        context = self.get_context(device_id)
        send_event(context, None, EventCode.DEVICE_CONTROL_STATUS, DeviceControlState.get_status(device_id))

    def handle_device_control_reply(self, json_data: dict) -> None:
        device_id = self.device_id
        reply_type = json_data["message"]["type"]

        pending_master = DeviceControlState.master_has_pending(device_id)
        pending_slave = DeviceControlState.slave_has_pending(device_id)

        active_master = DeviceControlState.master_has_active(device_id)
        active_slave = DeviceControlState.slave_has_active(device_id)
        peer = DeviceControlState.get_status(device_id=self.device_id)["peer"]

        # --- 1) REJECT (slave rejects pending request) ---
        if reply_type == "reject" and pending_slave:
            DeviceControlState.reject_pending(master_id=pending_slave, slave_id=device_id)

        # --- 2) APPROVE (slave approves pending request) ---
        elif reply_type == "approve":
            if pending_slave:
                DeviceControlState.approve_pending(master_id=pending_slave, slave_id=device_id)
            else:
                send_message(message="toasts.deviceControlApprovedFailed", args=None, finished=True, context=self.get_context(device_id), isError=True)

        # --- 3) CANCEL (master cancels pending) ---
        elif reply_type == "cancel":
            if pending_master:
                DeviceControlState.clear_pending(master_id=device_id, slave_id=pending_master)

        # --- 4) CLEAR (end active session) ---
        elif reply_type == "clear":
            # End active session regardless of direction
            if active_master:
                DeviceControlState.clear_active(master_id=device_id, slave_id=active_master)

            if active_slave:
                DeviceControlState.clear_active(master_id=active_slave, slave_id=device_id)

        # send current status to both
        self.send_device_control_status(device_id=device_id)
        self.send_device_control_status(device_id=peer)


class QrLoginConsumer(RateLimitedWebsocketConsumer):
    message_limit = 5
    message_window = 60

    def __init__(self, *args, **kwargs):
        super().__init__(args, kwargs)
        self.close_timer = None
        self.session_id = None

    def get_group_name(self) -> str:
        return "qrcode"

    def authorize(self) -> tuple[bool, bool, str]:
        session_id, is_standard_protocol = self.get_token_key()
        self.session_id = session_id

        if session_id:
            session_key = f"qr_session:{session_id}"
            session_json = cache.get(session_key)
            if session_json:
                self.close_timer = threading.Timer(QR_CODE_SESSION_EXPIRY + 5, lambda: self.close(code=4000))
                self.close_timer.start()
                return True, is_standard_protocol, session_id

        return False, is_standard_protocol, session_id

    def approve_session(self, event):
        if event['session_id'] == self.session_id:
            event['message']['opcode'] = 2
            self.send(text_data=json.dumps(event['message']))
            self.close(code=4000)

    def pending_session(self, event):
        if event['session_id'] == self.session_id:
            self.send(text_data=json.dumps({'opcode': 1, "user": event['username']}))

    def cancel_pending_session(self, event):
        if event['session_id'] == self.session_id:
            self.send(text_data=json.dumps({'opcode': 3}))
