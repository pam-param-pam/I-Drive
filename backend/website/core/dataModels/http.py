from typing import Optional

from django.contrib.auth.models import User


class RequestContext:
    def __init__(self, user_id: int, device_id: Optional[str], request_id: int):
        self.user_id = user_id
        self.device_id = device_id
        self.request_id = request_id

    def get_user(self) -> Optional[User]:
        return User.objects.get(id=self.user_id) if self.user_id else None

    def __json__(self):
        return {"user_id": self.user_id, "request_id": self.request_id, "device_id": self.device_id}

    @classmethod
    def from_user(cls, user_id: int) -> 'RequestContext':
        return cls(user_id, None, 0)

    @classmethod
    def deserialize(cls, context_json: dict) -> 'RequestContext':
        user_id = context_json['user_id']
        device_id = context_json.get('device_id')
        request_id = context_json.get('request_id', 0)
        return cls(user_id, device_id, request_id)
