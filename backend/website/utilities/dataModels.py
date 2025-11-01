from typing import Optional

from django.contrib.auth.models import User


class RequestContext:
    def __init__(self, user_id: str, device_id: str, request_id: int):
        self.user_id = user_id
        self.request_id = request_id
        self.device_id = device_id

    def get_user(self) -> Optional[User]:
        return User.objects.get(id=self.user_id) if self.user_id else None

    def __json__(self):
        return {"user_id": self.user_id, "request_id": self.request_id, "device_id": self.device_id}

    @classmethod
    def from_user(cls, user_id: str) -> 'RequestContext':
        return cls(user_id, None, 0)
