from typing import Optional

from django.contrib.auth.models import User
from pydantic import BaseModel


class RequestContext:
    def __init__(self, user_id: str, device_id: Optional[str], request_id: int):
        self.user_id = user_id
        self.device_id = device_id
        self.request_id = request_id

    def get_user(self) -> Optional[User]:
        return User.objects.get(id=self.user_id) if self.user_id else None

    def __json__(self):
        return {"user_id": self.user_id, "request_id": self.request_id, "device_id": self.device_id}

    @classmethod
    def from_user(cls, user_id: str) -> 'RequestContext':
        return cls(user_id, None, 0)

    @classmethod
    def deserialize(cls, context_json: dict) -> 'RequestContext':
        user_id = context_json['user_id']
        device_id = context_json.get('device_id')
        request_id = context_json.get('request_id', 0)
        return cls(user_id, device_id, request_id)

#TODO, finish this share logging
## SHARE LOGGING
class ViewShare(BaseModel):
    share_id: str

class FileOpenEvent(BaseModel):
    file_id: str

class FileCloseEvent(BaseModel):
    file_id: str

class FileDownloadStartEvent(BaseModel):
    file_id: str

class FileDownloadSuccessfulEvent(BaseModel):
    file_id: str

class FileStreamEvent(BaseModel):
    file_id: str
    from_byte: int
    to_byte: Optional[int]

class FolderOpenEvent(BaseModel):
    folder_id: str

class FolderCloseEvent(BaseModel):
    folder_id: str

class MovieWatchEvent(BaseModel):
    file_id: str
    from_second: int
    to_second: int

class MovieSeekEvent(BaseModel):
    file_id: str
    from_second: int
    to_second: int

class MoviePauseEvent(BaseModel):
    file_id: str
    position_second: int

class ZipDownloadStartEvent(BaseModel):
    files: list[str]
    folders: list[str]

class ZipDownloadSuccessfulEvent(BaseModel):
    files: list[str]
    folders: list[str]
