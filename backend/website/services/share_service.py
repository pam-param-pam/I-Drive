from datetime import timedelta

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from user_agents import parse as parse_ua

from ..auth.Permissions import CheckTrash, CheckState
from ..auth.utils import check_resource_perms
from ..constants import ShareEventType
from ..core.dataModels.general import Item
from ..core.dataModels.http import ShareContext
from ..core.errors import BadRequestError
from ..core.helpers import validate_ids_as_list, validate_value, get_ip
from ..core.validators.GeneralChecks import IsPositive, MaxLength, NotEmpty
from ..models import ShareableLink, UserZIP, Folder, ShareAccessEvent
from ..queries.selectors import check_if_item_belongs_to_share, get_item


def create_share(user: User, item_obj: Item, unit: str, value: int, password: str) -> ShareableLink:
    validate_value(value, int, checks=[IsPositive])
    validate_value(password, int, checks=[NotEmpty, MaxLength(100)])

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
        password=password,
    )

    return share


def delete_share(share: ShareableLink) -> None:
    share.delete()

# todo why does this check perms...
def create_share_zip(request, share_obj: ShareableLink, ids: list[str]) -> UserZIP:
    validate_ids_as_list(ids)

    user_zip = UserZIP.objects.create(owner=share_obj.owner)  # todo, this is weird, owner != share viewer

    for item_id in ids:
        item = get_item(item_id)
        check_if_item_belongs_to_share(share_obj, item)
        check_resource_perms(request, item, [CheckTrash, CheckState])

        if isinstance(item, Folder):
            user_zip.folders.add(item)
        else:
            user_zip.files.add(item)

    user_zip.save()
    return user_zip


def log_event_http(request, share: ShareableLink, event_type: ShareEventType, **metadata):
    ip, _ = get_ip(request)
    user_agent = request.user_agent
    user = request.user if request.user.is_authenticated else None

    context = ShareContext(ip=ip, user_agent=user_agent, user=user)
    ShareAccessEvent.log(share, context, event_type, **metadata)

def log_event_websocket(scope, share: ShareableLink, event_type: ShareEventType, **metadata):
    # IP address
    ip, _ = scope.get("client", ("", None))

    # Headers are list[(bytes, bytes)]
    headers = dict(scope.get("headers", []))
    ua_string = headers.get(b"user-agent", b"").decode()
    user_agent = parse_ua(ua_string)

    # Authenticated user (if middleware installed)
    user = scope.get("user")
    if user and not user.is_authenticated:
        user = None

    context = ShareContext(ip=ip, user_agent=user_agent, user=user)
    ShareAccessEvent.log(share, context, event_type, **metadata)
