from typing import Union, TypedDict

from website.models import Folder, File

Item = Union[Folder, File]


class ResponseDict(TypedDict):
    message: str
    task_id: str


class ErrorDict(TypedDict):
    code: int
    error: str
    details: str
