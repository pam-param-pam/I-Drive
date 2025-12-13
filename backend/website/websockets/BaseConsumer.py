import json
import traceback
from abc import abstractmethod, ABC
from datetime import timedelta

from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer
from django.core.cache import cache
from django.utils import timezone

from ..constants import EventCode


class RateLimitedWebsocketConsumer(WebsocketConsumer, ABC):
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
            self.reject(code=4408, reason="Too many connection attempts")

        authorized, is_standard_protocol, token = self.authorize()

        if not authorized:
            self.reject(code=4401, reason="Unauthorized")

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
        except Exception as e:
            traceback.print_exc()
            if not self.on_error(e):
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

    def on_error(self, exception: Exception) -> bool:
        return False
