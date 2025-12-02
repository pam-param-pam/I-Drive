from typing import Optional

from ..constants import EventCode
from ..core.Serializers import FolderSerializer, FileSerializer
from ..core.dataModels.http import RequestContext
from ..core.websocket.utils import send_event
from ..models import File

folder_serializer = FolderSerializer()
file_serializer = FileSerializer()

def send_message(message: str, args: Optional[dict], finished: bool, context: RequestContext, isError=False):
    send_event(context, None, EventCode.MESSAGE_SENT, {
        "message": message,
        "args": args,
        "isFinished": finished,
        "isError": isError,
        "task_id": context.request_id
    })


def auto_prefetch(file_obj: File, fragment_id: str) -> None:
    from .otherTasks import prefetch_next_fragments
    # todo circular
    if file_obj.type == "video" and file_obj.duration and file_obj.duration > 0:
        mb_per_second = round((file_obj.size / file_obj.duration) / (1024 * 1024), 1)
        fragments_to_prefetch = mb_per_second
        if mb_per_second <= 1:
            fragments_to_prefetch = 1
        elif mb_per_second > 20:
            fragments_to_prefetch = 20
    else:
        fragments_to_prefetch = 1

    prefetch_next_fragments.delay(fragment_id, fragments_to_prefetch)