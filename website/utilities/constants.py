# Max name length both for files and folders
from enum import Enum

from django.core.cache import caches


GET_BASE_URL = "https://get.pamparampam.dev"
API_BASE_URL = "https://api.pamparampam.dev"
# #
# GET_BASE_URL = "http://localhost:8050"
# API_BASE_URL = "http://localhost:8000"

# Max size of 1 message in discord, aka sum of all attachment sizes in bytes: < 25Mb
MAX_DISCORD_MESSAGE_SIZE = 25 * 1024 * 1023

# Max size of a file that we allow to be previewable in bytes: 100Mb
MAX_SIZE_OF_PREVIEWABLE_FILE = 100 * 1024 * 1024

# Max age of media cache in seconds: 1 month
MAX_MEDIA_CACHE_AGE = 2628000

# Discord message cache expiry in seconds: 1 day
DISCORD_MESSAGE_EXPIRY = 79200

MAX_RESOURCE_NAME_LENGTH = 75

SIGNED_URL_EXPIRY_SECONDS = 7200

cache = caches["default"]

RAW_IMAGE_EXTENSIONS = ('.IIQ', '.3FR', '.DCR', '.K25', '.KDC', '.CRW', '.CR2', '.CR3', '.ERF', '.MEF', '.MOS', '.NEF', '.NRW', '.ORF', '.PEF', '.RW2', '.ARW', '.SRF', '.SR2')

message_codes = {
    1: {"pl": "Niepoprawne zapytanie", "en": "Bad Request"},
    2: {"pl": "Nieznany błąd serwera", "en": "Internal Server Error"},
    3: {"pl": "Błąd bazy danych", "en": "Database Error"},
    4: {"pl": "Użytkownik nieuwierzytelniony", "en": "Unauthenticated"},
    5: {"pl": "Brak uprawnień do zasobu", "en": "Access to resource forbidden"},
    6: {"pl": "Zasób już nie istnieje", "en": "Resource expired"},
    7: {"pl": "Zasób jeszcze nie gotowy", "en": "Resource is not ready yet"},
    8: {"pl": "Zasób nie istnieje", "en": "Resource doesn't exist"},
    9: {"pl": "Zasobu nie da sie pobrać", "en": "Resource is not downloadable"},
    10: {"pl": "Zasobu nie da sie strumieniować", "en": "Resource is not streamable"},
    11: {"pl": "Nie da sie wygenerować podglądu zasobu", "en": "Resource is not previewable"},
    12: {"pl": "Brak uprawnień do 'root' foldera", "en": "Access denied to 'root' folder"},
    13: {"pl": "Discord wysłał błędną odpowiedż", "en": "Unexpected discord response"},
    14: {"pl": "Discord jest chwilowo zablokowany ", "en": "Discord is temporarily blocked"},
    15: {"pl": "Funkcja jeszcze nie dostępna", "en": "Not yet implemented"},
    16: {"pl": "Hasło jest nie poprawne", "en": "Resource password is incorrect"},
    18: {"pl": "Plik już posiada thumbnail", "en": "File already has a thumbnail"},
    19: {"pl": "Brak hasła", "en": "Password is missing"},
    20: {"pl": "Backend httpx connect error", "en": "Backend httpx connect error"},

}

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
