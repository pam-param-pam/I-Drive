from collections import defaultdict
from typing import List, Union, Optional

from ..Serializers import FolderSerializer, FileSerializer
from ..crypto.utils import encrypt_message
from ..dataModels.http import RequestContext
from ...constants import EventCode
from ...models import File, Folder
from ...tasks.queueTasks import queue_ws_event


def group_and_send_event(context: RequestContext, op_code: EventCode, resources: List[Union[File, Folder]]) -> None:
    """Group files by parent object and send event for each parent"""
    grouped_files = defaultdict(list)
    parent_mapping = {}

    folder_serializer = FolderSerializer()
    file_serializer = FileSerializer()

    for resource in resources:
        parent_mapping[resource.parent_id] = resource.parent
        if isinstance(resource, Folder):
            grouped_files[resource.parent.id].append(folder_serializer.serialize_object(resource))
        else:
            grouped_files[resource.parent_id].append(file_serializer.serialize_object(resource))

    for parent_id, file_dicts in grouped_files.items():
        parent = parent_mapping[parent_id]
        send_event(context, parent, op_code, file_dicts)


def send_event(context: RequestContext, folder_context: Optional[Folder], op_code: EventCode, payload: Union[List, dict, str, None] = None) -> None:
    """
    Sends an event to the websocket layer.
    Handles optional encryption when a folder is locked.
    """
    if payload and not isinstance(payload, list):
        payload = [payload]

    ws_payload = {
        'is_encrypted': False
    }

    if folder_context:
        ws_payload['folder_context_id'] = folder_context.id

    event_body = {
        'op_code': op_code.value
    }

    if payload:
        event_body['data'] = payload

    # Encrypt event body when the folder is locked
    if folder_context and folder_context.is_locked:
        ws_payload['is_encrypted'] = True
        ws_payload['lockFrom'] = folder_context.lockFrom.id
        event_body = encrypt_message(folder_context.password, event_body)

    # Attach final event object
    ws_payload['event'] = event_body

    queue_ws_event.delay(
        'user',
        {
            'type': 'send_event',
            'context': context,
            'ws_payload': ws_payload
        }
    )



