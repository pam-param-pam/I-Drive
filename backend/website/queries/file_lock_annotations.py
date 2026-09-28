from django.db.models import BooleanField, CharField, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce

from website.config import MAX_FOLDER_DEPTH
from website.models import FolderLockPolicy


def file_lock_annotations() -> dict:
    return _lock_annotations("parent")


def folder_lock_annotations() -> dict:
    return _lock_annotations("")


def _lock_annotations(base_path: str) -> dict:
    if base_path:
        parent_paths = [base_path + "__parent" * depth for depth in range(MAX_FOLDER_DEPTH + 1)]
    else:
        parent_paths = [""] + ["parent" + "__parent" * depth for depth in range(MAX_FOLDER_DEPTH)]

    policy_ids = [
        Subquery(
            FolderLockPolicy.objects.filter(
                owner_id=OuterRef("owner_id"),
                folder_id=OuterRef(f"{path}__id" if path else "id"),
            ).values("folder_id")[:1]
        )
        for path in parent_paths
    ]
    policy_names = [
        Subquery(
            FolderLockPolicy.objects.filter(
                owner_id=OuterRef("owner_id"),
                folder_id=OuterRef(f"{path}__id" if path else "id"),
            ).values("folder__name")[:1]
        )
        for path in parent_paths
    ]
    policy_presence = [
        Subquery(
            FolderLockPolicy.objects.filter(
                owner_id=OuterRef("owner_id"),
                folder_id=OuterRef(f"{path}__id" if path else "id"),
            ).annotate(has_policy=Value(True, output_field=BooleanField())).values("has_policy")[:1]
        )
        for path in parent_paths
    ]

    return {
        "is_locked": Coalesce(*policy_presence, Value(False), output_field=BooleanField()),
        "lock_from_id": Coalesce(*policy_ids, output_field=CharField(max_length=22)),
        "lock_from_name": Coalesce(*policy_names, output_field=CharField(max_length=100)),
    }
