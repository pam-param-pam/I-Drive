from website.constants import cache

FOLDER_CONTENT_CACHE_TIMEOUT = 6 * 60 * 60
FOLDER_HASH_CACHE_TIMEOUT = 6 * 60 * 60


def get_thumbnail_key(file_id: str) -> str:
    return f"thumbnail:{file_id}"

def get_folder_content_key(folder_id: str) -> str:
    return f"folder-content:{folder_id}"


def get_folder_hash_key(folder_id: str) -> str:
    return f"folder-hash:{folder_id}"


def get_folder_content_version(folder) -> str:
    return folder.last_modified_at.isoformat() if folder.last_modified_at else ""


def get_folder_content(folder):
    cached = cache.get(get_folder_content_key(folder.id))

    if not isinstance(cached, dict):
        return None

    if cached.get("version") != get_folder_content_version(folder):
        return None

    return cached.get("content")


def set_folder_content(folder, folder_content: dict) -> None:
    cache.set(
        get_folder_content_key(folder.id),
        {
            "version": get_folder_content_version(folder),
            "content": folder_content,
        },
        timeout=FOLDER_CONTENT_CACHE_TIMEOUT,
    )


def get_folder_hash(folder_id: str, version: str) -> str | None:
    cached = cache.get(get_folder_hash_key(folder_id))

    if not isinstance(cached, dict):
        return None

    if cached.get("version") != version:
        return None

    return cached.get("hash")


def set_folder_hash(folder_id: str, version: str, digest: str) -> None:
    cache.set(
        get_folder_hash_key(folder_id),
        {
            "version": version,
            "hash": digest,
        },
        timeout=FOLDER_HASH_CACHE_TIMEOUT,
    )


def get_folder_usage_key(folder_id: str) -> str:
    return f"folder-usage:{folder_id}"

def get_qr_session_key(session_id: str) -> str:
    return f"qr-session:{session_id}"

def get_qr_ip_key(qr_ip: str) -> str:
    return f"qr-ip:{qr_ip}"

def get_discord_message_key(message_id: str) -> str:
    return f"discord-message:{message_id}"

def get_total_used_size_key(user_id: int) -> str:
    return f"total-used-size:{user_id}"
