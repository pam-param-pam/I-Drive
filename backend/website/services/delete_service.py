from typing import Union

from django.utils import timezone

from website.core.dataModels.general import Item
from website.core.dataModels.http import RequestContext
from website.core.errors import BadRequestError
from website.core.helpers import get_attr
from website.models.delete_models import DeletionJob
from website.models.mixin_models import ItemState
from website.queries.selectors import check_if_bots_exists
from website.tasks.deleteTasks import plan_deletion_job


def delete_items(context: RequestContext, user, items: list[Union[Item, dict]]) -> None:
    check_if_bots_exists(context.get_user())

    ids = [get_attr(item, 'id') for item in items]

    for item in items:
        state = get_attr(item, 'state')
        if state != ItemState.ACTIVE:
            raise BadRequestError("Cannot delete. At least one item is not active.")

    job = DeletionJob.objects.create(
        requested_by=user,
        request_context=context.__json__(),
        requested_ids=ids,
        state=DeletionJob.State.PENDING,
        started_at=timezone.now(),
    )
    plan_deletion_job.delay(job.id)
