from datetime import datetime, timezone, timedelta

DISCORD_EPOCH = 1420070400000  # ms

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
