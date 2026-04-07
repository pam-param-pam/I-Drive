import math
from dataclasses import dataclass
from typing import Optional, Dict, Any, Literal

from .utils import decode_redis_hash
from ..core.helpers import normalize_blocked_until
from ..models import Bot, Webhook

CredentialType = Literal["bot", "webhook"]


@dataclass
class CredentialState:
    name: str
    secret: str
    discord_id: str
    credential_type: CredentialType
    requests_remaining: int
    reset_timestamp: Optional[float]
    in_flight: int = 0
    blocked_until: Optional[float] = None
    block_reason: str = ""
    discord_error_code: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        data = self.__dict__.copy()
        data.pop("secret", None)
        data["blocked_until"] = normalize_blocked_until(data.get("blocked_until"))
        return data

    def to_redis_hash(self) -> Dict[str, Any]:
        blocked_until = self.blocked_until
        if blocked_until is None:
            blocked_until_raw = ""
        elif math.isinf(blocked_until):
            blocked_until_raw = "inf"
        else:
            blocked_until_raw = blocked_until

        return {
            "name": self.name,
            "secret": self.secret,
            "discord_id": self.discord_id,
            "credential_type": self.credential_type,
            "requests_remaining": self.requests_remaining,
            "reset_timestamp": "" if self.reset_timestamp is None else self.reset_timestamp,
            "in_flight": self.in_flight,
            "blocked_until": blocked_until_raw,
            "block_reason": self.block_reason,
            "discord_error_code": "" if self.discord_error_code is None else self.discord_error_code,
        }

    @classmethod
    def new_bot(cls, bot: Bot) -> "CredentialState":
        return cls(
            name=bot.name,
            secret=bot.token,
            discord_id=bot.discord_id,
            credential_type="bot",
            requests_remaining=5,
            reset_timestamp=None,
        )

    @classmethod
    def new_webhook(cls, webhook: Webhook) -> "CredentialState":
        return cls(
            name=webhook.name,
            secret=webhook.url,
            discord_id=webhook.discord_id,
            credential_type="webhook",
            requests_remaining=5,
            reset_timestamp=None,
        )

    @classmethod
    def from_redis_hash(cls, data: Dict[str, Any]) -> "CredentialState":
        data = decode_redis_hash(data)

        blocked_until_raw = data.get("blocked_until")
        if blocked_until_raw in (None, "", "None"):
            blocked_until = None
        elif blocked_until_raw == "inf":
            blocked_until = float("inf")
        else:
            blocked_until = float(blocked_until_raw)

        reset_raw = data.get("reset_timestamp")
        reset_timestamp = None if reset_raw in (None, "", "None") else float(reset_raw)

        error_raw = data.get("discord_error_code")
        discord_error_code = None if error_raw in (None, "", "None") else int(error_raw)

        return cls(
            name=data["name"],
            secret=data["secret"],
            discord_id=data["discord_id"],
            credential_type=data["credential_type"],
            requests_remaining=int(data["requests_remaining"]),
            reset_timestamp=reset_timestamp,
            in_flight=int(data.get("in_flight", 0)),
            blocked_until=blocked_until,
            block_reason=data.get("block_reason", ""),
            discord_error_code=discord_error_code,
        )
