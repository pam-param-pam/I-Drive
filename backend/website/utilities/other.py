from datetime import timedelta, datetime
from typing import Union, List, Dict

from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from django.utils import timezone

from ..models import File, Folder, Preview, ShareableLink, Thumbnail, VideoPosition
from ..tasks import queue_ws_event
from ..utilities.TypeHinting import Resource, Breadcrumbs, FileDict, FolderDict, ShareDict, ResponseDict, ZipFileDict, ErrorDict
from ..utilities.constants import cache, SIGNED_URL_EXPIRY_SECONDS, API_BASE_URL, EventCode
from ..utilities.errors import ResourcePermissionError, ResourceNotFoundError, RootPermissionError, MissingOrIncorrectResourcePasswordError

signer = TimestampSigner()

def format_wait_time(seconds: int) -> str:
    if seconds >= 3600:  # More than or equal to 1 hour
        hours = seconds // 3600
        return f"{hours} hour{'s' if hours > 1 else ''}"
    elif seconds >= 60:  # More than or equal to 1 minute
        minutes = seconds // 60
        return f"{minutes} minute{'s' if minutes > 1 else ''}"
    else:
        return f"{seconds} second{'s' if seconds > 1 else ''}"


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


def send_event(user_id: int, op_code: EventCode, request_id: int, data: Union[List, dict]) -> None:
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


def create_breadcrumbs(folder_obj: Folder) -> List[Breadcrumbs]:
    folder_path = []

    while folder_obj.parent:
        data = {"name": folder_obj.name, "id": folder_obj.id}
        folder_path.append(data)
        folder_obj = get_folder(folder_obj.parent.id)
    folder_path.reverse()
    return folder_path


def create_share_breadcrumbs(folder_obj: Folder, obj_in_share: Resource, isFolderId: bool = False) -> List[Breadcrumbs]:
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

        folder_obj = get_folder(folder_obj.parent.id)

    folder_path.reverse()
    return folder_path


def create_file_dict(file_obj: File, hide=False) -> FileDict:
    file_dict = {
        'isDir': False,
        'id': file_obj.id,
        'name': file_obj.name,
        'parent_id': file_obj.parent.id,
        'extension': file_obj.extension,
        'size': file_obj.size,
        'type': file_obj.type,
        'created': formatDate(file_obj.created_at),
        'last_modified': formatDate(file_obj.last_modified_at),
        'isLocked': file_obj.is_locked,
        'is_encrypted': file_obj.is_encrypted,
        'encryption_method': file_obj.encryption_method

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

    if not hide:
        signed_file_id = sign_file_id_with_expiry(file_obj.id)

        if file_obj.extension in (
                '.IIQ', '.3FR', '.DCR', '.K25', '.KDC', '.CRW', '.CR2', '.CR3', '.ERF', '.MEF', '.MOS', '.NEF', '.NRW', '.ORF', '.PEF', '.RW2', '.ARW', '.SRF', '.SR2'):
            file_dict['preview_url'] = f"{API_BASE_URL}/file/preview/{signed_file_id}"

        download_url = f"{API_BASE_URL}/stream/{signed_file_id}"

        file_dict['download_url'] = download_url

        thumbnail = Thumbnail.objects.filter(file=file_obj)

        if thumbnail.exists():
            file_dict['thumbnail_url'] = f"{API_BASE_URL}/file/thumbnail/{signed_file_id}"

        if file_obj.type == "video":
            position = 0
            try:
                position = file_obj.videoposition.timestamp
            except VideoPosition.DoesNotExist:
                pass
            file_dict['video_position'] = position

    return file_dict


def create_folder_dict(folder_obj: Folder) -> FolderDict:
    """
    Crates partial folder dict, not containing children items
    """

    folder_dict = {
        'isDir': True,
        'id': folder_obj.id,
        'name': folder_obj.name,
        'parent_id': folder_obj.parent_id,
        'created': formatDate(folder_obj.created_at),
        'last_modified': formatDate(folder_obj.last_modified_at),
        'isLocked': folder_obj.is_locked,

    }
    if folder_obj.is_locked:
        folder_dict['lockFrom'] = folder_obj.lockFrom.id if folder_obj.lockFrom else folder_obj.id

    if folder_obj.inTrashSince:
        folder_dict["in_trash_since"] = formatDate(folder_obj.inTrashSince)

    return folder_dict


def create_share_dict(share: ShareableLink) -> ShareDict:
    try:
        obj = get_resource(share.object_id)
    except ResourceNotFoundError:
        # looks like folder/file no longer exist, deleting time!
        share.delete()
        raise ResourceNotFoundError(f"Resource with id {share.object_id} not found! Most likely underlying resource was deleted. Share is no longer valid.")

    isDir = True if isinstance(obj, Folder) else False

    item = {
        "expire": formatDate(share.expiration_time),
        "name": obj.name,
        "isDir": isDir,
        "token": share.token,
        "resource_id": share.object_id,
        "id": share.id,
    }
    return item

def hide_info_in_share_context(share: ShareableLink, resource_dict: Union[FileDict, FolderDict]) -> Dict:
    # hide lockFrom info
    del resource_dict['isLocked']
    try:
        del resource_dict['lockFrom']
    except KeyError:
        pass
    if share.is_locked():
        resource_dict['isLocked'] = True
        resource_dict['lockFrom'] = share.id
    return resource_dict

def create_share_resource_dict(share: ShareableLink, resource_in_share: Resource) -> Dict:
    if isinstance(resource_in_share, Folder):
        resource_dict = create_folder_dict(resource_in_share)
    else:
        resource_dict = create_file_dict(resource_in_share)

    return hide_info_in_share_context(share, resource_dict)


def build_share_folder_content(share: ShareableLink, folder_obj: Folder, include_folders: bool = True, include_files: bool = True) -> FolderDict:
    folder_dict = build_folder_content(folder_obj, include_folders, include_files)

    if share.is_locked():
        censored_children = []
        for resource_dict in folder_dict['children']:
            censored_child = hide_info_in_share_context(share, resource_dict)
            censored_children.append(censored_child)
        folder_dict['children'] = censored_children

    return folder_dict

def build_folder_content(folder_obj: Folder, include_folders: bool = True, include_files: bool = True) -> FolderDict:
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

    folder_dict["children"] = file_dicts + folder_dicts  # type: ignore         # goofy python bug

    return folder_dict


def build_response(task_id: str, message: str) -> ResponseDict:
    return {"task_id": task_id, "message": message}


def build_http_error_response(code: int, error: str, details: str) -> ErrorDict:  #todo  maybe change to build_http_error_response?
    return {"code": code, "error": error, "details": details}

def get_file(file_id: str) -> File:
    try:
        file = File.objects.get(id=file_id)
    except File.DoesNotExist:
        raise ResourceNotFoundError(f"File with id of '{file_id}' doesn't exist.")
    return file

def get_folder(folder_id: str) -> Folder:
    try:
        folder = Folder.objects.get(id=folder_id)
    except Folder.DoesNotExist:
        raise ResourceNotFoundError(f"Folder with id of '{folder_id}' doesn't exist.")
    return folder

def get_resource(obj_id: str) -> Resource:
    try:
        item = get_folder(obj_id)
    except ResourceNotFoundError:
        try:
            item = get_file(obj_id)
        except ResourceNotFoundError:
            raise ResourceNotFoundError(f"Resource with id of '{obj_id}' doesn't exist.")
    return item


def check_resource_perms(request, resource: Resource, checkOwnership=True, checkRoot=True, checkFolderLock=True, checkTrash=False, checkReady=True) -> None:
    if checkOwnership:
        if resource.owner != request.user:
            raise ResourcePermissionError("You have no access to this resource!")

    if checkFolderLock:
        check_folder_password(request, resource)

    if checkRoot:
        if isinstance(resource, Folder) and not resource.parent:
            raise RootPermissionError()

    if checkTrash:
        if resource.inTrash:
            raise ResourcePermissionError("Cannot access resource in trash!")

    if checkReady:
        if not resource.ready:
            raise ResourceNotFoundError("Resource is not ready")


def check_folder_password(request, resource: Resource) -> None:
    password = request.headers.get("X-Resource-Password")
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


def create_zip_file_dict(file_obj: File, file_name: str) -> ZipFileDict:

    check_resource_perms("dummy request", file_obj, checkOwnership=False, checkRoot=False, checkFolderLock=False, checkTrash=True)

    return {"name": file_name, "isDir": False, "fileObj": file_obj}


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


def get_flattened_children(folder: Folder, full_path="", single_root=False) -> List[ZipFileDict]:
    """
    Recursively collects all children (folders and files) of the given folder
    into a flattened list with file IDs and names including folders.
    """

    children = []
    check_resource_perms("dummy request", folder, checkOwnership=False, checkRoot=False, checkFolderLock=False, checkTrash=True)

    # Collect all files in the current folder
    files = folder.files.all()
    if files:
        for file in files:
            file_full_path = f"{full_path}{folder.name}/{file.name}"

            if single_root:
                file_full_path = f"{full_path}{file.name}"

            file_dict = create_zip_file_dict(file, file_full_path)
            children.append(file_dict)
    else:
        pass
        #todo handle empty dirs

    # Recursively collect all subfolders and their children
    for subfolder in folder.subfolders.all():
        subfolder_full_path = f"{full_path}{folder.name}/"
        children.extend(get_flattened_children(subfolder, subfolder_full_path))

    return children



