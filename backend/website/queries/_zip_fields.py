"""Database projections used only while assembling ZIP entries."""

ZIP_FILE_VALUE_FIELDS = (
    "id",
    "name",
    "crc",
    "size",
    "parent_id",
    "encryption_method",
    "iv",
    "key",
)

ZIP_FOLDER_VALUE_FIELDS = (
    "id",
    "name",
    "parent_id",
    "owner_id",
)
