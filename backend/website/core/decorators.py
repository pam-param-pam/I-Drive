import os
from functools import wraps
from typing import Callable, Union

from django.core.exceptions import ObjectDoesNotExist

from .crypto.signer import verify_signed_resource_id
from .helpers import validate_ids_as_list
from ..auth.Permissions import CheckGroup
from ..models import File, Folder, ShareableLink
from ..core.errors import ResourceNotFoundError, MissingOrIncorrectResourcePasswordError, BadRequestError
from ..queries.selectors import get_file

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
        kwargs["file_obj"] = file_obj
        request.META['signed_file_id'] = signed_file_id
        return view_func(request, *args, **kwargs)

    return wrapper


def check_resource_permissions(checks: list, resource_key: Union[str, list[str]], optional: bool = False):
    if not isinstance(checks, CheckGroup):
        if isinstance(checks, list):
            checks = CheckGroup(*checks)
        else:
            raise ValueError(f"checks must be a list or a CheckGroup, got: {type(checks)}")

    if isinstance(resource_key, str):
        resource_key = [resource_key]

    def decorator(view_func: Callable):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            resources = []
            missing_keys = []
            for key in resource_key:
                resource = kwargs.get(key)
                if resource is None:
                    missing_keys.append(key)
                resources.append(resource)

            if missing_keys:
                if optional:
                    return view_func(request, *args, **kwargs)
                else:
                    raise ValueError(f"[check_resource_permissions] Missing required resource(s) {missing_keys} in kwargs")

            print(f"[check_resource_permissions] Running checks: {checks} with resources: {resource_key}")
            for Check in checks:
                Check().check(request, *resources)

            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator


def extract_folder(source: str = "kwargs", key: str = "folder_id", inject_as: str = "folder_obj", optional: bool = False):
    return extract_resources({
        "source": source,
        "key": key,
        "model": [Folder],
        "inject_as": inject_as,
        "optional": optional
    })


def extract_file(source: str = "kwargs", key: str = "file_id", inject_as: str = "file_obj"):
    return extract_resources({
        "source": source,
        "key": key,
        "model": [File],
        "inject_as": inject_as,
    })


def extract_item(source: str = "kwargs", key: str = "item_id", inject_as: str = "item_obj"):
    return extract_resources({
        "source": source,
        "key": key,
        "model": [File, Folder],
        "inject_as": inject_as,
    })


def extract_items(source: str = "kwargs", key: str = "ids", inject_as: str = "items"):
    return extract_resources({
        "source": source,
        "key": key,
        "model": [File, Folder],
        "inject_as": inject_as,
        "many": True,
    })


def extract_share(source: str = "kwargs", key: str = "token", inject_as: str = "share_obj", model_field: str = "token"):
    return extract_resources({
        "source": source,
        "key": key,
        "model": [ShareableLink],
        "inject_as": inject_as,
        "model_field": model_field
    })


def extract_resources(*rules):
    def _get_resource_from_models(models, obj_id, model_field: str):
        for model in models:
            try:
                return model.objects.get(**{model_field: obj_id})
            except ObjectDoesNotExist:
                continue
        model_names = ", ".join(m.__name__ for m in models)

        raise ResourceNotFoundError(f"Couldn't find [{model_names}] with id={obj_id!r}")

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            for rule in rules:
                source = rule.get("source", "data")
                key = rule["key"]
                models = rule["model"]
                inject_as = rule["inject_as"]
                many = rule.get("many", False)
                optional = rule.get("optional", False)
                model_field = rule.get("model_field", "id")

                # Get container (e.g. kwargs, request.GET, request.data, etc.)
                container = kwargs if source == "kwargs" else getattr(request, source, {})

                # If key not in container and optional, skip this rule
                if key not in container:
                    if optional:
                        kwargs[inject_as] = None if not many else []
                        continue
                    else:
                        raise BadRequestError(f"Missing key '{key}' in request.{source}")

                ids = container[key]

                if many:
                    if not isinstance(ids, (list, tuple)):
                        raise BadRequestError(f"Expected list of IDs for key '{key}', got {type(ids).__name__}")

                    # if len(ids) != len(set(ids)):
                    #     raise BadRequestError(f"Duplicate IDs provided for '{key}'")

                    found_resources = []
                    for obj_id in ids:
                        resource = _get_resource_from_models(models, obj_id, model_field)
                        found_resources.append(resource)
                    kwargs[inject_as] = found_resources
                else:
                    if isinstance(ids, (list, tuple)):
                        raise BadRequestError(f"Expected single ID for key '{key}', got multiple")
                    resource = _get_resource_from_models(models, ids, model_field)
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

            if len(ids) != len(set(ids)):
                raise BadRequestError(f"Duplicate IDs provided for '{key}'")
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

            for check in checks:
                for resource in resources:
                    try:
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


def accumulate_password_errors(*decorators):
    """
    Wrap multiple decorators and accumulate MissingOrIncorrectResourcePasswordError
    from all of them before raising a single exception.
    The wrapped view will only run after all checks pass.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            password_errors = []

            for dec in decorators:
                try:
                    # Use a dummy function to only execute the decorator checks,
                    # without running the actual view.
                    dec(lambda *a, **k: None)(*args, **kwargs)
                except MissingOrIncorrectResourcePasswordError as e:
                    password_errors.extend(e.requiredPasswords)

            if password_errors:
                raise MissingOrIncorrectResourcePasswordError(password_errors)

            # Now run the actual view
            return func(*args, **kwargs)

        return wrapper
    return decorator
