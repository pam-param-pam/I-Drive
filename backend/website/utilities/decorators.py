import os
import time
from functools import wraps
from typing import Callable

from django.core.exceptions import ObjectDoesNotExist

from .signer import verify_signed_resource_id
from ..models import File, Folder, ShareableLink
from ..utilities.errors import ResourceNotFoundError, MissingOrIncorrectResourcePasswordError, BadRequestError
from ..utilities.other import get_file, validate_ids_as_list

is_dev_env = os.getenv('IS_DEV_ENV', 'False') == 'True'


def no_gzip(view_func):
    """Decorator to prevent GZipMiddleware from compressing the response."""

    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        request.META["HTTP_ACCEPT_ENCODING"] = "identity"
        response = view_func(request, *args, **kwargs)
        return response

    return wrapped_view


def disable_common_errors(view_func):
    def wrapper(*args, **kwargs):
        setattr(wrapper, 'disable_common_errors', True)
        return view_func(*args, **kwargs)
    return wrapper


def extract_file_from_signed_url(view_func):
    @wraps(view_func)
    def wrapper(request, signed_file_id, *args, **kwargs):
        file_id = verify_signed_resource_id(signed_file_id)
        file_obj = get_file(file_id)

        return view_func(request, file_obj, *args, **kwargs)

    return wrapper


def check_resource_permissions(checks: list, resource_key):
    def decorator(view_func: Callable):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            start_time = time.perf_counter()

            resource = kwargs.get(resource_key)
            if not resource:
                raise ValueError(f"Missing '{resource_key}' in kwargs")
            print(f"got checks: {checks}")
            for Check in checks:
                Check().check(request, resource)

            end_time = time.perf_counter()
            elapsed = end_time - start_time
            print(f"PERMISSION CHECKS took {elapsed:.4f} seconds")

            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator


def extract_folder(source="kwargs", key="folder_id", inject_as="folder_obj"):
    return extract_resources({
        "source": source,
        "key": key,
        "model": [Folder],
        "inject_as": inject_as,
    })


def extract_file(source="kwargs", key="file_id", inject_as="file_obj"):
    return extract_resources({
        "source": source,
        "key": key,
        "model": [File],
        "inject_as": inject_as,
    })


def extract_item(source="kwargs", key="item_id", inject_as="item_obj"):
    return extract_resources({
        "source": source,
        "key": key,
        "model": [File, Folder],
        "inject_as": inject_as,
    })

def extract_items(source="kwargs", key="ids", inject_as="items"):
    return extract_resources({
        "source": source,
        "key": key,
        "model": [File, Folder],
        "inject_as": inject_as,
        "many": True,
    })
def extract_resource(source="kwargs", key="resource_id", inject_as="resource_obj"):
    return extract_resources({
        "source": source,
        "key": key,
        "model": [File, Folder, ShareableLink],
        "inject_as": inject_as,
    })


def extract_resources(*rules):
    def _get_resource_from_models(models, obj_id):
        for model in models:
            try:
                return model.objects.get(id=obj_id)
            except ObjectDoesNotExist:
                continue
        model_names = ", ".join(m.__name__ for m in models)
        raise ResourceNotFoundError(f"No resource with ID '{obj_id}' found in models: {model_names}")

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            for rule in rules:
                source = rule.get("source", "data")
                key = rule["key"]
                models = rule["model"]
                inject_as = rule["inject_as"]
                many = rule.get("many", False)

                # Get container
                container = kwargs if source == "kwargs" else getattr(request, source, {})
                if key not in container:
                    raise ValueError(f"Missing key '{key}' in request.{source}")

                ids = container[key]

                if many:
                    if not isinstance(ids, (list, tuple)):
                        raise ValueError(f"Expected list of IDs for key '{key}', got {type(ids).__name__}")
                    found_resources = []
                    for obj_id in ids:
                        resource = _get_resource_from_models(models, obj_id)
                        found_resources.append(resource)
                    kwargs[inject_as] = found_resources
                else:
                    if isinstance(ids, (list, tuple)):
                        raise ValueError(f"Expected single ID for key '{key}', got multiple")
                    resource = _get_resource_from_models(models, ids)
                    kwargs[inject_as] = resource

                # Remove original key
                if source == "kwargs" and key in kwargs:
                    del kwargs[key]
                elif source in ("data", "GET") and hasattr(container, "pop"):
                    container.pop(key, None)

            return view_func(request, *args, **kwargs)

        return _wrapped_view
    return decorator


def extract_items_from_ids_annotated(file_values, file_annotate=None, folder_model=Folder, file_model=File, inject_as="items", source="data", key="ids", max_length=10000):
    file_annotate = file_annotate or {}

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            container = getattr(request, source, {})
            ids = container.get(key)

            validate_ids_as_list(ids, max_length=max_length)

            files_qs = (
                file_model.objects
                .filter(id__in=ids)
                .annotate(**file_annotate)
                .values(*file_values)
            )
            files = list(files_qs)
            matched_file_ids = {f["id"] for f in files}

            # Get remaining IDs to query from Folder
            remaining_ids = set(ids) - matched_file_ids
            folders = list(folder_model.objects.filter(id__in=remaining_ids))
            matched_folder_ids = {f.id for f in folders}

            # Optional: Check if total matched == input length
            total_matched = len(matched_file_ids) + len(matched_folder_ids)
            if total_matched != len(set(ids)):
                missing = set(ids) - matched_file_ids - matched_folder_ids
                raise BadRequestError(f"Some IDs were wrong: {missing}")

            kwargs[inject_as] = files + folders
            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator


def check_bulk_permissions(checks, resource_key="items"):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            resources = kwargs.get(resource_key)
            all_required_passwords = []
            seen_ids = set()
            print(f"got checks: {checks}")

            for check in checks:
                try:
                    for resource in resources:
                        check().check(request, resource)
                except MissingOrIncorrectResourcePasswordError as e:
                    for pwd in e.requiredPasswords:
                        if pwd["id"] not in seen_ids:
                            all_required_passwords.append(pwd)
                            seen_ids.add(pwd["id"])

            if all_required_passwords:
                raise MissingOrIncorrectResourcePasswordError(all_required_passwords)

            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator
