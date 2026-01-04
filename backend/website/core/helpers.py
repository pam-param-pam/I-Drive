import base64
from typing import Union, Type, Tuple, Optional, Any

from .errors import BadRequestError
from .validators.Check import Check
from ..constants import MAX_RESOURCE_NAME_LENGTH, EncryptionMethod, EXTENSION_TO_FILE_TYPE

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


def validate_ids_as_list(ids: list, max_length: int = 1000, child_type: Union[Type, Tuple[Type, ...]] = (str, dict)) -> None:
    if not isinstance(ids, list):
        raise BadRequestError("'ids' must be a list.")

    if len(ids) == 0:
        raise BadRequestError("'ids' length cannot be 0.")

    if len(ids) > max_length:
        raise BadRequestError(f"'ids' length cannot > {max_length}.")

    for x in ids:
        if not isinstance(x, child_type):
            types_tuple = child_type if isinstance(child_type, tuple) else (child_type,)
            expected_types = ", ".join(f"'{t.__name__}'" for t in types_tuple)

            raise BadRequestError(f"All ids must be of type=[{expected_types}], got type='{type(x).__name__}'")


def get_file_type(extension: str) -> str:
    return EXTENSION_TO_FILE_TYPE.get(extension.lower(), "Other")

def get_file_extension(filename: str) -> str:
    if "." not in filename or filename.endswith("."):
        return ".txt"
    return "." + filename.rsplit(".", 1)[1]

def validate_value(value: Any, expected_type: Type, *, required: bool = False, default=None, checks: list = None):
    if value is None:
        if not required and default is not None:
            return default
        if not required:
            return None
        raise BadRequestError("Value cannot be null.")

    if expected_type is str and isinstance(value, str):
        if "\x00" in value:
            value = value.replace("\x00", "")

    if not isinstance(value, expected_type):
        raise BadRequestError(f"Value must be of type {expected_type}, got {type(value).__name__}")

    if checks is None:
        checks = []

    normalized_checks = []
    for check in checks:
        if isinstance(check, type) and issubclass(check, Check):
            check = check()
        normalized_checks.append(check)

    # Run checks
    for check in normalized_checks:
        if not check.check(value):
            raise BadRequestError(f"Validation failed on {type(check).__name__} with value '{value}'")

    return value


def validate_key(data: Optional[dict], key: str, expected_type, *, required: bool = True, default=None, checks: list = None):
    if not data:
        if required:
            raise BadRequestError("'data' cannot be None.")
        return default

    if not isinstance(data, dict):
        raise BadRequestError("'data' must be a dict.")

    if key not in data:
        if required:
            raise BadRequestError(f"Missing required field '{key}'.")
        return default

    value = data[key]

    try:
        return validate_value(
            value,
            expected_type,
            required=required,
            default=default,
            checks=checks
        )
    except BadRequestError as e:
        raise BadRequestError(f"Field '{key}': {e}")


def validate_encryption_fields(encryption_method: int, key_b64: str, iv_b64: str) -> tuple[Optional[bytes], Optional[bytes]]:
    method = EncryptionMethod(encryption_method)

    if method == EncryptionMethod.Not_Encrypted:
        if key_b64 or iv_b64:
            raise BadRequestError("Unencrypted files must NOT provide 'key' or 'iv'.")
        return None, None

    if not key_b64 or not iv_b64:
        raise BadRequestError("Encrypted files must provide both 'key' and 'iv'.")

    try:
        key = base64.b64decode(key_b64)
        iv = base64.b64decode(iv_b64)
    except Exception:
        raise BadRequestError("Invalid base64 for 'key' or 'iv'.")

    if len(key) == 0 or len(iv) == 0:
        raise BadRequestError("'key' or 'iv' decoded to empty bytes.")

    if method == EncryptionMethod.AES_CTR:
        expected_iv = 16
        expected_key = 32

    elif method == EncryptionMethod.CHA_CHA_20:
        expected_iv = 12
        expected_key = 32

    else:
        raise BadRequestError(f"Unsupported encryption method: {method.value}")

    if len(key) != expected_key:
        raise BadRequestError(f"Invalid key length for {method.name}: expected {expected_key} bytes, got {len(key)}.")

    if len(iv) != expected_iv:
        raise BadRequestError(f"Invalid IV length for {method.name}: expected {expected_iv} bytes, got {len(iv)}.")

    return key, iv


def validate_crc(file_size: int, crc: int) -> None:
    if not crc and file_size:
        raise BadRequestError("Bad crc value")
