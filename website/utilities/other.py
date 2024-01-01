import os
import json
from uuid import UUID

from website.models import File, Folder


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


class UUIDEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, UUID):
            # if the obj is uuid, we simply return the value of uuid
            return obj.hex
        return json.JSONEncoder.default(self, obj)



def create_files_dict(file_list):
    file_dict_list = []

    for file_obj in file_list:
        file_dict = {
            'folder': False,
            'id': str(file_obj.id),
            'name': file_obj.name,
            'parent_id': file_obj.parent_id,
            'extension': file_obj.extension,
            'streamable': file_obj.streamable,
            'size': file_obj.size,
            'encrypted_size': file_obj.encrypted_size,
            'uploaded_at': file_obj.uploaded_at.strftime('%Y-%m-%d %H:%M'),  # Format with date, hour, and minutes
            'ready': file_obj.ready,
            'owner': {"name": file_obj.owner.username, "id": file_obj.owner.id},
            "maintainers": [],
            "viewers": [],
        }

        file_dict_list.append(file_dict)

    return file_dict_list


def build_folder_tree(folder_objs, parent_folder=None):
    folder_tree = []

    # Get all folders with the specified parent folder
    child_folders = folder_objs.filter(parent=parent_folder)

    for folder in child_folders:

        folder_data = {
            'id': str(folder.id),
            'name': folder.name,
            'owner': {"name": folder.owner.username, "id": folder.owner.id},
            'parent_id': folder.parent_id,
            'children': build_folder_tree(folder_objs, folder),
        }

        folder_tree.append(folder_data)

    return folder_tree


def create_fragmented_folder_dict(folder_children):
    folder_list = []
    for folder in folder_children:
        folder_data = {
            'id': str(folder.id),
            'name': folder.name,
            'owner': {"name": folder.owner.username, "id": folder.owner.id},
            'parent_id': folder.parent_id,
            'folder': True,
        }
        folder_list.append(folder_data)
    return folder_list


def build_folder_content(folder_obj):
    file_children = File.objects.filter(parent=folder_obj)
    folder_children = Folder.objects.filter(parent=folder_obj)

    file_dicts = create_files_dict(file_children)
    folder_dicts = create_fragmented_folder_dict(folder_children)

    json_string = {"folder": True, "name": folder_obj.name, "id": folder_obj.id,
                   "owner": {"name": folder_obj.owner.username, "id": folder_obj.owner.id}, "maintainers": [],
                   "viewers": [], "children": file_dicts + folder_dicts}
    return json_string

