from website.constants import MAX_FILES_IN_ZIP
from website.core.errors import BadRequestError
from website.core.helpers import get_attr, validate_ids_as_list
from website.models import UserZIP, Folder, File


def create_zip_model(user, items: list[dict]) -> UserZIP:
    validate_ids_as_list(items, child_type=(dict, Folder, File), max_length=MAX_FILES_IN_ZIP)

    parent_ids = set()

    for item in items:
        parent_ids.add(get_attr(item, "parent_id"))

    if len(parent_ids) > 1:
        raise BadRequestError("All files and folders must come from the same parent")

    user_zip = UserZIP.objects.create(owner=user, name="I-Drive")

    file_relations = []
    folder_relations = []

    # Get the through tables
    file_through = UserZIP.files.through
    folder_through = UserZIP.folders.through

    for item in items:
        item_id = get_attr(item, 'id')

        if isinstance(item, Folder):
            folder_relations.append(folder_through(userzip_id=user_zip.pk, folder_id=item_id))
        else:
            file_relations.append(file_through(userzip_id=user_zip.pk, file_id=item_id))

    if file_relations:
        file_through.objects.bulk_create(file_relations, ignore_conflicts=True)
    if folder_relations:
        folder_through.objects.bulk_create(folder_relations, ignore_conflicts=True)

    if not file_relations and len(folder_relations) == 1:
        user_zip.name = get_attr(items[0], "name")
    else:
        user_zip.name = f"I-Drive-{user_zip.id}"

    user_zip.save(update_fields=["name"])

    return user_zip
