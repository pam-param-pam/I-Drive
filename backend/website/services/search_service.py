import re
from datetime import datetime, timedelta
from typing import Optional

from django.core.exceptions import BadRequest
from django.db.models.query_utils import Q
from django.http import JsonResponse

from ..core.Serializers import FileSerializer, FolderSerializer
from ..core.errors import BadRequestError
from ..core.helpers import validate_key, validate_ids_as_list
from ..core.validators.GeneralChecks import Min, Max, MaxLength
from ..models import File, Folder
from ..models.mixin_models import ItemState
from ..queries.builders import calculate_size

def validate_filter(f: Optional[dict]) -> Optional[dict]:
    ALLOWED_OPS = {
        "string": {"regex"},
        "number": {"between", "lt", "gt"},
        "date": {"between", "lt", "gt"},
    }

    ALLOWED_FIELDS = {
        "name": "string",
        "extension": "string",
        "size": "number",
        "created_at": "date",
        "last_modified_at": "date",
    }

    if f is None:
        return None

    if not isinstance(f, dict):
        raise BadRequestError("Filter must be an object.")

    field = f.get("field")
    op = f.get("op")
    value = f.get("value")

    if field not in ALLOWED_FIELDS:
        raise BadRequestError(f"Invalid filter field: {field}")

    field_type = ALLOWED_FIELDS[field]

    if op not in ALLOWED_OPS[field_type]:
        raise BadRequestError(f"Invalid operator '{op}' for field '{field}'")

    if field_type == "string":
        if not isinstance(value, str) or not value:
            raise BadRequestError("String filter requires non-empty string value")

        # optional: safe regex check
        if len(value) > 50:
            raise BadRequestError("Regex too long")

    elif field_type in ("number", "date"):
        if op in ("lt", "gt"):
            if not isinstance(value, (int, float, str)):
                raise BadRequestError("Invalid value for comparison filter")

        elif op == "between":
            if not isinstance(value, dict):
                raise BadRequestError("Between filter requires object value")

            if "from" not in value or "to" not in value:
                raise BadRequestError("Between requires both 'from' and 'to'")

            if value["from"] is None or value["to"] is None:
                raise BadRequestError("Between values cannot be null")

            if value["from"] > value["to"]:
                raise BadRequestError("'from' cannot be greater than 'to'")

    return {
        "field": field,
        "op": op,
        "value": value,
    }

def validate_search_request(data: dict) -> dict:
    out = {}

    # -----------------------------
    # Basic
    # -----------------------------
    out["query"] = validate_key(data, "query", str, required=False, default="", checks=[MaxLength(50)])
    out["files"] = validate_key(data, "files", bool, required=False, default=True)
    out["folders"] = validate_key(data, "folders", bool, required=False, default=True)
    out["type"] = validate_key(data, "type", str, required=False)

    if not out["files"] and not out["folders"]:
        raise BadRequestError("At least one of 'files' or 'folders' must be true.")

    # -----------------------------
    # Limits / sorting
    # -----------------------------
    out["resultLimit"] = validate_key(data, "resultLimit", int, required=False, default=100, checks=[Min(1), Max(1000)])

    order_by = validate_key(data, "orderBy", str, required=False, default="created_at")
    allowed_order_by = {"size", "created_at", "name"}

    if order_by not in allowed_order_by:
        raise BadRequestError(f"Order by must be one of: {allowed_order_by}")

    out["orderBy"] = order_by
    out["ascending"] = validate_key(data, "ascending", bool, required=False, default=True)

    # -----------------------------
    # Arrays
    # -----------------------------
    extensions = validate_key(data, "extensions", list, required=False, default=[])
    validate_ids_as_list(extensions, max_length=50, child_type=str, empty_allowed=True)

    tags = validate_key(data, "tags", list, required=False, default=[])
    validate_ids_as_list(tags, max_length=50, child_type=str, empty_allowed=True)

    limitToFolders = validate_key(data, "limitToFolders", list, required=False, default=[])
    validate_ids_as_list(limitToFolders, max_length=50, child_type=str, empty_allowed=True)

    excludeFolders = validate_key(data, "excludeFolders", list, required=False, default=[])
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
    out["filter"] = validate_filter(validate_key(data, "filter", dict, required=False))

    # -----------------------------
    # LOCK
    # -----------------------------
    out["lockFrom"] = validate_key(data, "lockFrom", str, required=False)
    out["password"] = validate_key(data, "password", str, required=False)

    # -----------------------------
    # CROSS-FIELD RULES (CRITICAL)
    # -----------------------------

    # Disable folders if file-specific filters present
    file_specific = (
        bool(out["extensions"]) or
        bool(out["tags"]) or
        bool(out["type"])
    )

    filter_field = out["filter"]["field"] if out["filter"] else None
    filter_is_file_only = filter_field in {"size", "extension"}

    if (file_specific or filter_is_file_only) and out["folders"]:
        raise BadRequestError("Folders is not allowed with these filters.")

    return out

def build_lock_q(lock_from, password):
    if lock_from and password:
        # access to specific locked subtree
        return (
            Q(lockFrom__isnull=True) |
            Q(lockFrom=lock_from, password=password)
        )
    else:
        # no access to locked content
        return Q(lockFrom__isnull=True)

def file_lock_q(lock_from, password):
    if lock_from and password:
        return (
            Q(parent__lockFrom__isnull=True) |
            Q(parent__lockFrom=lock_from, parent__password=password)
        )
    else:
        return Q(parent__lockFrom__isnull=True)

def folder_lock_q(lock_from, password):
    if lock_from and password:
        return (
            Q(lockFrom__isnull=True) |
            Q(lockFrom=lock_from, password=password) |
            Q(parent__lockFrom__isnull=True) |
            Q(parent__lockFrom=lock_from, parent__password=password)
        )
    else:
        return (
            Q(lockFrom__isnull=True) |
            Q(parent__lockFrom__isnull=True)
        )


def build_attr_filter(filter_obj):
    if not filter_obj:
        return None

    field = filter_obj.get("field")
    op = filter_obj.get("op")
    value = filter_obj.get("value")

    # -------------------------
    # whitelist fields
    # -------------------------
    FIELD_TYPES = {
        "name": "string",
        "extension": "string",
        "size": "number",
        "created_at": "date",
        "last_modified_at": "date",
    }

    if field not in FIELD_TYPES:
        raise BadRequest(f"Invalid filter field: {field}")

    field_type = FIELD_TYPES[field]

    # -------------------------
    # operator validation
    # -------------------------
    if field_type == "string":
        if op != "regex":
            raise BadRequest("String fields only support 'regex'")
    else:
        if op not in ("between", "lt", "gt"):
            raise BadRequest(f"Invalid op '{op}' for {field}")

    # -------------------------
    # build Q
    # -------------------------
    if field_type == "string":
        if not isinstance(value, str) or not value:
            raise BadRequest("Regex must be non-empty string")

        try:
            re.compile(value)
        except re.error:
            raise BadRequest("Invalid regex")

        return Q(**{f"{field}__regex": value})

    # -------------------------
    # number / date
    # -------------------------
    if op in ("lt", "gt"):
        if value is None:
            raise BadRequest("Value required")

        if field_type == "date":
            try:
                value = datetime.strptime(value, "%Y-%m-%d")
            except Exception:
                raise BadRequest("Invalid date format")
        else:
            try:
                value = float(value)
            except Exception:
                raise BadRequest("Invalid numeric value")

        lookup = "lt" if op == "lt" else "gt"
        return Q(**{f"{field}__{lookup}": value})

    if op == "between":
        if not isinstance(value, dict):
            raise BadRequest("Between requires dict")

        v_from = value.get("from")
        v_to = value.get("to")

        if v_from is None or v_to is None:
            raise BadRequest("Between requires both from/to")

        if field_type == "date":
            try:
                start = datetime.strptime(v_from, "%Y-%m-%d")
                end = datetime.strptime(v_to, "%Y-%m-%d")
            except Exception:
                raise BadRequest("Invalid date format")

            if start > end:
                raise BadRequest("from > to")

            return Q(**{f"{field}__gte": start}) & Q(**{f"{field}__lt": end + timedelta(days=1)})

        else:
            try:
                start = float(v_from)
                end = float(v_to)
            except Exception:
                raise BadRequest("Invalid numeric range")

            if start > end:
                raise BadRequest("from > to")

            return Q(**{f"{field}__range": (start, end)})

    return None

def perform_search(request):
    user = request.user
    validated = validate_search_request(request.data)

    query = validated["query"]
    include_files = validated["files"]
    include_folders = validated["folders"]

    lock_from = validated.get("lockFrom")
    password = validated.get("password")

    result_limit = validated["resultLimit"]
    order_by = validated["orderBy"]
    order_prefix = "" if validated["ascending"] else "-"

    base = Q(owner=user, state=ItemState.ACTIVE, inTrash=False, parent__inTrash=False)

    file_q = base & file_lock_q(lock_from, password)
    folder_q = base & folder_lock_q(lock_from, password)

    # ------------------------
    # query
    # ------------------------
    if query:
        file_q &= Q(name__icontains=query)
        folder_q &= Q(name__icontains=query)

    # ------------------------
    # FILE filters (already validated)
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
        file_q &= Q(parent__id__in=validated["limitToFolders"])
        folder_q &= Q(id__in=validated["limitToFolders"])

    if validated["excludeFolders"]:
        file_q &= ~Q(parent__id__in=validated["excludeFolders"])
        folder_q &= ~Q(id__in=validated["excludeFolders"])

    # ------------------------
    # Property filter
    # ------------------------
    attr_filter = build_attr_filter(validated["filter"])

    if attr_filter is not None:
        file_q &= attr_filter

        # folders only get safe subset
        if include_folders and validated["filter"]["field"] in {"name", "created_at", "last_modified_at"}:
            folder_q &= attr_filter

    # ------------------------
    # EXECUTION
    # ------------------------
    result = []

    if include_files:
        files = (
            File.objects.filter(file_q)
            .select_related("parent", "mediaposition", "thumbnail")
            .prefetch_related("tags")
            .order_by(f"{order_prefix}{order_by}")
            .annotate(**File.get_display_annotate())
            .values_list(*File.DISPLAY_VALUES)[:result_limit]
        )
        result.extend(FileSerializer.serialize_tuple(f) for f in files)

    if include_folders:
        folders = (
            Folder.objects.filter(folder_q)
            .select_related("parent")
            .order_by(f"{order_prefix}{order_by}")[:result_limit]
        )
        result.extend(FolderSerializer.serialize_object(f) for f in folders)

    return result
