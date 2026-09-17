from datetime import datetime, timezone, timedelta

DISCORD_EPOCH = 1420070400000  # ms
from typing import LiteralString


def auto_prefetch(fragment_id: str) -> None:
    from .otherTasks import prefetch_next_fragments
    fragments_to_prefetch = 5
    prefetch_next_fragments.delay(fragment_id, fragments_to_prefetch)

def snowflake_to_datetime(snowflake_id: str):
    snowflake = int(snowflake_id)
    timestamp_ms = (snowflake >> 22) + DISCORD_EPOCH
    return datetime.fromtimestamp(timestamp_ms / 1000, timezone.utc)

def is_bulk_deletable(message_id: str):
    ts = snowflake_to_datetime(message_id)
    age = datetime.now(timezone.utc) - ts
    # avoid race conditions
    return age < timedelta(days=13, hours=23)

def format_cleanup_summary(res: dict) -> LiteralString | None:
    parts = []

    labels = {
        "shares_removed": "Shares",
        "zips_removed": "ZIPs",
        "tokens_removed": "Tokens",
        "trash_removed": "Trash",
        "notifications_removed": "Notifications",
        "discord_removed": "Discord",
        "cleanup_remote_missing_files": "Remote missing files",
    }

    for key, label in labels.items():
        count = res.get(key, 0)
        if count > 0:
            parts.append(f"{label}: {count} removed")

    # generic errors
    for k, v in res.items():
        if k.endswith("_error"):
            parts.append(f"{k.replace('_', ' ').capitalize()}: {v}")

    return " | ".join(parts) if parts else None