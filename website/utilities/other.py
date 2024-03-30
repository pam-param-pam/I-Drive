import os

from website.models import File, Folder, UserSettings

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

}


def calculate_time(file_size_bytes, bitrate_bps):
    time_seconds = (file_size_bytes * 8) / bitrate_bps
    return time_seconds


def get_percentage(current, all) -> int:
    if all == 0:
        return 0  # To avoid division by zero error
    percentage = round((current / all) * 100)
    return percentage


def create_temp_request_dir(request_id):
    upload_folder = os.path.join("temp", request_id)
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
    return upload_folder


def create_temp_file_dir(upload_folder, file_id):
    out_folder_path = os.path.join(upload_folder, str(file_id))
    if not os.path.exists(out_folder_path):
        os.makedirs(out_folder_path)
    return out_folder_path


def create_file_dict(file_obj):
    file_dict = {
        'isDir': False,
        'id': str(file_obj.id),
        'name': file_obj.name,
        'parent_id': file_obj.parent_id,
        'extension': file_obj.extension,
        'streamable': file_obj.streamable,
        'size': file_obj.size,
        'type': file_obj.type,
        'encrypted_size': file_obj.encrypted_size,
        'created': file_obj.created_at.strftime('%Y-%m-%d %H:%M'),  # Format with date, hour, and minutes
        'ready': file_obj.ready,
        'owner': {"name": file_obj.owner.username, "id": file_obj.owner.id},
        "maintainers": [],
        "last_modified": file_obj.last_modified_at.strftime('%Y-%m-%d %H:%M'),
    }
    if file_obj.size < 25 * 1024 * 1024:  # max preview size
        file_dict['preview_url'] = f"http://127.0.0.1:8000/api/file/preview/{file_obj.id}"
    return file_dict


def create_folder_dict(folder_obj):
    file_children = File.objects.filter(parent=folder_obj, ready=True)
    folder_children = Folder.objects.filter(parent=folder_obj)

    folder_dict = {
        'id': str(folder_obj.id),
        'name': folder_obj.name,
        "numFiles": len(file_children),
        "numFolders": len(folder_children),
        'created': folder_obj.created_at.strftime('%Y-%m-%d %H:%M'),
        'last_modified': folder_obj.last_modified_at.strftime('%Y-%m-%d %H:%M'),
        'owner': {"name": folder_obj.owner.username, "id": folder_obj.owner.id},
        'parent_id': folder_obj.parent_id,
        'isDir': True,
    }
    return folder_dict


def create_share_dict(share):
    isDir = False
    try:
        obj = File.objects.get(id=share.object_id)
    except File.DoesNotExist:
        try:
            obj = Folder.objects.get(id=share.object_id)
            isDir = True
        except Folder.DoesNotExist:
            # looks like folder/file no longer exist, deleting time!
            share.delete()
            return
    item = {
        "expire": share.expiration_time.strftime('%Y-%m-%d %H:%M'),
        "name": obj.name,
        "isDir": isDir,
        "token": share.token,
        "resource_id": share.object_id,
        "id": share.pk
    }
    return item


def build_folder_tree(folder_objs, parent_folder=None):
    folder_tree = []

    # Get all folders with the specified parent folder
    child_folders = folder_objs.filter(parent=parent_folder)

    for folder in child_folders:
        folder_dict = create_folder_dict(folder)
        folder_dict["children"] = build_folder_tree(folder_objs, folder)

        folder_tree.append(folder_dict)

    return folder_tree


def get_shared_folder(folder_obj, includeSubfolders):
    def recursive_build(folder):
        file_children = File.objects.filter(parent=folder, ready=True)
        folder_children = Folder.objects.filter(parent=folder)

        file_dicts = [create_file_dict(file) for file in file_children]

        folder_dicts = []
        if includeSubfolders:
            folder_dicts = [recursive_build(subfolder) for subfolder in folder_children]

        folder_dict = create_folder_dict(folder)
        folder_dict["children"] = file_dicts + folder_dicts

        return folder_dict

    return recursive_build(folder_obj)


def build_folder_content(folder_obj, includeTrash):

    file_children = File.objects.filter(parent=folder_obj, ready=True, inTrash=includeTrash)
    folder_children = Folder.objects.filter(parent=folder_obj, inTrash=includeTrash)

    file_dicts = []
    for file in file_children:
        file_dict = create_file_dict(file)
        file_dicts.append(file_dict)

    folder_dicts = []
    for folder in folder_children:
        folder_dict = create_folder_dict(folder)
        folder_dicts.append(folder_dict)

    folder_dict = create_folder_dict(folder_obj)
    folder_dict["children"] = file_dicts + folder_dicts

    return folder_dict


def build_response(task_id, message):
    return {"task_id": task_id, "message": message}


def error_res(user, code, error_code, details):  # build_http_error_response
    locale = "en"

    if not user.is_anonymous:
        settings = UserSettings.objects.get(user=user)
        locale = settings.locale

    return {"code": code, "error": message_codes[error_code][locale], "details": details}


def get_folder_path(folder_id, folder_structure, path=None):
    if path is None:
        path = []

    for folder in folder_structure['children']:
        if folder['id'] == folder_id:
            # Found the folder, add it to the path
            path.append(folder)
            return path
        elif folder['children']:
            # Recursively search in children
            result = get_folder_path(folder_id, folder, path + [folder])
            if result:
                return result

    # Folder ID not found in the current folder structure
    return []
