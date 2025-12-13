import json
import threading

from .BaseConsumer import RateLimitedWebsocketConsumer
from ..constants import QR_CODE_SESSION_EXPIRY, cache


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
