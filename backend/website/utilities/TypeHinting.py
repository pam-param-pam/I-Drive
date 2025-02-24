from typing import Union, TypedDict, Optional, List, Any

from django.db.models import PositiveBigIntegerField
from shortuuidfield import ShortUUIDField

from ..models import Folder, File
from typing_extensions import NotRequired

Resource = Union[Folder, File]


class Breadcrumbs(TypedDict):
    name: str
    id: ShortUUIDField

class FileDict(TypedDict):
    isDir: bool
    id: ShortUUIDField
    name: str
    parent_id: Union[ShortUUIDField, None]
    extension: str
    size: PositiveBigIntegerField
    type: str
    created: str
    last_modified: str
    isLocked: bool
    encryption_method: int
    lockFrom: Optional[ShortUUIDField]
    in_trash_since: Optional[str]
    iso: Optional[str]
    model_name: Optional[str]
    aperture: Optional[str]
    exposure_time: Optional[str]
    focal_length: Optional[str]
    preview_url: Optional[str]
    download_url: Optional[str]
    thumbnail_url: Optional[str]


class FolderDict(TypedDict):
    isDir: bool
    id: ShortUUIDField
    name: str
    parent_id: Union[ShortUUIDField, None, Any]
    created: str
    last_modified: str
    isLocked: bool
    lockFrom: Optional[ShortUUIDField]
    in_trash_since: str
    children: NotRequired[List[Union['FolderDict', FileDict]]]


class PartialFragmentDict(TypedDict):
    sequence: int
    size: int


class ZipFileDict(TypedDict):
    name: str
    isDir: bool
    fileObj: File


class ShareDict(TypedDict):
    expire: str
    name: str
    isDir: bool
    token: str
    resource_id: str
    id: ShortUUIDField


class ResponseDict(TypedDict):
    message: str
    task_id: str


class ErrorDict(TypedDict):
    code: int
    error: str
    details: str
