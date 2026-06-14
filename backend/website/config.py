import json
import os
from pathlib import Path


CONFIG_FILE_PATH = os.environ.get("IDRIVE_CONFIG_FILE", "idrive.config.json")


DEFAULT_CONFIG = {
    "NUMBER_OF_CHANNELS": 5,
    "MAX_NUMBER_OF_CHANNELS": 10,
    "NUMBER_OF_WEBHOOKS_PER_CHANNEL": 2,
    "WEBHOOK_NAME_TEMPLATE": "Captain Hook v{n}",
    "ALLOWED_IPS_LOCKED": [],
    "MAX_FOLDER_DEPTH": 10,
    "MAX_FILES_IN_FOLDER": 10_000,
    "TOKEN_EXPIRY_DAYS": 30,
    "MAX_RESOURCE_NAME_LENGTH": 75,
    "MAX_THUMBNAIL_SIZE": int(0.5 * 1024 * 1024),
    "GENERATE_RAW_THUMBNAILS": True,
    "MAX_RAW_IMAGE_SIZE_ALLOWED_FOR_CONVERSION": 75 * 1024 * 1024,
}


def load_config():
    config = DEFAULT_CONFIG.copy()
    path = Path(CONFIG_FILE_PATH)

    if not path.exists():
        return config

    with path.open(encoding="utf-8") as f:
        user_config = json.load(f)

    unknown_keys = set(user_config) - set(DEFAULT_CONFIG)
    if unknown_keys:
        raise ValueError(f"Unknown config keys: {sorted(unknown_keys)}")

    config.update(user_config)
    validate_config(config)
    return config


def validate_config(config):
    positive_int_keys = [
        "NUMBER_OF_CHANNELS",
        "MAX_NUMBER_OF_CHANNELS",
        "NUMBER_OF_WEBHOOKS_PER_CHANNEL",
        "MAX_FOLDER_DEPTH",
        "MAX_FILES_IN_FOLDER",
        "TOKEN_EXPIRY_DAYS",
        "MAX_RESOURCE_NAME_LENGTH",
        "MAX_THUMBNAIL_SIZE",
        "MAX_RAW_IMAGE_SIZE_ALLOWED_FOR_CONVERSION",
    ]

    for key in positive_int_keys:
        if not isinstance(config[key], int) or config[key] < 1:
            raise ValueError(f"{key} must be a positive integer")

    if config["MAX_NUMBER_OF_CHANNELS"] < config["NUMBER_OF_CHANNELS"]:
        raise ValueError("MAX_NUMBER_OF_CHANNELS must be >= NUMBER_OF_CHANNELS")

    if not isinstance(config["WEBHOOK_NAME_TEMPLATE"], str) or "{n}" not in config["WEBHOOK_NAME_TEMPLATE"]:
        raise ValueError("WEBHOOK_NAME_TEMPLATE must be a string containing {n}")

    if not isinstance(config["ALLOWED_IPS_LOCKED"], list):
        raise ValueError("ALLOWED_IPS_LOCKED must be a list")

    if not isinstance(config["GENERATE_RAW_THUMBNAILS"], bool):
        raise ValueError("GENERATE_RAW_THUMBNAILS must be true or false")


CONFIG = load_config()


NUMBER_OF_CHANNELS = CONFIG["NUMBER_OF_CHANNELS"]
MAX_NUMBER_OF_CHANNELS = CONFIG["MAX_NUMBER_OF_CHANNELS"]
NUMBER_OF_WEBHOOKS_PER_CHANNEL = CONFIG["NUMBER_OF_WEBHOOKS_PER_CHANNEL"]
WEBHOOK_NAME_TEMPLATE = CONFIG["WEBHOOK_NAME_TEMPLATE"]
ALLOWED_IPS_LOCKED = CONFIG["ALLOWED_IPS_LOCKED"]
MAX_FOLDER_DEPTH = CONFIG["MAX_FOLDER_DEPTH"]
MAX_FILES_IN_FOLDER = CONFIG["MAX_FILES_IN_FOLDER"]
TOKEN_EXPIRY_DAYS = CONFIG["TOKEN_EXPIRY_DAYS"]
MAX_RESOURCE_NAME_LENGTH = CONFIG["MAX_RESOURCE_NAME_LENGTH"]
MAX_THUMBNAIL_SIZE = CONFIG["MAX_THUMBNAIL_SIZE"]
GENERATE_RAW_THUMBNAILS = CONFIG["GENERATE_RAW_THUMBNAILS"]
MAX_RAW_IMAGE_SIZE_ALLOWED_FOR_CONVERSION = CONFIG["MAX_RAW_IMAGE_SIZE_ALLOWED_FOR_CONVERSION"]