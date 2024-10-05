import os
from enum import Enum

from django.core.cache import caches

API_BASE_URL = os.environ["BACKEND_BASE_URL"]


# Max size of 1 message in discord, aka sum of all attachment sizes in bytes: < 25Mb
MAX_DISCORD_MESSAGE_SIZE = 25 * 1024 * 1023

# Max size of a file that we allow to be previewable in bytes: 100Mbex
MAX_SIZE_OF_PREVIEWABLE_FILE = 100 * 1024 * 1024

# Max age of media cache in seconds: 1 month
MAX_MEDIA_CACHE_AGE = 2628000

# Discord message cache expiry in seconds: 1 day
DISCORD_MESSAGE_EXPIRY = 79200

MAX_RESOURCE_NAME_LENGTH = 75

SIGNED_URL_EXPIRY_SECONDS = 7200

cache = caches["default"]

RAW_IMAGE_EXTENSIONS = ('.IIQ', '.3FR', '.DCR', '.K25', '.KDC', '.CRW', '.CR2', '.CR3', '.ERF', '.MEF', '.MOS', '.NEF', '.NRW', '.ORF', '.PEF', '.RW2', '.ARW', '.SRF', '.SR2')

class EventCode(Enum):
    ITEM_CREATE = 1
    ITEM_DELETE = 2
    ITEM_NAME_CHANGE = 3
    MESSAGE_SENT = 4
    ITEM_MOVED = 5
    ITEM_PREVIEW_INFO_ADD = 6
    FORCE_FOLDER_NAVIGATION = 7
    FOLDER_LOCK_STATUS_CHANGE = 8
    ITEM_MOVE_TO_TRASH = 9
    ITEM_RESTORE_FROM_TRASH = 10
