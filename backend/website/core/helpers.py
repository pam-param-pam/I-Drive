from typing import Union

from .errors import BadRequestError
from ..constants import MAX_RESOURCE_NAME_LENGTH, CODE_EXTENSIONS, RAW_IMAGE_EXTENSIONS, EXECUTABLE_EXTENSIONS, VIDEO_EXTENSIONS, AUDIO_EXTENSIONS, TEXT_EXTENSIONS, DOCUMENT_EXTENSIONS, \
    EBOOK_EXTENSIONS, SYSTEM_EXTENSIONS, DATABASE_EXTENSIONS, ARCHIVE_EXTENSIONS, IMAGE_EXTENSIONS

_SENTINEL = object()  # Unique object to detect omitted default

def get_attr(resource: Union[dict, object], attr: str, default=_SENTINEL):
    """Helper function to get attribute from either an object or a dictionary.
    If `default` is not specified and the attribute is missing, raises AttributeError.
    """
    # Case 1: When the resource is a dictionary
    if isinstance(resource, dict):
        if default is _SENTINEL and attr not in resource:
            raise AttributeError(f"Attribute '{attr}' not found in dictionary.")
        return resource.get(attr, default if default is not _SENTINEL else None)

    # Case 2: When the resource is a Django ORM object
    try:
        if '__' in attr:
            attributes = attr.split('__')
            value = resource
            for attribute in attributes:
                value = getattr(value, attribute, _SENTINEL)
                if value is _SENTINEL or value is None:
                    if default is _SENTINEL:
                        raise AttributeError(f"Attribute '{attr}' not found in object: {resource.__class__.__name__}.")
                    return default
            return value
        else:
            # Direct attribute (non-related)
            value = getattr(resource, attr, _SENTINEL)
            if value is _SENTINEL:
                if default is _SENTINEL:
                    raise AttributeError(f"Attribute '{attr}' not found in object: {resource.__class__.__name__}.")
                return default
            return value
    except AttributeError:
        if default is _SENTINEL:
            raise AttributeError(f"Attribute '{attr}' not found in object: {resource.__class__.__name__}.")
        return default


def format_wait_time(seconds: int) -> str:
    if seconds >= 3600:  # More than or equal to 1 hour
        hours = seconds // 3600
        return f"{hours} hour{'s' if hours > 1 else ''}"
    elif seconds >= 60:  # More than or equal to 1 minute
        minutes = seconds // 60
        return f"{minutes} minute{'s' if minutes > 1 else ''}"
    else:
        return f"{seconds} second{'s' if seconds > 1 else ''}"

def chop_long_file_name(file_name: str) -> str:
    if len(file_name) > MAX_RESOURCE_NAME_LENGTH:
        # Find the last occurrence of '.' to handle possibility of no extension
        last_dot_index = file_name.rfind('.')

        # Extracting the extension if it exists
        if last_dot_index != -1:
            file_extension = file_name[last_dot_index + 1:]
            file_name_without_extension = file_name[:last_dot_index]
        else:
            file_extension = ""
            file_name_without_extension = file_name

        # Keeping only the first 'max_name_length' characters
        shortened_file_name = file_name_without_extension[:MAX_RESOURCE_NAME_LENGTH]

        # Adding the extension back if it exists
        if file_extension:
            shortened_file_name += "." + file_extension
        return shortened_file_name
    return file_name


def get_ip(request) -> tuple[str, bool]:
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        from_nginx = True
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        from_nginx = False
        ip = request.META.get('REMOTE_ADDR')

    return ip, from_nginx


def validate_ids_as_list(ids: list, max_length: int = 1000) -> None:
    if not isinstance(ids, list):
        raise BadRequestError("'ids' must be a list.")
    if len(ids) == 0:
        raise BadRequestError("'ids' length cannot be 0.")
    if len(ids) > max_length:
        raise BadRequestError(f"'ids' length cannot > {max_length}.")


def get_file_type(extension: str) -> str:
    extension = extension.lower()
    if extension in VIDEO_EXTENSIONS:
        return "Video"
    elif extension in AUDIO_EXTENSIONS:
        return "Audio"
    elif extension in TEXT_EXTENSIONS:
        return "Text"
    elif extension in DOCUMENT_EXTENSIONS:
        return "Document"
    elif extension in EBOOK_EXTENSIONS:
        return "Ebook"
    elif extension in SYSTEM_EXTENSIONS:
        return "System"
    elif extension in DATABASE_EXTENSIONS:
        return "Database"
    elif extension in ARCHIVE_EXTENSIONS:
        return "Archive"
    elif extension in IMAGE_EXTENSIONS:
        return "Image"
    elif extension in EXECUTABLE_EXTENSIONS:
        return "Executable"
    elif extension in CODE_EXTENSIONS:
        return "Code"
    elif extension in RAW_IMAGE_EXTENSIONS:
        return "Raw image"
    else:
        return "Other"
