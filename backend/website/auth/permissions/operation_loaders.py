from dataclasses import replace

from django.utils import timezone

from website.config import MAX_FILES_IN_FOLDER
from website.core.errors import BadRequestError, ResourceNotFoundError
from website.core.helpers import extract_key, validate_ids_as_list
from website.models import File, ShareableLink, UserSettings, UserZIP

from .contexts import AccessContext, ResourceRef, ResourceType, ZIPScope, as_items


def _refs(file_ids=None, folder_ids=None):
    files = file_ids if file_ids is not None else []
    folders = folder_ids if folder_ids is not None else []
    for ids in (files, folders):
        validate_ids_as_list(ids, max_length=MAX_FILES_IN_FOLDER, child_type=str, empty_allowed=True)
    if len(files) + len(folders) > MAX_FILES_IN_FOLDER:
        raise BadRequestError("Too many resources")
    return (*(ResourceRef(ResourceType.FILE, key) for key in files),
            *(ResourceRef(ResourceType.FOLDER, key) for key in folders))


def _get_share_metadata(token):
    share = ShareableLink.objects.filter(token=token).first()
    if share is None:
        raise ResourceNotFoundError()
    descendants = bool(UserSettings.objects.filter(user_id=share.owner_id)
                       .values_list("subfolders_in_shares", flat=True).first())
    return share, descendants


def _load_item(context, root_facts, item_facts, resources) -> AccessContext:
    request = context.request
    item_id = extract_key(request.params, "item_id")
    validate_ids_as_list([item_id], max_length=1, child_type=str)
    kind = request.get("resource_type")
    if kind is None:
        kind = ResourceType.FILE if File.objects.filter(owner_id=request.principal.user_id, id=item_id).exists() else ResourceType.FOLDER
    loaded = resources.load_many((ResourceRef(ResourceType(kind), item_id),), request.principal.user_id,
                                 request.get("locked_hierarchy"), locked_files=request.get("locked_files"),
                                 facts=item_facts)
    return replace(context, items=as_items(loaded))


def filter_items_loader(context, root_facts, item_facts, resources) -> AccessContext:
    request = context.request
    loaded = resources.load_many(_refs(request.get("file_ids"), request.get("folder_ids")),
                                 request.principal.user_id, request.get("locked_hierarchy"),
                                 locked_files=request.get("locked_files"), facts=item_facts)
    return replace(context, items=as_items(loaded))


def _load_selection(context, root_facts, item_facts, resources) -> AccessContext:
    request = context.request
    item_ids = request.get("item_ids", request.get("item_id"))
    validate_ids_as_list(item_ids, max_length=MAX_FILES_IN_FOLDER, child_type=str)
    loaded = resources.load_selection(request.principal.user_id, item_ids, facts=item_facts)
    return replace(context, items=as_items(loaded))


def user_resources_loader(context, root_facts, item_facts, resources) -> AccessContext:
    request = context.request
    selected = request.get("item_ids", request.get("item_id"))
    if isinstance(selected, (list, tuple)):
        return _load_selection(context, root_facts, item_facts, resources)
    if request.get("item_id") is not None:
        return _load_item(context, root_facts, item_facts, resources)
    return filter_items_loader(context, root_facts, item_facts, resources)


def move_loader(context, root_facts, item_facts, resources) -> AccessContext:
    request = context.request
    destination_id = extract_key(request.params, "destination_id")
    validate_ids_as_list([destination_id], max_length=1, child_type=str)
    if not destination_id:
        raise BadRequestError("A move requires a destination folder")
    destination = ResourceRef(ResourceType.FOLDER, destination_id)
    item_ids = request.get("item_ids")
    facts = root_facts | item_facts
    if item_ids is not None:
        validate_ids_as_list(item_ids, max_length=MAX_FILES_IN_FOLDER, child_type=str)
        loaded = resources.load_selection(request.principal.user_id, item_ids, destination, facts=facts)
    else:
        selected = _refs(request.get("file_ids"), request.get("folder_ids"))
        if not selected:
            raise BadRequestError("A move requires sources and a destination")
        loaded = resources.load_many((*selected, destination), request.principal.user_id,
                                     request.get("locked_hierarchy"), locked_files=request.get("locked_files"),
                                     facts=facts)
    return replace(context, root=as_items(loaded, (len(loaded.rows) - 1,)),
                         items=as_items(loaded, range(len(loaded.rows) - 1)))


def share_loader(context, root_facts, item_facts, resources) -> AccessContext:
    request = context.request
    share, descendants = _get_share_metadata(request.principal.share_token)
    return replace(context, data={**context.data, "share": share, "allow_descendants": descendants})


def share_resources_loader(context, root_facts, item_facts, resources) -> AccessContext:
    request = context.request
    share = context.data["share"]
    root = ResourceRef(ResourceType(share.get_type()), share.root_id)
    item_ids = request.get("item_ids")
    if item_ids is not None:
        validate_ids_as_list(item_ids, max_length=MAX_FILES_IN_FOLDER, child_type=str)
        loaded = resources.load_selection(share.owner_id, item_ids, root, facts=root_facts | item_facts)
        loaded.rows = (loaded.rows[-1], *loaded.rows[:-1])
        if loaded.resources:
            loaded.resources = (loaded.resources[-1], *loaded.resources[:-1])
    else:
        requested_type, requested_id = request.get("resource_type"), request.get("item_id")
        if request.get("folder_id") is not None:
            requested_type, requested_id = ResourceType.FOLDER, request.get("folder_id")
        if (requested_type is None) != (requested_id is None):
            raise BadRequestError("A share item requires both its type and ID")
        requested = request.get("requested")
        if "file_ids" in request.params or "folder_ids" in request.params:
            requested = _refs(request.get("file_ids"), request.get("folder_ids"))
            if not requested:
                raise BadRequestError("A selection cannot be empty")
        if requested is None:
            requested = (root,) if requested_id is None else (ResourceRef(ResourceType(requested_type), requested_id),)
        projected = request.get("projected", False) or "file_ids" in request.params or "folder_ids" in request.params
        loaded = resources.load_many((root, *requested), share.owner_id, projected=projected,
                                     facts=root_facts | item_facts)
    root_items = as_items(loaded, (0,))
    return replace(
        context,
        root=root_items,
        items=as_items(loaded, range(1, len(loaded.rows))),
        data={**context.data, "root_lock_id": root_items[0].state.lock_id},
    )


def trash_loader(context, root_facts, item_facts, resources) -> AccessContext:
    from website.queries.listing import load_trash_rows

    request = context.request
    files, folders = load_trash_rows(request.principal.user_id)
    loaded = resources.for_rows(_refs(list(files), list(folders)), request.principal.user_id,
                                files, folders, facts=item_facts)
    return replace(context, items=as_items(loaded))


def children_loader(context, root_facts, item_facts, resources) -> AccessContext:
    request = context.request
    loaded = resources.load_many((ResourceRef(ResourceType.FOLDER, extract_key(request.params, "folder_id")),),
                                 request.principal.user_id, projected=True, facts=root_facts)
    return replace(context, root=as_items(loaded))


def signed_file_loader(context, root_facts, item_facts, resources) -> AccessContext:
    request = context.request
    owner_id = File.objects.filter(id=request.principal.resource_id).values_list("owner_id", flat=True).first()
    if owner_id is None:
        raise ResourceNotFoundError()
    loaded = resources.load_many((ResourceRef(ResourceType.FILE, request.principal.resource_id),),
                                 owner_id, facts=item_facts)
    return replace(context, items=as_items(loaded), data={**context.data, "owner_id": owner_id})


def signed_zip_loader(context, root_facts, item_facts, resources) -> AccessContext:
    request = context.request
    record = UserZIP.objects.filter(id=request.principal.resource_id).first()
    if record is None:
        raise ResourceNotFoundError()
    loaded = resources.load_many(_refs(record.file_ids, record.folder_ids), record.owner_id,
                                 projected=True, facts=item_facts)
    if not loaded.rows:
        raise ResourceNotFoundError()
    now = timezone.now()
    scope = ZIPScope(str(record.id), record.owner_id, record.parent_id,
                     {(row["kind"], row["id"]) for row in loaded.rows},
                     {row["id"]: loaded.state(row).lock_id for row in loaded.rows if row["kind"] == "folder"}, now)
    return replace(context, items=as_items(loaded), data={**context.data, "record": record, "scope": scope})


def zip_items_loader(context, root_facts, item_facts, resources) -> AccessContext:
    request = context.request
    scope = request.params["scope"]
    loaded = resources.load_many(_refs(request.get("file_ids"), request.get("folder_ids")),
                                 scope.owner_id, projected=True, facts=item_facts)
    return replace(context, items=as_items(loaded), data={**context.data, "scope": scope})


def download_children_root_loader(context, root_facts, item_facts, resources) -> AccessContext:
    request = context.request
    root_id = extract_key(request.params, "root_id")
    root = resources.load_many((ResourceRef(ResourceType.FOLDER, root_id),), request.principal.user_id,
                               projected=True, facts=root_facts)
    return replace(context, root=as_items(root))


def download_children_loader(context, root_facts, item_facts, resources) -> AccessContext:
    request = context.request
    candidates = resources.load_many(_refs(request.get("file_ids"), request.get("folder_ids")),
                                     request.principal.user_id, projected=True, facts=item_facts)
    return replace(context, items=as_items(candidates))
