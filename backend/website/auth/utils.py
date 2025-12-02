from typing import Union

from ..core.dataModels.general import Item


def check_resource_perms(request, resource: Union[Item, dict], checks) -> None:
    for Check in checks:
        Check().check(request, resource)
