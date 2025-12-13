from typing import Optional

from ..models import ShareableLink
from ..websockets.BaseConsumer import RateLimitedWebsocketConsumer


class ShareConsumer(RateLimitedWebsocketConsumer):
    message_limit = 5
    message_window = 60

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

