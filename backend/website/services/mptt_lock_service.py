from collections.abc import Iterable

from django.db import connection
from django.db.transaction import TransactionManagementError

from website.models import Folder


# There is no root row to lock while a new MPTT tree is being created.
# Serialize only that operation with a transaction-scoped PostgreSQL lock.
_ROOT_CREATION_ADVISORY_LOCK_ID = 4_912_244_839_130


def lock_mptt_trees(folders: Iterable[Folder] = (), creating_root: bool = False) -> list[Folder]:
    """Lock the roots for MPTT structural writes in a deterministic order."""
    if not connection.in_atomic_block:
        raise TransactionManagementError("MPTT tree locks require transaction.atomic()")

    if creating_root:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_advisory_xact_lock(%s)",
                [_ROOT_CREATION_ADVISORY_LOCK_ID],
            )

    folder_ids = {folder.pk for folder in folders if folder.pk is not None}
    if not folder_ids:
        return []

    folder_rows = list(
        Folder.objects
        .filter(pk__in=folder_ids)
        .values_list("pk", "tree_id")
    )
    if len(folder_rows) != len(folder_ids):
        raise Folder.DoesNotExist("A folder disappeared while acquiring its MPTT tree lock")

    initial_tree_ids = {tree_id for _, tree_id in folder_rows}
    roots = list(
        Folder.objects
        .select_for_update()
        .filter(tree_id__in=initial_tree_ids, level=0)
        .order_by("tree_id", "pk")
    )

    if len(roots) != len(initial_tree_ids):
        raise RuntimeError("Invalid MPTT tree: expected exactly one root per tree")

    # A cross-tree move may have completed while this transaction waited for
    # the old root. Refuse to continue without the new tree's lock.
    current_rows = list(
        Folder.objects
        .filter(pk__in=folder_ids)
        .values_list("pk", "tree_id")
    )
    if len(current_rows) != len(folder_ids):
        raise Folder.DoesNotExist("A folder disappeared while acquiring its MPTT tree lock")

    current_tree_ids = {tree_id for _, tree_id in current_rows}
    if current_tree_ids != initial_tree_ids:
        raise RuntimeError("A folder changed trees while its MPTT lock was being acquired")

    return roots
