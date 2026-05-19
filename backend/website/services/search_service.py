import re
from datetime import datetime, timedelta

from django.core.exceptions import BadRequest
from django.db.models.query_utils import Q
from django.http import JsonResponse

from ..core.Serializers import FileSerializer, FolderSerializer
from ..core.errors import BadRequestError
from ..core.helpers import validate_key, validate_ids_as_list
from ..core.validators.GeneralChecks import Min, Max
from ..models import File, Folder
from ..models.mixin_models import ItemState
from ..queries.builders import calculate_size


def validate_search_request(data: dict) -> dict:
    out = {}

    # -----------------------------
    # Basic
    # -----------------------------
    out["query"] = validate_key(data, "query", str, required=False, default="")
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
    allowed_order_by = {"size", "created_at", "name", "duration"}

    if order_by not in allowed_order_by:
        raise BadRequestError(f"Order by must one one of: {allowed_order_by}")

    out["orderBy"] = order_by

    out["ascending"] = validate_key(data, "ascending", bool, required=False, default=True)

    # -----------------------------
    # Arrays
    # -----------------------------
    extensions = validate_key(data, "extensions", list, required=False, default=[])
    validate_ids_as_list(extensions, max_length=50)

    tags = validate_key(data, "tags", list, required=False, default=[])
    validate_ids_as_list(tags, max_length=50)

    limitToFolders = validate_key(data, "limitToFolders", list, required=False, default=[])
    validate_ids_as_list(limitToFolders, max_length=50)

    excludeFolders = validate_key(data, "excludeFolders", list, required=False, default=[])
    validate_ids_as_list(excludeFolders, max_length=50)

    if set(limitToFolders) & set(excludeFolders):
        raise BadRequestError("limitToFolders and excludeFolders overlap.")

    out["extensions"] = extensions
    out["tags"] = tags
    out["limitToFolders"] = limitToFolders
    out["excludeFolders"] = excludeFolders

    # -----------------------------
    # Filter
    # -----------------------------
    out["filter"] = validate_filter(validate_key(data, "filter", dict, required=False, default=None))

    return out

def perform_search(request):
    # todo fix this
    user = request.user
    data = request.data

    # Basic parameters
    query = data.get('query')
    file_type = data.get('type')
    extension = data.get('extension')

    lock_from = data.get('lockFrom')
    password = request.headers.get("X-resource-Password")  # keep header for password security

    # Tags: array of objects -> list of tag names
    tags_include = data.get('tagsInclude', [])
    if tags_include:
        tags = [tag['name'] for tag in tags_include]
    else:
        tags = None

    # Folder filters: arrays of objects -> extract IDs
    limit_to_folders = data.get('limitToFolders', [])
    exclude_folders = data.get('excludeFolders', [])

    if limit_to_folders:
        limit_folder_ids = [f['id'] for f in limit_to_folders]
    else:
        limit_folder_ids = []

    if exclude_folders:
        exclude_folder_ids = [f['id'] for f in exclude_folders]
    else:
        exclude_folder_ids = []

    # Ordering
    order_by = data.get('orderBy', 'created_at')
    if order_by not in ('size', 'created_at', 'name'):
        order_by = 'created_at'
    ascending = data.get('ascending', True)
    order_prefix = "" if ascending else "-"

    # Result limits
    result_limit = min(int(data.get('resultLimit', 100)), 1000)
    include_files = data.get('files', True)
    include_folders = data.get('folders', True)

    # Property filter
    filter_obj = data.get('filter')
    if filter_obj:
        # Validate both field and op/value are present
        if not filter_obj.get('field') or not filter_obj.get('op'):
            raise BadRequest("Both property and filter parameters must be specified.")
        attribute = filter_obj['field']
        op = filter_obj['op']
        value = filter_obj.get('value')

        if op not in ('regex', 'between', 'lt', 'gt'):
            raise BadRequest(f"Invalid filter operation: {op}")

        # Map field to model field type
        allowed_fields = {
            'name': 'string',
            'extension': 'string',
            'size': 'number',
            'duration': 'duration',
            'created_at': 'date',
            'last_modified_at': 'date',
        }
        if attribute not in allowed_fields:
            raise BadRequest(f"Invalid property: {attribute}")

        field_type = allowed_fields[attribute]
        if field_type == 'string' and op != 'regex':
            raise BadRequest("String properties only support 'regex' operation.")
        if field_type == 'number' and op not in ('between', 'lt', 'gt'):
            raise BadRequest("Number properties only support 'between', 'lt', or 'gt'.")
        if field_type == 'date' and op not in ('between', 'lt', 'gt'):
            raise BadRequest("Date properties only support 'between', 'lt', or 'gt'.")

        # Build the Q object based on op and value
        if op == 'regex':
            if not isinstance(value, str):
                raise BadRequest("Regex value must be a string.")
            try:
                re.compile(value)
                attr_filter = Q(**{f"{attribute}__regex": value})
            except re.error:
                raise BadRequest("Invalid regex pattern.")
        else:
            # Numeric or date operations
            if op in ('lt', 'gt'):
                if value is None:
                    raise BadRequest("A value is required for 'lt'/'gt' operations.")
                try:
                    numeric_value = float(value) if field_type == 'number' else None
                except (ValueError, TypeError):
                    raise BadRequest("Invalid numeric value.")
                if field_type == 'date':
                    try:
                        date_value = datetime.strptime(value, "%Y-%m-%d")
                    except ValueError:
                        raise BadRequest("Invalid date format. Use YYYY-MM-DD.")
                    if op == 'lt':
                        attr_filter = Q(**{f"{attribute}__lt": date_value})
                    else:  # 'gt'
                        attr_filter = Q(**{f"{attribute}__gt": date_value})
                else:  # number
                    if op == 'lt':
                        attr_filter = Q(**{f"{attribute}__lt": numeric_value})
                    else:
                        attr_filter = Q(**{f"{attribute}__gt": numeric_value})
            elif op == 'between':
                if not isinstance(value, dict) or 'from' not in value or 'to' not in value:
                    raise BadRequest("'between' requires a dict with 'from' and 'to'.")
                from_val = value['from']
                to_val = value['to']
                if field_type == 'date':
                    try:
                        start = datetime.strptime(from_val, "%Y-%m-%d")
                        end = datetime.strptime(to_val, "%Y-%m-%d")
                    except ValueError:
                        raise BadRequest("Invalid date format. Use YYYY-MM-DD.")
                    attr_filter = Q(**{f"{attribute}__gte": start}) & Q(**{f"{attribute}__lt": end + timedelta(days=1)})
                else:  # number
                    try:
                        from_num = float(from_val)
                        to_num = float(to_val)
                    except (ValueError, TypeError):
                        raise BadRequest("Invalid numeric values in range.")
                    attr_filter = Q(**{f"{attribute}__range": (from_num, to_num)})
    else:
        attribute = None
        attr_filter = Q()

    # ------------------------------------------------------------------
    # Base querysets for files and folders
    file_base = Q(owner=user, state=ItemState.ACTIVE, inTrash=False, parent__inTrash=False)
    folder_base = Q(owner=user, state=ItemState.ACTIVE, inTrash=False, parent__inTrash=False)

    # ------------------------------------------------------------------
    # Lock / password handling
    if lock_from and password:
        # Password provided – include matching locked folders and their subtree
        file_base &= Q(
            Q(parent__lockFrom__isnull=True, parent__password__isnull=True) |
            Q(parent__lockFrom=lock_from, parent__password=password)
        )
        folder_base &= Q(
            Q(lockFrom__isnull=True, password__isnull=True) |
            Q(lockFrom=lock_from, password=password) |
            Q(parent__lockFrom=lock_from, parent__password=password)
        )
    else:
        # No password: show only unlocked items + top-level locked folders (no subfolders)
        file_base &= Q(parent__lockFrom__isnull=True, parent__password__isnull=True)
        folder_base &= Q(
            Q(lockFrom__isnull=True, password__isnull=True) |
            Q(lockFrom__isnull=False, parent__isnull=True)  # top-level locked folders
        )

    # ------------------------------------------------------------------
    # Search query
    if query:
        file_base &= Q(name__icontains=query)
        folder_base &= Q(name__icontains=query)

    if file_type:
        file_base &= Q(type=file_type)

    if extension:
        file_base &= Q(extension=extension)

    if tags:
        file_base &= Q(tags__name__in=tags)

    # Property filter
    if attribute:
        file_base &= attr_filter
        folder_base &= attr_filter

    # Exclude folders
    if exclude_folder_ids:
        file_base &= ~Q(parent__id__in=exclude_folder_ids)
        folder_base &= ~Q(id__in=exclude_folder_ids)

    # Limit to folders
    if limit_folder_ids:
        file_base &= Q(parent__id__in=limit_folder_ids)
        folder_base &= Q(id__in=limit_folder_ids)

    # ------------------------------------------------------------------
    # Execute queries
    files = []
    folders = []

    if include_files:
        files = File.objects.filter(file_base) \
            .select_related("parent", "mediaposition", "thumbnail") \
            .prefetch_related("tags") \
            .order_by(f"{order_prefix}{order_by}") \
            .annotate(**File.get_display_annotate()) \
            .values_list(*File.DISPLAY_VALUES)[:result_limit]

    if include_folders:
        folders_qs = Folder.objects.filter(folder_base) \
            .select_related("parent") \
            .order_by("-created_at")[:result_limit]

        if order_by == 'size':
            # Sort by calculated size (client‑side sort after fetching)
            folders_list = list(folders_qs)
            folders_list.sort(key=calculate_size, reverse=(order_prefix == "-"))
            folders = folders_list[:result_limit]
        else:
            folders = folders_qs

    # Serialize
    folder_dicts = []
    file_dicts = []

    if include_folders and not (extension or file_type):
        for folder in folders:
            folder_dicts.append(FolderSerializer.serialize_object(folder))

    if include_files:
        file_dicts = [FileSerializer.serialize_tuple(file) for file in files]

    return JsonResponse(file_dicts + folder_dicts, safe=False)