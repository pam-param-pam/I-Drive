from datetime import timedelta

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from ..auth.Permissions import CheckTrash, CheckReady
from ..auth.utils import check_resource_perms
from ..core.dataModels.general import Item
from ..core.errors import BadRequestError
from ..core.helpers import validate_ids_as_list
from ..models import ShareableLink, UserZIP, Folder
from ..queries.selectors import check_if_item_belongs_to_share, get_item


def create_share(user: User, item_obj: Item, unit: str, value: int, password: str) -> ShareableLink:
    units = {
        "minutes": timedelta(minutes=value),
        "hours": timedelta(hours=value),
        "days": timedelta(days=value),
    }

    if unit not in units:
        raise BadRequestError("Invalid unit. Supported units: minutes, hours, days.")

    expiration_time = timezone.now() + units[unit]

    content_type = ContentType.objects.get_for_model(item_obj)

    share = ShareableLink.objects.create(
        expiration_time=expiration_time,
        owner=user,
        content_type=content_type,
        object_id=item_obj.pk,
        password=password or None,
    )

    return share


def delete_share(share: ShareableLink) -> None:
    share.delete()


def create_share_zip(request, share_obj: ShareableLink, ids: list[str]) -> UserZIP:
    validate_ids_as_list(ids)

    user_zip = UserZIP.objects.create(owner=share_obj.owner)

    for item_id in ids:
        item = get_item(item_id)
        check_if_item_belongs_to_share(request, share_obj, item)
        check_resource_perms(request, item, [CheckTrash, CheckReady])

        if isinstance(item, Folder):
            user_zip.folders.add(item)
        else:
            user_zip.files.add(item)

    user_zip.save()
    return user_zip
