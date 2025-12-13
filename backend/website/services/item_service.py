from ..constants import MAX_RESOURCE_NAME_LENGTH, EventCode
from ..core.Serializers import FileSerializer, FolderSerializer
from ..core.dataModels.general import Item
from ..core.helpers import get_file_type, validate_value
from ..core.validators.GeneralChecks import MaxLength
from ..models import File
from ..websockets.utils import send_event


def rename_item(request, item_obj: Item, new_name: str, extension: str) -> None:
    validate_value(new_name, str, checks=[MaxLength(MAX_RESOURCE_NAME_LENGTH)])
    validate_value(extension, str, checks=[MaxLength(30)])

    item_obj.name = new_name

    if isinstance(item_obj, File):
        item_obj.type = get_file_type(extension)
        item_obj.save()
        data = FileSerializer().serialize_object(item_obj)
    else:
        item_obj.save()
        data = FolderSerializer().serialize_object(item_obj)

    send_event(request.context, item_obj.parent, EventCode.ITEM_UPDATE, data)

