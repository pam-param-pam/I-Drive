from dataclasses import dataclass

from django.db import connection

from website.auth.permissions.contexts import FolderState, ResourceContext, ResourceRef, ResourceType, Fact
from website.config import MAX_FILES_IN_FOLDER
from website.core.errors import BadRequestError, ResourceNotFoundError
from website.models import File, Folder
from .resource_facts import FOLDER_FIELDS, build_states, load_ancestors


FILE_FIELDS = FOLDER_FIELDS + ("size", "crc", "encryption_method", "key", "iv")
ALL_FACTS = frozenset(Fact)


def _row(resource, kind):
    fields = FILE_FIELDS if kind == "file" else FOLDER_FIELDS
    row = {field: getattr(resource, field) for field in fields}
    return _normalize(row, kind)


def _normalize(row, kind):
    row["id"] = str(row["id"])
    row["parent_id"] = str(row["parent_id"]) if row["parent_id"] is not None else None
    row["kind"] = kind
    return row


@dataclass
class LoadedResources:
    rows: tuple[dict, ...]
    states: dict[str, FolderState]
    ancestors: dict[str, dict]
    resources: tuple = ()

    def state(self, row):
        return self.states[row["id"] if row["kind"] == "folder" else row["parent_id"]]

    def context(self, row):
        state = self.state(row)
        return ResourceContext(
            ResourceType(row["kind"]), row["id"], row["owner_id"], row["parent_id"],
            row["state"], row["kind"] == "folder" and row["parent_id"] is None,
            row["explicit_trash_root"],
            row["id"] if row["explicit_trash_root"] else state.trash_root_id,
            row["id"] if row["state"] == "deleting" else state.deleting_root_id,
            state.lock_id, state.lock_name, state.lock_password, row["resource_version"], state.ancestor_ids,
        )


class ResourceLoader:
    def resolve_file(self, file_id, owner_id, locked_hierarchy=None, locked_files=None):
        return self.resolve_many(
            (ResourceRef(ResourceType.FILE, file_id),), owner_id, locked_hierarchy, locked_files,
        )[0]

    def resolve_folder(self, folder_id, owner_id, locked_hierarchy=None):
        return self.resolve_many((ResourceRef(ResourceType.FOLDER, folder_id),), owner_id, locked_hierarchy)[0]

    def resolve_many(self, refs, owner_id, locked_hierarchy=None, locked_files=None):
        loaded = self.load_many(
            refs, owner_id, locked_hierarchy, locked_files=locked_files, projected=True,
        )
        return tuple(loaded.context(row) for row in loaded.rows)

    def load_many(self, refs, owner_id, locked_hierarchy=None, *, locked_files=None, projected=False, facts=None):
        refs = tuple(refs)
        if len(refs) > MAX_FILES_IN_FOLDER + 1:
            raise BadRequestError("Too many resource references")
        if (locked_hierarchy is not None or locked_files is not None) and not connection.in_atomic_block:
            raise RuntimeError("A locked hierarchy requires its active transaction")
        file_ids = {ref.resource_id for ref in refs if ref.resource_type == ResourceType.FILE}
        folder_ids = {ref.resource_id for ref in refs if ref.resource_type == ResourceType.FOLDER}
        files, folders, models = {}, {}, {}
        for model, kind, ids, fields, output in (
            (File, "file", file_ids, FILE_FIELDS, files),
            (Folder, "folder", folder_ids, FOLDER_FIELDS, folders),
        ):
            if not ids:
                continue
            if model is File and locked_files is not None:
                records = [obj for key, obj in locked_files.items() if key in ids and obj.owner_id == owner_id]
                for obj in records:
                    output[str(obj.id)] = _row(obj, kind)
                    models[(kind, str(obj.id))] = obj
            elif model is Folder and locked_hierarchy is not None:
                records = [obj for key, obj in locked_hierarchy.folders.items() if key in ids and obj.owner_id == owner_id]
                for obj in records:
                    output[str(obj.id)] = _row(obj, kind)
                    models[(kind, str(obj.id))] = obj
            elif projected:
                output.update((str(row["id"]), _normalize(row, kind)) for row in
                              model.objects.filter(owner_id=owner_id, id__in=ids).values(*fields))
            else:
                for obj in model.objects.filter(owner_id=owner_id, id__in=ids).select_related("owner", "parent"):
                    output[str(obj.id)] = _row(obj, kind)
                    models[(kind, str(obj.id))] = obj
        if set(files) != file_ids or set(folders) != folder_ids:
            raise ResourceNotFoundError()
        loaded = self.for_rows(refs, owner_id, files, folders, locked_hierarchy, facts=facts)
        if not projected:
            loaded.resources = tuple(models[(ref.resource_type.value, ref.resource_id)] for ref in refs)
        return loaded

    def load_selection(self, owner_id, item_ids, extra=None, *, facts=None):
        """Classify a mixed projected selection for the permission engine."""
        files = {str(row["id"]): _normalize(row, "file") for row in
                 File.objects.filter(owner_id=owner_id, id__in=item_ids).values(*FILE_FIELDS)}
        folders = {str(row["id"]): _normalize(row, "folder") for row in
                   Folder.objects.filter(owner_id=owner_id, id__in=item_ids).values(*FOLDER_FIELDS)}
        if len(files) + len(folders) != len(item_ids) or set(files) & set(folders):
            raise ResourceNotFoundError()
        refs = tuple(ResourceRef(ResourceType.FILE if key in files else ResourceType.FOLDER, key) for key in item_ids)
        if extra is not None:
            model, fields, target = ((Folder, FOLDER_FIELDS, folders) if extra.resource_type == ResourceType.FOLDER
                                     else (File, FILE_FIELDS, files))
            if extra.resource_id not in target:
                row = model.objects.filter(owner_id=owner_id, id=extra.resource_id).values(*fields).first()
                if row is None:
                    raise ResourceNotFoundError()
                target[extra.resource_id] = _normalize(row, extra.resource_type.value)
            refs += (extra,)
        return self.for_rows(refs, owner_id, files, folders, facts=facts)

    def for_rows(self, refs, owner_id, files, folders, locked_hierarchy=None, *, facts=None):
        """Resolve ancestry once per distinct parent, without per-file contexts."""
        if locked_hierarchy is not None and not connection.in_atomic_block:
            raise RuntimeError("A locked hierarchy requires its active transaction")
        facts = ALL_FACTS if facts is None else frozenset(facts)
        needs_ancestors = bool(facts & {Fact.ANCESTORS, Fact.TRASH, Fact.DELETION, Fact.LOCK})
        ancestors = dict(folders)
        if locked_hierarchy is not None:
            ancestors.update((key, _row(value, "folder")) for key, value in locked_hierarchy.folders.items())
        starts = {ref.resource_id if ref.resource_type == ResourceType.FOLDER
                  else files[ref.resource_id]["parent_id"] for ref in refs}
        if needs_ancestors:
            ancestors = load_ancestors(starts, ancestors, owner_id, locked_hierarchy, _normalize)
        if any(row["owner_id"] != owner_id for row in (*ancestors.values(), *files.values())):
            raise ResourceNotFoundError()

        states = build_states(starts, ancestors, facts, owner_id)
        trash = {key for key, row in ancestors.items() if row["trashed_at"] is not None} if Fact.TRASH in facts else set()
        for row in files.values():
            row["explicit_trash_root"] = row["trashed_at"] is not None
        for row in folders.values():
            row["explicit_trash_root"] = row["id"] in trash
        rows = tuple(files[ref.resource_id] if ref.resource_type == ResourceType.FILE else folders[ref.resource_id] for ref in refs)
        return LoadedResources(rows, states, ancestors)
