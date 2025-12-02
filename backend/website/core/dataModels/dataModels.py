from typing import Optional

from pydantic import BaseModel


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
