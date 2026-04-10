import json
from typing import Optional

from .BaseConsumer import RateLimitedWebsocketConsumer
from ..constants import EventCode
from ..core.dataModels.http import RequestContext
from ..core.dataModels.websocket import WebsocketEvent, WebsocketLogoutEvent
from ..models import PerDeviceToken


class UserConsumer(RateLimitedWebsocketConsumer):
    connection_limit = 10        # how many new connections allowed

    message_limit = 10
    message_window = 30

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
        self.token = token_key
        self.device_id = self.token_obj.device_id
        return token.user.is_authenticated, is_standard_protocol, token_key

    def send_error(self, error_code):
        self.send_json({'is_encrypted': False, 'event': {'op_code': EventCode.WEBSOCKET_ERROR.value, 'data': [{'error_code': f"errors.{error_code}"}]}})

    def on_ratelimit(self):
        self.send_error("rate_limit_exceeded")

    def send_event(self, event: WebsocketEvent):
        if self.user.id == event['context']['user_id'] and (self.device_id == event['context'].get('device_id') or not event['context'].get('device_id')):
            self.send(json.dumps(event['ws_payload']))

    def logout(self, event: WebsocketLogoutEvent):
        if self.user.id == event['context']['user_id']:
            if event['device_id']:  # specific connection to close
                if self.device_id == event['device_id']:
                    self.close()
            else:  # close all connections
                self.close()

    def get_context(self, device_id: str) -> RequestContext:
        context = RequestContext.from_user(self.user.id)
        context.device_id = device_id
        return context
