import json
import threading
import time
import traceback
import uuid
from abc import abstractmethod, ABC
from datetime import timedelta

from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer
from django.core.cache import cache
from django.utils import timezone


class RateLimitedWebsocketConsumer(WebsocketConsumer, ABC):
    max_connections_per_client = 5
    connection_limit = 5        # how many new connections allowed
    connection_window = 30       # seconds

    message_limit = 60          # messages allowed
    message_window = 60          # seconds

    ping_heartbeat = True
    ping_interval = 10  # seconds
    ping_timeout = 5  # seconds

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_pong = time.time()
        self._heartbeat_thread = None
        self._heartbeat_running = None
        self._connection_id = str(uuid.uuid4())

    @abstractmethod
    def authorize(self) -> tuple[bool, bool, str]:
        raise NotImplementedError("authorize() must be implemented in subclass.")

    @abstractmethod
    def get_group_name(self) -> str:
        raise NotImplementedError("get_group_name() must be implemented in subclass.")

    def on_ratelimit(self):
        pass

    def on_exception(self, exception: Exception):
        pass

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
        # self.send_json({"type": "error", "reason": reason})
        self.close(code)
        return

    def connect(self):
        if not self._check_rate_limit("connect", self.connection_limit, self.connection_window):
            self.reject(code=4408, reason="Too many connection attempts")

        if self._count_connections() > self.max_connections_per_client:
            self.reject(4409, "Too many active connections")
            return

        authorized, is_standard_protocol, token = self.authorize()

        if not authorized:
            self.reject(code=4401, reason="Unauthorized")

        if is_standard_protocol:
            self.accept()
        else:
            self.accept(token)

        self._register_connection()

        if self.ping_heartbeat:
            self.last_pong = time.time()
            self._heartbeat_running = True
            self._heartbeat_thread = threading.Thread(
                target=self._heartbeat_loop,
                daemon=True
            )
            self._heartbeat_thread.start()

        async_to_sync(self.channel_layer.group_add)(self.get_group_name(), self.channel_name)

        self.on_accept()

    def disconnect(self, close_code):
        async_to_sync(self.channel_layer.group_discard)(self.get_group_name(), self.channel_name)
        self._unregister_connection()
        self.on_disconnect(close_code)

    def receive(self, text_data=None, bytes_data=None):
        """DO NOT OVERRIDE THIS FUNCTION TO HANDLE MESSAGES.
        USE on_message() INSTEAD!"""

        # 0) Ensure client is still authorized
        authorized, _, _ = self.authorize()
        if not authorized:
            self.close()

        # 1) Rate-limit per-message
        if not self._check_rate_limit("msg", self.message_limit, self.message_window):
            self.on_ratelimit()
            return

        # 2) Handle heartbeat (application pong)
        if self.ping_heartbeat and text_data == "PONG":
            self._refresh_connection()
            self.last_pong = time.time()
            return

        # 3) Pass to subclass handler
        try:
            self.on_message(text_data, bytes_data)
        except Exception as e:
            traceback.print_exc()
            self.on_exception(e)

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

    def _heartbeat_loop(self):
        while self._heartbeat_running:
            time.sleep(10)

            async_to_sync(self.channel_layer.send)(
                self.channel_name,
                {
                    "type": "heartbeat_ping",
                }
            )

            if time.time() - self.last_pong > self.ping_interval + self.ping_timeout:
                async_to_sync(self.channel_layer.send)(
                    self.channel_name,
                    {
                        "type": "heartbeat_close",
                    }
                )
                break

    def heartbeat_ping(self, event):
        self.send("PING")

    def heartbeat_close(self, event):
        self.close()

    def _count_connections(self) -> int:
        ident = self.get_rate_limit_id()
        cache = self.get_cache()
        pattern = f"ws-active:{ident}:*"

        keys = cache.keys(pattern)
        return len(keys)

    def _register_connection(self) -> None:
        cache = self.get_cache()
        ident = self.get_rate_limit_id()

        ttl = self.ping_interval + self.ping_timeout

        key = f"ws-active:{ident}:{self._connection_id}"
        cache.set(key, 1, timeout=ttl)

    def _refresh_connection(self) -> None:
        cache = self.get_cache()
        ident = self.get_rate_limit_id()

        ttl = self.ping_interval + self.ping_timeout

        key = f"ws-active:{ident}:{self._connection_id}"
        cache.set(key, 1, timeout=ttl)

    def _unregister_connection(self) -> None:
        cache = self.get_cache()
        ident = self.get_rate_limit_id()

        key = f"ws-active:{ident}:{self._connection_id}"
        cache.delete(key)