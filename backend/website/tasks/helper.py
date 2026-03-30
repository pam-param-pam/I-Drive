from datetime import datetime, timezone, timedelta
from typing import Optional

from ..constants import EventCode
from ..core.Serializers import FolderSerializer, FileSerializer
from ..core.dataModels.http import RequestContext
from ..models import File
from ..websockets.utils import send_event

folder_serializer = FolderSerializer()
file_serializer = FileSerializer()
DISCORD_EPOCH = 1420070400000  # ms

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
    fragments_to_prefetch = 5
    prefetch_next_fragments.delay(fragment_id, fragments_to_prefetch)

def snowflake_to_datetime(snowflake_id: str):
    snowflake = int(snowflake_id)
    timestamp_ms = (snowflake >> 22) + DISCORD_EPOCH
    return datetime.fromtimestamp(timestamp_ms / 1000, timezone.utc)

def bulk_deletable(message_id: str):
    ts = snowflake_to_datetime(message_id)
    age = datetime.now(timezone.utc) - ts
    # avoid race conditions
    return age < timedelta(days=13, hours=23)
