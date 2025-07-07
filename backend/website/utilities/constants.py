import os
from enum import Enum

from django.core.cache import caches

API_BASE_URL = os.environ["BACKEND_BASE_URL"]

DISCORD_BASE_URL = "https://discord.com/api/v10"

# Max size of 1 message in discord, aka sum of all attachment sizes in bytes: < 10Mb
MAX_DISCORD_MESSAGE_SIZE = 10 * 1023 * 1024

# Max size of a file that we allow to be previewable in bytes: 50Mb
MAX_SIZE_OF_PREVIEWABLE_FILE = 50 * 1024 * 1024

# Max age of media cache in seconds: 1 month
MAX_MEDIA_CACHE_AGE = 2628000

# Discord message cache expiry in seconds: 1 day
DISCORD_MESSAGE_EXPIRY = 79200

MAX_RESOURCE_NAME_LENGTH = 75

SIGNED_URL_EXPIRY_SECONDS = 7200

ALLOWED_THUMBNAIL_SIZES = {"64", "128", "512", "1024", "original"}

cache = caches["default"]

RAW_IMAGE_EXTENSIONS = ('.IIQ', '.3FR', '.DCR', '.K25', '.KDC', '.CRW', '.CR2', '.CR3', '.ERF', '.MEF', '.MOS', '.NEF', '.NRW', '.ORF', '.PEF', '.RW2', '.ARW', '.SRF', '.SR2')
VIDEO_EXTENSIONS = (".mp4", ".avi", ".mkv", ".mov", ".wmv", ".m4v", ".webm", ".ts", ".ogv")
AUDIO_EXTENSIONS = (".mp3", ".wav", ".flac", ".aac")
TEXT_EXTENSIONS = (".txt", '.text')
DOCUMENT_EXTENSIONS = (".doc", ".docx", ".odt", ".xls", ".xlsx", ".ods", ".ppt", ".pptx", ".odp", ".pdf")
EBOOK_EXTENSIONS = (".epub", ".mobi", ".azw", ".fb2")
SYSTEM_EXTENSIONS = (".dll", ".sys", ".ini", ".log", ".cfg", "sqlite", "sqlite3")
DATABASE_EXTENSIONS = (".sql", ".db", ".sqlite", ".mdb", ".accdb")
ARCHIVE_EXTENSIONS = (".zip", ".rar", ".7z", ".tar", ".gz", ".bz2")
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp")
EXECUTABLE_EXTENSIONS = (".exe", ".msi", ".apk", ".bat", ".sh", ".bin", ".ps1")
CODE_EXTENSIONS = (
    ".py", ".js", ".ts", ".java", ".cpp", ".c", ".cs", ".rb", ".php", ".html", ".css", ".xml", ".json", ".yaml", ".yml", ".go", ".rs", ".tsconfig", ".babelrc",
    ".eslintrc", ".prettierrc", ".editorconfig", ".md", ".gitignore", ".vue", ".scss", ".swift", ".zig", ".dart", ".kts", ".kt", ".lua", ".conf", ".srs", ".vtt",
    ".sql", ".svg"
)

FILE_TYPE_CHOICES = [
    ("Video", "Video"),
    ("Audio", "Audio"),
    ("Text", "Text"),
    ("Document", "Document"),
    ("Ebook", "Ebook"),
    ("System", "System"),
    ("Database", "Database"),
    ("Archive", "Archive"),
    ("Image", "Image"),
    ("Executable", "Executable"),
    ("Code", "Code"),
    ("Raw image", "Raw image"),
    ("Other", "Other"),
]

class EventCode(Enum):
    ITEM_CREATE = 1
    ITEM_DELETE = 2
    ITEM_UPDATE = 3
    ITEM_MOVE_OUT = 4
    ITEM_MOVE_IN = 5
    ITEM_MOVE_TO_TRASH = 6
    ITEM_RESTORE_FROM_TRASH = 7

    MESSAGE_UPDATE = 8
    MESSAGE_SENT = 9
    FOLDER_LOCK_STATUS_CHANGE = 10
    FORCE_LOGOUT = 11

class EncryptionMethod(Enum):
    Not_Encrypted = 0
    AES_CTR = 1
    CHA_CHA_20 = 2


class AuditAction(Enum):
    USER_LOGGED_IN = 1
    USER_LOGGED_OUT = 2
    USER_LOGIN_FAILED = 3
