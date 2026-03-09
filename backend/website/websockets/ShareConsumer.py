import json
from typing import Optional

from ..constants import ShareEventType
from ..models import ShareableLink
from ..services import share_service
from ..websockets.BaseConsumer import RateLimitedWebsocketConsumer


class ShareConsumer(RateLimitedWebsocketConsumer):
    message_limit = 60
    message_window = 60
    ping_heartbeat = False

    def __init__(self):
        super().__init__()
        self.share = None

    def get_share(self, token) -> Optional[ShareableLink]:
        if not token:
            return None

        qs = ShareableLink.objects.filter(token=token)
        if not qs.exists():
            return None
        return qs[0]

    def get_group_name(self) -> str:
        return "share"

    def authorize(self) -> tuple[bool, bool, str]:
        token_key, is_standard_protocol = self.get_token_key()

        share = self.get_share(token_key)
        if not share:
            return False, is_standard_protocol, token_key

        self.share = share
        return True, is_standard_protocol, token_key

    def on_ratelimit(self):
        print("rate limit")

    def on_message(self, text_data, bytes_data):
        json_data = json.loads(text_data)
        event_type = json_data['type']
        args = json_data['args']

        if event_type == ShareEventType.FILE_OPEN.value:
            share_service.log_event_websocket(self.scope, self.share, ShareEventType.FILE_OPEN, **args)
        elif event_type == ShareEventType.MOVIE_WATCH.value:
            share_service.log_event_websocket(self.scope, self.share, ShareEventType.MOVIE_WATCH, **args)
        elif event_type == ShareEventType.MOVIE_TOGGLE.value:
            share_service.log_event_websocket(self.scope, self.share, ShareEventType.MOVIE_TOGGLE, **args)
        elif event_type == ShareEventType.MOVIE_SEEK.value:
            share_service.log_event_websocket(self.scope, self.share, ShareEventType.MOVIE_SEEK, **args)

        else:
            print("NOT FOUND")
            print(event_type)
            print(args)