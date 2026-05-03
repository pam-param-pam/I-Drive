from typing import Dict, Any


def decode_redis_hash(data: Dict[Any, Any]) -> Dict[str, str]:
    return {
        (k.decode() if isinstance(k, bytes) else k):
            (v.decode() if isinstance(v, bytes) else v)
        for k, v in data.items()
    }
