from ..constants import MAX_RESOURCE_NAME_LENGTH, EventCode
from ..core.Serializers import FileSerializer, FolderSerializer
from ..core.dataModels.general import Item
from ..core.errors import BadRequestError
from ..core.helpers import get_file_type
from ..core.websocket.utils import send_event
from ..models import File


def rename_item(request, item_obj: Item, new_name: str, extension: str) -> None:
    if len(new_name) > MAX_RESOURCE_NAME_LENGTH:
        raise BadRequestError(f"Name cannot be longer than '{MAX_RESOURCE_NAME_LENGTH}' characters")

    item_obj.name = new_name

    if isinstance(item_obj, File):
        item_obj.type = get_file_type(extension)
        item_obj.save()
        data = FileSerializer().serialize_object(item_obj)
    else:
        item_obj.save()
        data = FolderSerializer().serialize_object(item_obj)

    send_event(request.context, item_obj.parent, EventCode.ITEM_UPDATE, data)

