from datetime import timedelta, datetime
from typing import Union

from django.contrib.auth.models import User
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from django.db.models import DateTimeField
from django.utils import timezone

from website.models import File, Folder, UserSettings, Preview, ShareableLink, Thumbnail
from website.tasks import queue_ws_event
from website.utilities.TypeHinting import Resource
from website.utilities.constants import cache, SIGNED_URL_EXPIRY_SECONDS, GET_BASE_URL, API_BASE_URL, message_codes, EventCode
from website.utilities.errors import ResourcePermissionError, ResourceNotFoundError, RootPermissionError, MissingResourcePasswordError, \
    MissingOrIncorrectResourcePasswordError

signer = TimestampSigner()


# Function to sign a URL with an expiration time
def sign_file_id_with_expiry(file_id: str) -> str:
    # cached_signed_file_id = cache.get(file_id)
    # if cached_signed_file_id:
    #     return cached_signed_file_id
    signed_file_id = signer.sign(file_id)
    cache.set(file_id, signed_file_id, timeout=SIGNED_URL_EXPIRY_SECONDS)
    return signed_file_id


# Function to verify and extract the file id
def verify_signed_file_id(signed_file_id: str, expiry_seconds: int = SIGNED_URL_EXPIRY_SECONDS) -> str:
    try:
        file_id = signer.unsign(signed_file_id, max_age=timedelta(seconds=expiry_seconds))
        return file_id
    except (BadSignature, SignatureExpired):
        raise ResourcePermissionError("URL not valid or expired.")


def formatDate(date: datetime) -> str:
    return timezone.localtime(date).strftime('%Y-%m-%d %H:%M')


def logout_and_close_websockets(user_id: int) -> None:
    queue_ws_event.delay(
        'user',
        {
            "type": "logout",
            "user_id": user_id,
        }
    )
    queue_ws_event.delay(
        'command',
        {
            "type": "logout",
            "user_id": user_id,
        }
    )


def send_event(user_id: int, op_code: EventCode, request_id: int, data: Union[list, dict]) -> None:
    queue_ws_event.delay(
        'user',
        {
            'type': 'send_event',
            'user_id': user_id,
            'op_code': op_code.value,
            'request_id': request_id,
            'data': data,
        }
    )


def create_breadcrumbs(folder_obj: Folder) -> list:
    folder_path = []

    while folder_obj.parent:
        data = {"name": folder_obj.name, "id": folder_obj.id}
        folder_path.append(data)
        folder_obj = Folder.objects.get(id=folder_obj.parent.id)
    folder_path.reverse()
    return folder_path


def create_share_breadcrumbs(folder_obj: Folder, obj_in_share: Resource, isFolderId: bool = False) -> list:
    folder_path = []

    while folder_obj:
        data = {"name": folder_obj.name, "id": folder_obj.id}
        if folder_obj != obj_in_share:
            folder_path.append(data)
        if folder_obj == obj_in_share:
            if isFolderId:
                folder_path.append(data)
            break
        if not folder_obj.parent:
            break
        folder_obj = Folder.objects.get(id=folder_obj.parent.id)

    folder_path.reverse()
    return folder_path


def create_file_dict(file_obj: File, hide=False) -> dict:
    file_dict = {
        'isDir': False,
        'id': str(file_obj.id),
        'name': file_obj.name,
        'parent_id': file_obj.parent_id,
        'extension': file_obj.extension,
        'size': file_obj.size,
        'type': file_obj.type,
        # 'encrypted_size': file_obj.encrypted_size,
        'created': formatDate(file_obj.created_at),
        'last_modified': formatDate(file_obj.last_modified_at),
        'isLocked': file_obj.is_locked
        # 'ready': file_obj.ready,
        # 'owner': file_obj.owner.username,
        # "maintainers": [],
    }
    if file_obj.is_locked:
        file_dict['lockFrom'] = file_obj.lockFrom.id if file_obj.lockFrom else file_obj.id

    if file_obj.inTrashSince:
        file_dict["in_trash_since"] = formatDate(file_obj.inTrashSince)

    try:
        preview = Preview.objects.get(file=file_obj)
        file_dict["iso"] = preview.iso
        file_dict["model_name"] = preview.model_name
        file_dict["aperture"] = preview.aperture
        file_dict["exposure_time"] = preview.exposure_time
        file_dict["focal_length"] = preview.focal_length

    except Preview.DoesNotExist:
        pass

    # base_url = "http://127.0.0.1:8000"
    # stream_url = "http://192.168.1.14:8050"

    # base_url = "http://127.0.0.1:8050/stream"
    # hide media from files in trash for example
    if not hide or not file_obj.is_locked:
        signed_file_id = sign_file_id_with_expiry(file_obj.id)

        if file_obj.extension in (
                '.IIQ', '.3FR', '.DCR', '.K25', '.KDC', '.CRW', '.CR2', '.CR3', '.ERF', '.MEF', '.MOS', '.NEF', '.NRW', '.ORF', '.PEF', '.RW2', '.ARW', '.SRF', '.SR2'):
            file_dict['preview_url'] = f"{API_BASE_URL}/api/file/preview/{signed_file_id}"

        download_url = f"{GET_BASE_URL}/stream/{signed_file_id}"

        file_dict['download_url'] = download_url

        thumbnail = Thumbnail.objects.filter(file=file_obj)

        if thumbnail:
            file_dict['thumbnail_url'] = f"{GET_BASE_URL}/thumbnail/{signed_file_id}"

    return file_dict


def create_folder_dict(folder_obj: Folder) -> dict:
    """
    Crates partial folder dict, not containing children items
    """
    file_children = folder_obj.files.filter(ready=True, inTrash=False)
    folder_children = folder_obj.subfolders.filter(inTrash=False)

    folder_dict = {
        'id': str(folder_obj.id),
        'name': folder_obj.name,
        "numFiles": len(file_children),
        "numFolders": len(folder_children),
        'created': formatDate(folder_obj.created_at),
        'last_modified': formatDate(folder_obj.last_modified_at),
        # 'owner': folder_obj.owner.username,
        'parent_id': folder_obj.parent_id,
        'isDir': True,
        'isLocked': folder_obj.is_locked,

    }
    if folder_obj.is_locked:
        folder_dict['lockFrom'] = folder_obj.lockFrom.id if folder_obj.lockFrom else None
    if folder_obj.inTrashSince:
        folder_dict["in_trash_since"] = formatDate(folder_obj.inTrashSince),
    return folder_dict


def create_share_dict(share: ShareableLink) -> dict:
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
            raise ResourceNotFoundError(f"Resource with id {share.object_id} not found! Most likely underlying resource was deleted. Share is no longer valid.")
    item = {
        "expire": formatDate(share.expiration_time),
        "name": obj.name,
        "isDir": isDir,
        "token": share.token,
        "resource_id": share.object_id,
        "id": share.pk,
        # "download_url": f"{GET_BASE_URL}/"
    }
    return item


@DeprecationWarning
def get_shared_folder(folder_obj: Folder, includeSubfolders: bool) -> dict:
    def recursive_build(folder):
        file_children = folder_obj.files.filter(ready=True)
        folder_children = folder_obj.subfolders.all()

        file_dicts = [create_file_dict(file) for file in file_children]

        folder_dicts = []
        if includeSubfolders:
            folder_dicts = [recursive_build(subfolder) for subfolder in folder_children]

        folder_dict = create_folder_dict(folder)
        folder_dict["children"] = file_dicts + folder_dicts

        return folder_dict

    return recursive_build(folder_obj)


def build_folder_content(folder_obj: Folder, include_folders: bool = True, include_files: bool = True) -> dict:
    file_children = []
    if include_files:
        file_children = folder_obj.files.filter(ready=True, inTrash=False)

    folder_children = []
    if include_folders:
        folder_children = folder_obj.subfolders.filter(inTrash=False)

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


def build_response(task_id: str, message: str) -> dict:
    return {"task_id": task_id, "message": message}


def error_res(user: User, code: int, error_code: int, details: str) -> dict:  # build_http_error_response
    locale = "en"

    if not user.is_anonymous:
        settings = UserSettings.objects.get(user=user)
        locale = settings.locale

    return {"code": code, "error": message_codes[error_code][locale], "details": details}


def get_resource(obj_id: str) -> Resource:
    try:
        item = Folder.objects.get(id=obj_id)
    except Folder.DoesNotExist:
        try:
            item = File.objects.get(id=obj_id)
        except File.DoesNotExist:
            raise ResourceNotFoundError(f"Resource with id of '{obj_id}' doesn't exist.")
    return item


def check_resource_perms(request, resource: Resource, checkOwnership=True, checkRoot=True, checkFolderLock=True) -> None:
    if checkOwnership:
        if resource.owner != request.user:
            raise ResourcePermissionError()

    if checkRoot:
        if isinstance(resource, Folder) and not resource.parent:
            raise RootPermissionError("Cannot access 'root' folder!")
    if checkFolderLock:
        check_folder_password(request, resource)


def check_folder_password(request, resource: Resource) -> None:
    password = request.headers.get("X-Folder-Password")
    passwords = request.data.get('resourcePasswords')
    if resource.is_locked:
        if password:
            if resource.password != password:
                raise MissingOrIncorrectResourcePasswordError([resource.lockFrom])
        elif passwords:
            if resource.lockFrom and resource.password != passwords.get(resource.lockFrom.id):
                raise MissingOrIncorrectResourcePasswordError([resource.lockFrom])
        else:
            raise MissingOrIncorrectResourcePasswordError([resource.lockFrom])


def create_zip_file_dict(file_obj: File, file_name: str) -> dict:
    signed_id = sign_file_id_with_expiry(file_obj.id)

    file_dict = {"id": file_obj.id,
                 "name": file_name,
                 "signed_id": signed_id,
                 "isDir": False,
                 "size": file_obj.size,
                 "mimetype": file_obj.mimetype,
                 "type": file_obj.type,
                 "modified_at": timezone.localtime(file_obj.last_modified_at),
                 # "created_at": timezone.localtime(file_obj.created_at),
                 "key": str(file_obj.key),
                 "fragments": [],
                 }
    fragments_list = []
    for fragment in file_obj.fragments.all():
        fragments_list.append({"sequence": fragment.sequence, "size": fragment.size})
    file_dict["fragments"] = fragments_list
    return file_dict


def calculate_size(folder: Folder) -> int:
    """
    Function to recursively calculate size of a folder
    """

    size = 0
    for file_in_folder in folder.files.filter(ready=True, inTrash=False):
        size += file_in_folder.size

    # Recursively calculate size for subfolders
    for subfolder in folder.subfolders.filter(inTrash=False):
        size += calculate_size(subfolder)
    return size


def calculate_file_and_folder_count(folder: Folder) -> tuple[int, int]:
    """
    Function to recursively calculate entire file & folder count of a given folder
    """
    folder_count = 0
    file_count = 0

    file_count += len(folder.files.filter(ready=True, inTrash=False))

    # Recursively calculate size for subfolders
    subfolders = folder.subfolders.filter(inTrash=False)
    folder_count += len(subfolders)

    for subfolder in subfolders:
        folders, files = calculate_file_and_folder_count(subfolder)
        folder_count += folders
        file_count += files

    return folder_count, file_count


def get_flattened_children(folder: Folder, full_path="") -> list:
    """
    Recursively collects all children (folders and files) of the given folder
    into a flattened list with file IDs and names including folders.
    """

    children = []

    # Collect all files in the current folder
    files = folder.files.all()
    if files:
        for file in files:
            file_full_path = f"{full_path}{folder.name}/{file.name}"
            file_dict = create_zip_file_dict(file, file_full_path)
            children.append(file_dict)
    else:
        pass
        # todo remove pass?
        folder_full_path = f"{full_path}{folder.name}/"

        children.append({'id': folder.id, 'name': folder_full_path, "isDir": True})

    # Recursively collect all subfolders and their children
    for subfolder in folder.subfolders.all():
        subfolder_full_path = f"{full_path}{folder.name}/"
        children.extend(get_flattened_children(subfolder, subfolder_full_path))

    return children
