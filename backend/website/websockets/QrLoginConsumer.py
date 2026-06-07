import json
import threading

from website.constants import cache, QR_CODE_SESSION_EXPIRY
from website.services import cache_service
from website.websockets.BaseConsumer import RateLimitedWebsocketConsumer


class QrLoginConsumer(RateLimitedWebsocketConsumer):
    message_limit = 5
    message_window = 60

    connection_limit = 15
    connection_window = 30
    ping_heartbeat = False

    def __init__(self):
        super().__init__()
        self.close_timer = None
        self.session_id = None
        self._closed = False
        self._close_lock = threading.Lock()

    def get_group_name(self) -> str:
        return "qrcode"

    def safe_close(self, code=4000):
        with self._close_lock:
            if self._closed:
                return
            self._closed = True

            if self.close_timer:
                self.close_timer.cancel()
                self.close_timer = None

        self.close(code=code)

    def on_disconnect(self, close_code):
        with self._close_lock:
            self._closed = True

            if self.close_timer:
                self.close_timer.cancel()
                self.close_timer = None

    def authorize(self) -> tuple[bool, bool, str]:
        session_id, is_standard_protocol = self.get_token_key()
        self.session_id = session_id

        if session_id:
            session_key = cache_service.get_qr_session_key(session_id)
            session_json = cache.get(session_key)

            if session_json:
                self.close_timer = threading.Timer(QR_CODE_SESSION_EXPIRY + 5, lambda: self.safe_close())
                self.close_timer.daemon = True
                self.close_timer.start()
                return True, is_standard_protocol, session_id

        return False, is_standard_protocol, session_id

    def approve_session(self, event):
        if event["session_id"] == self.session_id:
            event["message"]["opcode"] = 2
            self.send(text_data=json.dumps(event["message"]))
            self.safe_close()

    def pending_session(self, event):
        if event["session_id"] == self.session_id:
            self.send(text_data=json.dumps({"opcode": 1, "user": event["username"]}))

    def cancel_pending_session(self, event):
        if event["session_id"] == self.session_id:
            self.send(text_data=json.dumps({"opcode": 3}))
            self.safe_close()
