from typing import LiteralString


def format_cleanup_summary(res: dict) -> LiteralString | None:
    parts = []

    labels = {
        "shares_removed": "Shares",
        "zips_removed": "ZIPs",
        "tokens_removed": "Tokens",
        "trash_removed": "Trash",
        "discord_removed": "Discord",
        "notifications_removed": "Notifications",
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