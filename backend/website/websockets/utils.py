from collections import defaultdict
import logging
from typing import List, Union, Optional

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction

from ..constants import EventCode
from ..core.Serializers import FolderSerializer, FileSerializer
from website.queries.display import load_file_displays, load_folder_displays
from website.core.http.context import RequestContext
from ..models import File, Folder


logger = logging.getLogger(__name__)


def send_message(message: str, args: Optional[dict], finished: bool, context: RequestContext, isError=False):
    send_event(context, None, EventCode.MESSAGE_SENT, {
        "message": message,
        "args": args,
        "isFinished": finished,
        "isError": isError,
        "task_id": context.request_id
    })

def group_and_send_event(context: RequestContext, op_code: EventCode, resources: List[Union[File, Folder]]) -> None:
    """Group files by parent object and send event for each parent"""
    grouped_files = defaultdict(list)
    parent_mapping = {}
    serialized_files = {
        item["id"]: item for item in FileSerializer.serialize_many(load_file_displays(
            resource for resource in resources if isinstance(resource, File)
        ))
    }

    serialized_folders = {
        str(row["id"]): FolderSerializer.serialize_dict(row)
        for row in load_folder_displays(resource for resource in resources if isinstance(resource, Folder))
    }

    for resource in resources:
        if resource.parent_id not in parent_mapping:
            parent_mapping[resource.parent_id] = resource.parent
        grouped_files[resource.parent_id].append(resource)

    for parent_id, items in grouped_files.items():
        parent = parent_mapping[parent_id]
        send_event(context, parent, op_code, [
            serialized_folders[str(item.id)] if isinstance(item, Folder)
            else serialized_files[str(item.id)] for item in items
        ])


def send_event(context: RequestContext, folder_context: Optional[Folder], op_code: EventCode, payload: Union[List, dict, str, None] = None) -> None:
    transaction.on_commit(lambda: _send_event(context, folder_context, op_code, payload))


def _send_event(context: RequestContext, folder_context: Optional[Folder], op_code: EventCode, payload: Union[List, dict, str, None] = None) -> None:
    """
    Sends an event to the websocket layer.
    Handles optional encryption when a folder is locked.
    """
    try:
        if payload and not isinstance(payload, list):
            payload = [payload]

        ws_payload = {'is_encrypted': False}
        if folder_context:
            ws_payload['folder_context_id'] = folder_context.id
        event_body = {'op_code': op_code.value}
        if payload:
            event_body['data'] = payload
        ws_payload['event'] = event_body

        send_channels_message(
            'user',
            {
                'type': 'send_event',
                'context': context.__json__(),
                'ws_payload': ws_payload
            }
        )
    except Exception:
        logger.exception("Failed to send websocket event %s", op_code)


def send_channels_message(ws_channel, ws_event: dict):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(ws_channel, ws_event)
