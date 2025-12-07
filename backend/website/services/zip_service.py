from ..core.errors import BadRequestError
from ..core.helpers import get_attr
from ..models import UserZIP


def create_zip_model(user, items: list[str]) -> UserZIP:
    parent_ids = set()

    for item in items:
        parent_ids.add(get_attr(item, "parent_id"))

    if len(parent_ids) > 1:
        raise BadRequestError("All files and folders must come from the same parent")

    user_zip = UserZIP.objects.create(owner=user)

    file_relations = []
    folder_relations = []

    # Get the through tables
    file_through = UserZIP.files.through
    folder_through = UserZIP.folders.through

    for item in items:
        item_id = get_attr(item, 'id')

        if get_attr(item, 'is_dir', True):
            folder_relations.append(folder_through(userzip_id=user_zip.pk, folder_id=item_id))
        else:
            file_relations.append(file_through(userzip_id=user_zip.pk, file_id=item_id))

    if file_relations:
        file_through.objects.bulk_create(file_relations, ignore_conflicts=True)
    if folder_relations:
        folder_through.objects.bulk_create(folder_relations, ignore_conflicts=True)

    return user_zip
