from enum import Enum

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
    16: {"pl": "Hasło do folderu jest nie poprawne", "en": "Folder password is incorrect"},
    17: {"pl": "Hasło do folderu jest wymagane", "en": "Folder password is required"},

}

class EventCode(Enum):
    ITEM_CREATE = 1
    ITEM_DELETE = 2
    ITEM_NAME_CHANGE = 3
    MESSAGE_SENT = 4
    ITEM_MOVED = 5
    ITEM_PREVIEW_INFO_ADD = 6
    FORCE_FOLDER_NAVIGATION = 7

