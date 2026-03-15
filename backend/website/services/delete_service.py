from typing import Union

from django.utils import timezone

from ..core.dataModels.general import Item
from ..core.errors import BadRequestError
from ..core.helpers import get_attr
from ..models.delete_models import DeletionJob
from ..models.mixin_models import ItemState
from ..queries.selectors import check_if_bots_exists
from ..core.dataModels.http import RequestContext
from ..tasks.deleteTasks import plan_deletion_job


def delete_items(context: RequestContext, user, items: list[Union[Item, dict]]) -> None:
    check_if_bots_exists(context.get_user())

    ids = [get_attr(item, 'id') for item in items]

    for item in items:
        state = get_attr(item, 'state')
        if state != ItemState.ACTIVE:
            raise BadRequestError("Cannot delete. At least one item is not ready.")

    job = DeletionJob.objects.create(
        requested_by=user,
        request_context=context.__json__(),
        requested_ids=ids,
        state=DeletionJob.State.PENDING,
        started_at=timezone.now(),
    )
    plan_deletion_job.delay(job.id)
