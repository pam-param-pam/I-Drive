import os
from datetime import timedelta
from typing import Union

from django.contrib.auth.models import User
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from django.utils import timezone

from website.models import File, Folder, UserSettings, Preview, ShareableLink, Thumbnail
from website.tasks import queue_ws_event
from website.utilities.OPCodes import message_codes, EventCode
from website.utilities.TypeHinting import Resource
from website.utilities.constants import cache, SIGNED_URL_EXPIRY_SECONDS
from website.utilities.errors import ResourcePermissionError, ResourceNotFoundError, RootPermissionError, MissingResourcePasswordError

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

    while folder_obj.parent:
        data = {"name": folder_obj.name, "id": folder_obj.id}
        if folder_obj != obj_in_share:
            folder_path.append(data)
        if folder_obj == obj_in_share:
            if isFolderId:
                folder_path.append(data)
            break

        folder_obj = Folder.objects.get(id=folder_obj.parent.id)

    folder_path.reverse()
    return folder_path


def create_file_dict(file_obj: File) -> dict:
    file_dict = {
        'isDir': False,
        'id': str(file_obj.id),
        'name': file_obj.name,
        'parent_id': file_obj.parent_id,
        'extension': file_obj.extension,
        'size': file_obj.size,
        'type': file_obj.type,
        #'encrypted_size': file_obj.encrypted_size,
        'created': timezone.localtime(file_obj.created_at).strftime('%Y-%m-%d %H:%M'),
        'last_modified': timezone.localtime(file_obj.last_modified_at).strftime('%Y-%m-%d %H:%M'),
        'isLocked': file_obj.is_locked
        # 'ready': file_obj.ready,
        # 'owner': {"name": file_obj.owner.username, "id": file_obj.owner.id},
        # "maintainers": [],
    }
    if file_obj.is_locked:
        file_dict['lockFrom'] = file_obj.lockFrom.id if file_obj.lockFrom else file_obj.id

    if file_obj.inTrashSince:
        file_dict["in_trash_since"] = timezone.localtime(file_obj.inTrashSince).strftime('%Y-%m-%d %H:%M'),

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
    base_url = "https://api.pamparampam.dev"
    stream_url = "https://get.pamparampam.dev"

    # base_url = "http://127.0.0.1:8050/stream"
    signed_file_id = sign_file_id_with_expiry(file_obj.id)

    if file_obj.extension in (
            '.IIQ', '.3FR', '.DCR', '.K25', '.KDC', '.CRW', '.CR2', '.CR3', '.ERF', '.MEF', '.MOS', '.NEF', '.NRW', '.ORF', '.PEF', '.RW2', '.ARW', '.SRF', '.SR2'):
        file_dict['preview_url'] = f"{base_url}/api/file/preview/{signed_file_id}"

    download_url = f"{stream_url}/stream/{signed_file_id}"

    file_dict['download_url'] = download_url

    thumbnail = Thumbnail.objects.filter(file=file_obj)

    if thumbnail:
        file_dict['thumbnail_url'] = f"{stream_url}/thumbnail/{signed_file_id}"

    return file_dict


def create_folder_dict(folder_obj: Folder) -> dict:
    """
    Crates partial folder dict, not containing children items
    """
    file_children = folder_obj.files.filter(ready=True)
    folder_children = folder_obj.folders.all()

    folder_dict = {
        'id': str(folder_obj.id),
        'name': folder_obj.name,
        "numFiles": len(file_children),
        "numFolders": len(folder_children),
        'created': timezone.localtime(folder_obj.created_at).strftime('%Y-%m-%d %H:%M'),
        'last_modified': timezone.localtime(folder_obj.last_modified_at).strftime('%Y-%m-%d %H:%M'),
        'owner': {"name": folder_obj.owner.username, "id": folder_obj.owner.id},
        'parent_id': folder_obj.parent_id,
        'isDir': True,
        'isLocked': folder_obj.is_locked,
        'lockFrom': folder_obj.lockFrom.id if folder_obj.lockFrom else folder_obj.id

    }
    if folder_obj.is_locked:
        folder_dict['lockFrom'] = folder_obj.lockFrom.id if folder_obj.lockFrom else None
    if folder_obj.inTrashSince:
        folder_dict["in_trash_since"] = timezone.localtime(folder_obj.inTrashSince).strftime('%Y-%m-%d %H:%M'),
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
        "expire": share.expiration_time.strftime('%Y-%m-%d %H:%M'),
        "name": obj.name,
        "isDir": isDir,
        "token": share.token,
        "resource_id": share.object_id,
        "id": share.pk
    }
    return item


@DeprecationWarning
def get_shared_folder(folder_obj: Folder, includeSubfolders: bool) -> dict:
    def recursive_build(folder):
        file_children = folder_obj.files.filter(ready=True)
        folder_children = folder_obj.folders.all()

        file_dicts = [create_file_dict(file) for file in file_children]

        folder_dicts = []
        if includeSubfolders:
            folder_dicts = [recursive_build(subfolder) for subfolder in folder_children]

        folder_dict = create_folder_dict(folder)
        folder_dict["children"] = file_dicts + folder_dicts

        return folder_dict

    return recursive_build(folder_obj)


def build_folder_content(folder_obj: Folder, include_folders: bool = True) -> dict:
    file_children = folder_obj.files.filter(ready=True, inTrash=False)

    folder_children = []
    if include_folders:
        folder_children = folder_obj.folders.filter(inTrash=False)

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

def get_resource(obj_id: str):
    try:
        item = Folder.objects.get(id=obj_id)
    except Folder.DoesNotExist:
        try:
            item = File.objects.get(id=obj_id)
        except File.DoesNotExist:
            raise ResourceNotFoundError(f"Resource with id of '{obj_id}' doesn't exist.")
    return item

def check_resource_perms(request, resource: Resource):
    if resource.owner != request.user:
        raise ResourcePermissionError()

    if isinstance(resource, Folder) and not resource.parent:
        raise RootPermissionError("Cannot modify 'root' folder!")

    password = request.headers.get("X-Folder-Password")
    if password != resource.password:
        raise MissingResourcePasswordError(lockFrom=resource.lockFrom.id, resourceId=resource.id)

@DeprecationWarning
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

@DeprecationWarning
def calculate_time(file_size_bytes, bitrate_bps):
    time_seconds = (file_size_bytes * 8) / bitrate_bps
    return time_seconds

@DeprecationWarning
def get_percentage(current, all):
    if all == 0:
        return 0  # To avoid division by zero error
    percentage = round((current / all) * 100)
    return percentage

@DeprecationWarning
def create_temp_request_dir(request_id):
    upload_folder = os.path.join("temp", request_id)
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
    return upload_folder

@DeprecationWarning
def create_temp_file_dir(upload_folder, file_id):
    out_folder_path = os.path.join(upload_folder, str(file_id))
    if not os.path.exists(out_folder_path):
        os.makedirs(out_folder_path)
    return out_folder_path
"""
def build_folder_tree(folder_objs, parent_folder=None):
    folder_tree = []

    # Get all folders with the specified parent folder
    child_folders = folder_objs.filter(parent=parent_folder)

    for folder in child_folders:
        folder_dict = create_folder_dict(folder)
        folder_dict["children"] = build_folder_tree(folder_objs, folder)

        folder_tree.append(folder_dict)

    return folder_tree
"""
