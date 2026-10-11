import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.utils import timezone
from django.db.models.query_utils import Q

from website.queries.display import load_file_displays, load_folder_displays
from website.core.Serializers import FileSerializer, FolderSerializer
from website.core.errors import BadRequestError
from website.core.helpers import validate_key, validate_ids_as_list
from website.core.validators.GeneralChecks import MaxLength, Max, Min
from website.models import Folder, File
from website.queries.hierarchy import get_descendant_folder_ids
from website.auth.permissions import (
    CredentialSet, ResourceAction, ResourceType, UserPrincipal)
from website.auth.permissions.engine import permissions


_FILTER_FIELDS = {
    "name": "string", "extension": "string", "size": "number",
    "created_at": "date", "last_modified_at": "date",
}
_FILTER_OPERATORS = {
    "string": {"regex"}, "number": {"between", "lt", "gt"},
    "date": {"between", "lt", "gt"},
}


@dataclass(frozen=True)
class SearchFilter:
    field: str
    op: str
    value: str | float | datetime | tuple[float, float] | tuple[datetime, datetime]


def _normalize_filter_value(value, field_type: str):
    if field_type == "date":
        if not isinstance(value, str):
            raise BadRequestError("Date filters require YYYY-MM-DD strings")
        try:
            parsed = datetime.strptime(value, "%Y-%m-%d")
        except ValueError as exception:
            raise BadRequestError("Invalid date format") from exception
        return timezone.make_aware(parsed, timezone.get_current_timezone())
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise BadRequestError("Invalid numeric value")
    try:
        number = float(value)
    except (ValueError, OverflowError) as exception:
        raise BadRequestError("Invalid numeric value") from exception
    if not math.isfinite(number):
        raise BadRequestError("Numeric filters require finite values")
    return number


def validate_filter(raw: dict | None) -> SearchFilter | None:
    """Validate and normalize once, before comparing bounds or building SQL."""
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise BadRequestError("Filter must be an object")
    field, op, value = raw.get("field"), raw.get("op"), raw.get("value")
    if not isinstance(field, str) or field not in _FILTER_FIELDS:
        raise BadRequestError(f"Invalid filter field: {field}")
    field_type = _FILTER_FIELDS[field]
    if not isinstance(op, str) or op not in _FILTER_OPERATORS[field_type]:
        raise BadRequestError(f"Invalid operator '{op}' for field '{field}'")
    if field_type == "string":
        if not isinstance(value, str) or not value:
            raise BadRequestError("String filter requires non-empty string value")
        if len(value) > 50:
            raise BadRequestError("Regex too long")
        try:
            re.compile(value)
        except re.error as exception:
            raise BadRequestError("Invalid regex") from exception
    elif op == "between":
        if not isinstance(value, dict) or "from" not in value or "to" not in value:
            raise BadRequestError("Between requires both 'from' and 'to'")
        start = _normalize_filter_value(value["from"], field_type)
        end = _normalize_filter_value(value["to"], field_type)
        if start > end:
            raise BadRequestError("'from' cannot be greater than 'to'")
        if field_type == "date":
            try:
                end += timedelta(days=1)
            except OverflowError as exception:
                raise BadRequestError("Date range end is too large") from exception
        value = (start, end)
    else:
        value = _normalize_filter_value(value, field_type)
    return SearchFilter(field, op, value)


def validate_search_request(data: dict) -> dict:
    out = {}

    # -----------------------------
    # Basic
    # -----------------------------
    out["query"] = validate_key(data, "query", str, default="", checks=[MaxLength(50)])
    out["files"] = validate_key(data, "files", bool, default=True)
    out["folders"] = validate_key(data, "folders", bool, default=True)
    out["type"] = validate_key(data, "type", str, default=None)

    if not out["files"] and not out["folders"]:
        raise BadRequestError("At least one of 'files' or 'folders' must be true.")

    # -----------------------------
    # Limits / sorting
    # -----------------------------
    out["resultLimit"] = validate_key(data, "resultLimit", int, default=100, checks=[Min(1), Max(1000)])

    order_by = validate_key(data, "orderBy", str, default="created_at")
    allowed_order_by = {"size", "created_at", "name"}

    if order_by not in allowed_order_by:
        raise BadRequestError(f"Order by must be one of: {allowed_order_by}")

    out["orderBy"] = order_by
    out["ascending"] = validate_key(data, "ascending", bool, default=True)

    # -----------------------------
    # Arrays
    # -----------------------------
    extensions = validate_key(data, "extensions", list, default=[])
    validate_ids_as_list(extensions, max_length=50, child_type=str, empty_allowed=True)

    tags = validate_key(data, "tags", list, default=[])
    validate_ids_as_list(tags, max_length=50, child_type=str, empty_allowed=True)

    limitToFolders = validate_key(data, "limitToFolders", list, default=[])
    validate_ids_as_list(limitToFolders, max_length=50, child_type=str, empty_allowed=True)

    excludeFolders = validate_key(data, "excludeFolders", list, default=[])
    validate_ids_as_list(excludeFolders, max_length=50, child_type=str, empty_allowed=True)

    if set(limitToFolders) & set(excludeFolders):
        raise BadRequestError("limitToFolders and excludeFolders overlap.")

    out["extensions"] = extensions
    out["tags"] = tags
    out["limitToFolders"] = limitToFolders
    out["excludeFolders"] = excludeFolders

    # -----------------------------
    # Filter
    # -----------------------------
    out["filter"] = validate_filter(validate_key(data, "filter", dict, default=None))

    # -----------------------------
    # CROSS-FIELD RULES
    # -----------------------------

    # Disable folders if file-specific filters present
    file_specific = (
        bool(out["extensions"]) or
        bool(out["tags"]) or
        bool(out["type"])
    )

    filter_field = out["filter"].field if out["filter"] else None
    filter_is_file_only = filter_field in {"size", "extension"}

    if (file_specific or filter_is_file_only) and out["folders"]:
        raise BadRequestError("Folders is not allowed with these filters.")

    return out

def build_attr_filter(filter_obj: SearchFilter | None) -> Q | None:
    """Compile a normalized filter; raw input validation belongs above."""
    if filter_obj is None:
        return None
    if filter_obj.op == "between":
        start, end = filter_obj.value
        if isinstance(start, datetime):
            return Q(**{f"{filter_obj.field}__gte": start, f"{filter_obj.field}__lt": end})
        return Q(**{f"{filter_obj.field}__range": (start, end)})
    return Q(**{f"{filter_obj.field}__{filter_obj.op}": filter_obj.value})


def perform_search(principal: UserPrincipal, data: dict, credentials: CredentialSet | None = None):
    validated = validate_search_request(data)

    query = validated["query"]
    include_files = validated["files"]
    include_folders = validated["folders"]

    result_limit = validated["resultLimit"]
    order_by = validated["orderBy"]
    order_prefix = "" if validated["ascending"] else "-"

    file_q = Q(owner_id=principal.user_id)
    folder_q = Q(owner_id=principal.user_id)

    # ------------------------
    # query
    # ------------------------
    if query:
        file_q &= Q(name__icontains=query)
        folder_q &= Q(name__icontains=query)

    # ------------------------
    # FILE filters
    # ------------------------
    if include_files:
        if validated["type"]:
            file_q &= Q(type=validated["type"])

        if validated["extensions"]:
            file_q &= Q(extension__in=validated["extensions"])

        if validated["tags"]:
            file_q &= Q(tags__id__in=validated["tags"])

    # ------------------------
    # Folder scope filters
    # ------------------------
    if validated["limitToFolders"]:
        subtree_ids = get_descendant_folder_ids(validated["limitToFolders"])
        folder_q &= Q(id__in=subtree_ids)
        file_q &= Q(parent_id__in=subtree_ids)

    if validated["excludeFolders"]:
        subtree_ids = get_descendant_folder_ids(validated["excludeFolders"])
        folder_q &= ~Q(id__in=subtree_ids)
        file_q &= ~Q(parent_id__in=subtree_ids)

    # ------------------------
    # Property filter
    # ------------------------
    attr_filter = build_attr_filter(validated["filter"])

    if attr_filter is not None:
        if include_files:
            file_q &= attr_filter

        # folders only get safe subset
        if include_folders and validated["filter"].field in {"name", "created_at", "last_modified_at"}:
            folder_q &= attr_filter

    # ------------------------
    # EXECUTION
    # ------------------------
    candidate_limit = min(result_limit * 4, 4000)
    file_candidate_ids = list(
        File.objects.filter(file_q).distinct()
        .order_by(f"{order_prefix}{order_by}")
        .values_list("id", flat=True)[:candidate_limit]
    ) if include_files else []
    folder_candidate_ids = list(
        Folder.objects.filter(folder_q).distinct()
        .order_by(f"{order_prefix}{order_by}")
        .values_list("id", flat=True)[:candidate_limit]
    ) if include_folders else []

    visible = tuple(item.resource for item in permissions.authorize(
        ResourceAction.SEARCH, principal, file_ids=file_candidate_ids,
        folder_ids=folder_candidate_ids, credentials=credentials,
    ).items)
    authorized_files = {str(item.id) for item in visible if isinstance(item, File)}
    authorized_folders = {str(item.id) for item in visible if isinstance(item, Folder)}

    result = []
    if include_files and authorized_files:
        files = list(
            File.objects.filter(id__in=authorized_files)
            .order_by(f"{order_prefix}{order_by}")
            [:result_limit]
        )
        result.extend(FileSerializer.serialize_many(load_file_displays(files)))

    if include_folders and authorized_folders:
        folders = (
            Folder.objects.filter(id__in=authorized_folders)
            .select_related("parent")
            .order_by(f"{order_prefix}{order_by}")[:result_limit]
        )
        result.extend(FolderSerializer.serialize_many(load_folder_displays(folders)))

    return result
