from ..utilities.constants import MAX_RESOURCE_NAME_LENGTH


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
