from website.config import MAX_RESOURCE_NAME_LENGTH


def param_to_bool(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    lowered = value.lower()
    if lowered in {"true", "1"}:
        return True
    if lowered in {"false", "0"}:
        return False
    raise ValueError(f"Conversion failed for: {value} to bool")


def chop_long_file_name(file_name: str) -> str:
    if len(file_name) <= MAX_RESOURCE_NAME_LENGTH:
        return file_name

    last_dot_index = file_name.rfind(".")

    if last_dot_index > 0:
        file_extension = file_name[last_dot_index:]
        file_name_without_extension = file_name[:last_dot_index]
    else:
        file_extension = ""
        file_name_without_extension = file_name

    max_base_length = MAX_RESOURCE_NAME_LENGTH - len(file_extension)

    if max_base_length <= 0:
        return file_name[:MAX_RESOURCE_NAME_LENGTH]

    return file_name_without_extension[:max_base_length] + file_extension
