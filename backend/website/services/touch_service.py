from django.db import transaction
from django.utils import timezone

from website.models import File
from website.models import Folder


def _file_parent_ids(file_ids: list[str]) -> list[str]:
    return list(File.objects.filter(id__in=file_ids).values_list("parent_id", flat=True).distinct())


def _folder_parent_ids(folder_ids: list[str]) -> list[str]:
    return list(Folder.objects.filter(id__in=folder_ids).values_list("parent_id", flat=True).distinct())


def _file_ids(files: list[File]) -> list[str]:
    return [file.id for file in files]


def _folder_ids(folders: list[Folder]) -> list[str]:
    return [folder.id for folder in folders]


def _file_parent_ids_from_objects(files: list[File]) -> list[str]:
    return list({file.parent_id for file in files if file.parent_id is not None})


def _folder_parent_ids_from_objects(folders: list[Folder]) -> list[str]:
    return list({folder.parent_id for folder in folders if folder.parent_id is not None})


def touch_files(file_ids: list[str], parent_ids: list[str] | None = None, touch_parent_listings: bool = True) -> None:
    now = timezone.now()

    with transaction.atomic():
        File.objects.filter(id__in=file_ids).update(last_modified_at=now)

        if touch_parent_listings:
            Folder.objects.filter(id__in=parent_ids or _file_parent_ids(file_ids)).update(last_modified_at=now)


def touch_file_objects(files: list[File], touch_parent_listings: bool = True) -> None:
    now = timezone.now()

    file_ids = _file_ids(files)
    with transaction.atomic():
        File.objects.filter(id__in=file_ids).update(last_modified_at=now)

        if touch_parent_listings:
            Folder.objects.filter(id__in=_file_parent_ids_from_objects(files)).update(last_modified_at=now)


def touch_folders(folder_ids: list[str], parent_ids: list[str] | None = None, touch_parent_listings: bool = True) -> None:
    now = timezone.now()

    with transaction.atomic():
        Folder.objects.filter(id__in=folder_ids).update(last_modified_at=now)

        if touch_parent_listings:
            Folder.objects.filter(id__in=parent_ids or _folder_parent_ids(folder_ids)).update(last_modified_at=now)


def touch_folder_objects(folders: list[Folder], touch_parent_listings: bool = True) -> None:
    now = timezone.now()

    folder_ids = _folder_ids(folders)
    with transaction.atomic():
        Folder.objects.filter(id__in=folder_ids).update(last_modified_at=now)

        if touch_parent_listings:
            Folder.objects.filter(id__in=_folder_parent_ids_from_objects(folders)).update(last_modified_at=now)


def touch_file_move(file_ids: list[str], old_parent_ids: list[str], new_parent_ids: list[str]) -> None:
    now = timezone.now()
    with transaction.atomic():
        File.objects.filter(id__in=file_ids).update(last_modified_at=now)

        Folder.objects.filter(id__in=[*old_parent_ids, *new_parent_ids]).update(last_modified_at=now)


def touch_file_object_move(files: list[File], old_parent_ids: list[str], new_parent_ids: list[str]) -> None:
    touch_file_move(_file_ids(files), old_parent_ids, new_parent_ids)


def touch_folder_move(folder_ids: list[str], old_parent_ids: list[str], new_parent_ids: list[str]) -> None:
    now = timezone.now()

    Folder.objects.filter(id__in=[*folder_ids, *old_parent_ids, *new_parent_ids]).update(last_modified_at=now)


def touch_folder_object_move(folders: list[Folder], old_parent_ids: list[str], new_parent_ids: list[str]) -> None:
    touch_folder_move(_folder_ids(folders), old_parent_ids, new_parent_ids)


def touch_file_object(file: File, touch_parent_listings: bool = True) -> None:
    touch_file_objects([file], touch_parent_listings=touch_parent_listings)


def touch_folder_object(folder: Folder, touch_parent_listings: bool = True) -> None:
    touch_folder_objects([folder], touch_parent_listings=touch_parent_listings)