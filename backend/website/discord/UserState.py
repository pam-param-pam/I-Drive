import json
import time
from typing import Optional, Dict, Any

from django_redis import get_redis_connection

from .CredentialState import CredentialState, CredentialType
from .utils import decode_redis_hash
from ..core.errors import DiscordBlockError, CannotProcessDiscordRequestError, BadRequestError
from ..core.helpers import normalize_blocked_until
from ..models import DiscordSettings, Bot, Channel, Webhook


class UserState:
    """
    Redis-backed replacement for the original in-memory UserState.

    Persistent/static user snapshot:
      - guild_id
      - channels
      - max_concurrent_per_token
      - mapping of credentials

    Mutable runtime state in Redis per credential:
      - requests_remaining
      - reset_timestamp
      - in_flight
      - blocked_until
      - block_reason
      - discord_error_code

    Global mutable runtime state in Redis:
      - _blocked_until
    """

    REDIS_PREFIX = "discord_user_state"

    def __init__(self, user, max_concurrent_per_token: int = 3):
        self.user = user
        self.max_concurrent_per_token = max_concurrent_per_token
        self._redis = get_redis_connection()
        self._initialize()

    def _user_key(self) -> str:
        return f"{self.REDIS_PREFIX}:user:{self.user.id}"

    def _meta_key(self) -> str:
        return f"{self._user_key()}:meta"

    def _channels_key(self) -> str:
        return f"{self._user_key()}:channels"

    def _credentials_set_key(self) -> str:
        return f"{self._user_key()}:credentials"

    def _credentials_by_secret_key(self) -> str:
        return f"{self._user_key()}:credentials_by_secret"

    def _credential_key(self, secret: str) -> str:
        return f"{self._user_key()}:credential:{secret}"

    # ------------------------------------------------------------------
    # Lua scripts
    # ------------------------------------------------------------------

    @property
    def _acquire_script(self):
        return self._redis.register_script("""
            local now = tonumber(ARGV[1])
            local max_concurrent = tonumber(ARGV[2])
            local requested_type = ARGV[3]
            local requested_secret = ARGV[4]
            
            local global_blocked_until_raw = redis.call('HGET', KEYS[1], 'blocked_until')
            if global_blocked_until_raw and global_blocked_until_raw ~= '' then
                local global_blocked_until
                if global_blocked_until_raw == 'inf' then
                    global_blocked_until = math.huge
                else
                    global_blocked_until = tonumber(global_blocked_until_raw)
                end
            
                if global_blocked_until and now < global_blocked_until then
                    return cjson.encode({ ok = false, code = 'GLOBAL_BLOCK', retry_after = global_blocked_until - now })
                else
                    redis.call('HDEL', KEYS[1], 'blocked_until')
                end
            end
            
            if requested_secret ~= '' then
                local credential_key = redis.call('HGET', KEYS[2], requested_secret)
                if not credential_key then
                    return cjson.encode({ ok = false, code = 'NOT_FOUND' })
                end
            
                local ctype = redis.call('HGET', credential_key, 'credential_type')
                if requested_type ~= '' and ctype ~= requested_type then
                    return cjson.encode({ ok = false, code = 'TYPE_MISMATCH' })
                end
            
                local blocked_until_raw = redis.call('HGET', credential_key, 'blocked_until')
                if blocked_until_raw and blocked_until_raw ~= '' then
                    local blocked_until
                    if blocked_until_raw == 'inf' then
                        blocked_until = math.huge
                    else
                        blocked_until = tonumber(blocked_until_raw)
                    end
            
                    if blocked_until and now < blocked_until then
                        return cjson.encode({ ok = false, code = 'CREDENTIAL_BLOCKED' })
                    end
                end
            
                local reset_ts_raw = redis.call('HGET', credential_key, 'reset_timestamp')
                if reset_ts_raw and reset_ts_raw ~= '' then
                    local reset_ts = tonumber(reset_ts_raw)
                    if reset_ts and now >= reset_ts then
                        redis.call('HSET', credential_key, 'requests_remaining', 5)
                        redis.call('HSET', credential_key, 'reset_timestamp', '')
                    end
                end
            
                local requests_remaining = tonumber(redis.call('HGET', credential_key, 'requests_remaining') or '0')
                local in_flight = tonumber(redis.call('HGET', credential_key, 'in_flight') or '0')
            
                if requests_remaining > 0 and in_flight < max_concurrent then
                    redis.call('HINCRBY', credential_key, 'requests_remaining', -1)
                    redis.call('HINCRBY', credential_key, 'in_flight', 1)
                    return cjson.encode({ ok = true, credential_key = credential_key })
                end
            
                return cjson.encode({ ok = false, code = 'UNAVAILABLE' })
            end
            
            local credentials = redis.call('SMEMBERS', KEYS[3])
            for _, credential_key in ipairs(credentials) do
                local ctype = redis.call('HGET', credential_key, 'credential_type')
            
                if requested_type == '' or ctype == requested_type then
                    local blocked_until_raw = redis.call('HGET', credential_key, 'blocked_until')
            
                    local blocked = false
                    if blocked_until_raw and blocked_until_raw ~= '' then
                        local blocked_until
                        if blocked_until_raw == 'inf' then
                            blocked_until = math.huge
                        else
                            blocked_until = tonumber(blocked_until_raw)
                        end
            
                        if blocked_until and now < blocked_until then
                            blocked = true
                        end
                    end
            
                    if not blocked then
                        local reset_ts_raw = redis.call('HGET', credential_key, 'reset_timestamp')
                        if reset_ts_raw and reset_ts_raw ~= '' then
                            local reset_ts = tonumber(reset_ts_raw)
                            if reset_ts and now >= reset_ts then
                                redis.call('HSET', credential_key, 'requests_remaining', 5)
                                redis.call('HSET', credential_key, 'reset_timestamp', '')
                            end
                        end
            
                        local requests_remaining = tonumber(redis.call('HGET', credential_key, 'requests_remaining') or '0')
                        local in_flight = tonumber(redis.call('HGET', credential_key, 'in_flight') or '0')
            
                        if requests_remaining > 0 and in_flight < max_concurrent then
                            redis.call('HINCRBY', credential_key, 'requests_remaining', -1)
                            redis.call('HINCRBY', credential_key, 'in_flight', 1)
                            return cjson.encode({ ok = true, credential_key = credential_key })
                        end
                    end
                end
            end
            
            return cjson.encode({ ok = false, code = 'NO_CREDENTIALS' })
            """)

    @property
    def _release_script(self):
        return self._redis.register_script("""
            local in_flight = tonumber(redis.call('HGET', KEYS[1], 'in_flight') or '0')
            if in_flight > 0 then
                redis.call('HINCRBY', KEYS[1], 'in_flight', -1)
            end
            return 1
            """)

    @property
    def _block_credential_script(self):
        return self._redis.register_script("""
            local retry_after = ARGV[1]
            local reason = ARGV[2]
            local discord_error_code = ARGV[3]
            local now = tonumber(ARGV[4])

            local blocked_until = 'inf'
            if retry_after ~= '' then
                blocked_until = tostring(now + tonumber(retry_after))
            end

            redis.call('HSET', KEYS[1],
                'blocked_until', blocked_until,
                'block_reason', reason,
                'discord_error_code', discord_error_code
            )

            return 1
            """)

    @property
    def _unblock_credential_script(self):
        return self._redis.register_script("""
            redis.call('HSET', KEYS[1],
                'blocked_until', '',
                'block_reason', '',
                'discord_error_code', ''
            )
            return 1
            """)

    @property
    def _update_from_headers_script(self):
        return self._redis.register_script("""
            local remaining = ARGV[1]
            local reset = ARGV[2]

            if remaining ~= '' then
                redis.call('HSET', KEYS[1], 'requests_remaining', remaining)
            end

            if reset ~= '' then
                redis.call('HSET', KEYS[1], 'reset_timestamp', reset)
            end

            return 1
            """)

    # ------------------------------------------------------------------
    # Public serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        meta = decode_redis_hash(self._redis.hgetall(self._meta_key()))
        credential_keys = [
            k.decode() if isinstance(k, bytes) else k
            for k in self._redis.smembers(self._credentials_set_key())
        ]

        bots = []
        webhooks = []

        for credential_key in credential_keys:
            state = CredentialState.from_redis_hash(self._redis.hgetall(credential_key))
            if state.credential_type == "bot":
                bots.append(state.to_dict())
            elif state.credential_type == "webhook":
                webhooks.append(state.to_dict())

        channels = [
            c.decode() if isinstance(c, bytes) else c
            for c in self._redis.lrange(self._channels_key(), 0, -1)
        ]

        blocked_until_raw = meta.get("blocked_until")
        if blocked_until_raw == "inf":
            blocked_until = float("inf")
        elif blocked_until_raw in (None, "", "None"):
            blocked_until = None
        else:
            blocked_until = float(blocked_until_raw)

        return {
            "user_id": self.user.id,
            "guild_id": meta.get("guild_id"),
            "channels": channels,
            "max_concurrent_per_token": int(meta.get("max_concurrent_per_token", self.max_concurrent_per_token)),
            "_blocked_until": normalize_blocked_until(blocked_until),
            "bots": bots,
            "webhooks": webhooks,
        }

    # ------------------------------------------------------------------
    # Initialization from Django DB into Redis
    # ------------------------------------------------------------------

    def _initialize(self):
        settings = DiscordSettings.objects.get(user=self.user)
        bots = Bot.objects.filter(owner=self.user)
        webhooks = Webhook.objects.filter(owner=self.user)
        channels = Channel.objects.filter(owner=self.user)

        if not settings.auto_setup_complete:
            raise BadRequestError("No discord settings. Perform auto complete")

        pipe = self._redis.pipeline()

        pipe.delete(self._meta_key())
        pipe.delete(self._channels_key())
        pipe.delete(self._credentials_by_secret_key())

        existing = self._redis.smembers(self._credentials_set_key())
        if existing:
            pipe.delete(*existing)

        pipe.delete(self._credentials_set_key())

        pipe.hset(self._meta_key(), mapping={
            "guild_id": settings.guild_id,
            "max_concurrent_per_token": self.max_concurrent_per_token,
            "blocked_until": "",
        })

        channel_ids = [c.discord_id for c in channels]
        if channel_ids:
            pipe.rpush(self._channels_key(), *channel_ids)

        states = [CredentialState.new_bot(bot) for bot in bots]
        states.extend(CredentialState.new_webhook(webhook) for webhook in webhooks)

        for state in states:
            credential_key = self._credential_key(state.secret)
            pipe.hset(credential_key, mapping=state.to_redis_hash())
            pipe.hset(self._credentials_by_secret_key(), state.secret, credential_key)
            pipe.sadd(self._credentials_set_key(), credential_key)

        pipe.execute()

    # ------------------------------------------------------------------
    # Global block
    # ------------------------------------------------------------------

    def ensure_not_blocked(self):
        blocked_until_raw = self._redis.hget(self._meta_key(), "blocked_until")
        if blocked_until_raw in (None, "", "None"):
            return

        if blocked_until_raw == "inf":
            remaining = float("inf")
            raise DiscordBlockError("Discord temporarily blocked us :(", retry_after=remaining)

        blocked_until = float(blocked_until_raw)
        now = time.time()

        if now < blocked_until:
            remaining = blocked_until - now
            raise DiscordBlockError("Discord temporarily blocked us :(", retry_after=remaining)

        self._redis.hset(self._meta_key(), "blocked_until", "")

    # ------------------------------------------------------------------
    # Acquire
    # ------------------------------------------------------------------

    def _acquire(self, credential_type: Optional[CredentialType] = None, secret: Optional[str] = None) -> CredentialState:
        result_raw = self._acquire_script(
            keys=[self._meta_key(), self._credentials_by_secret_key(), self._credentials_set_key()],
            args=[time.time(), self.max_concurrent_per_token, credential_type or "", secret or ""],
        )

        result = json.loads(result_raw)

        if result["ok"]:
            return CredentialState.from_redis_hash(self._redis.hgetall(result["credential_key"]))

        code = result["code"]

        if code == "GLOBAL_BLOCK":
            raise DiscordBlockError("Discord temporarily blocked us :(", retry_after=result["retry_after"])
        if code == "NOT_FOUND":
            raise CannotProcessDiscordRequestError("Requested credential not found")
        if code == "TYPE_MISMATCH":
            raise CannotProcessDiscordRequestError("Credential type mismatch")
        if code == "CREDENTIAL_BLOCKED":
            raise CannotProcessDiscordRequestError("Credential is temporarily blocked")
        if code == "UNAVAILABLE":
            raise CannotProcessDiscordRequestError("Credential currently unavailable")
        if code == "NO_CREDENTIALS":
            raise CannotProcessDiscordRequestError("No credentials available right now")

        raise CannotProcessDiscordRequestError(f"Unexpected acquire error: {code}")

    def acquire_token(self, bot: Optional["Bot"] = None) -> CredentialState:
        secret = bot.token if bot else None
        return self._acquire("bot", secret)

    def acquire_webhook(self, webhook: Optional["Webhook"] = None) -> CredentialState:
        secret = webhook.url if webhook else None
        return self._acquire("webhook", secret)

    # ------------------------------------------------------------------
    # Release
    # ------------------------------------------------------------------
    def release(self, credential: CredentialState):
        self._release_script(keys=[self._credential_key(credential.secret)], args=[])

    # ------------------------------------------------------------------
    # Block / unblock credential
    # ------------------------------------------------------------------

    def block_credential(self, credential: CredentialState, retry_after_seconds: Optional[float], reason: str, discord_error_code: int):
        self._block_credential_script(
            keys=[self._credential_key(credential.secret)],
            args=[
                "" if retry_after_seconds is None else float(retry_after_seconds),
                reason or "",
                "" if discord_error_code is None else int(discord_error_code),
                float(time.time()),
            ]
        )

    def unblock_credential(self, credential: CredentialState):
        self._unblock_credential_script(keys=[self._credential_key(credential.secret)], args=[])

    # ------------------------------------------------------------------
    # Lookup by discord credential id
    # ------------------------------------------------------------------

    def get_credential_from_id(self, credential_id: str) -> Optional[CredentialState]:
        credential_keys = [
            k.decode() if isinstance(k, bytes) else k
            for k in self._redis.smembers(self._credentials_set_key())
        ]

        for credential_key in credential_keys:
            data = decode_redis_hash(self._redis.hgetall(credential_key))

            if data.get("discord_id") == credential_id:
                return CredentialState.from_redis_hash(data)

        return None

    # ------------------------------------------------------------------
    # Update from headers
    # ------------------------------------------------------------------

    def update_from_headers(self, credential: CredentialState, headers: dict):
        remaining = headers.get("X-RateLimit-Remaining")
        reset = headers.get("X-RateLimit-Reset")

        self._update_from_headers_script(
            keys=[self._credential_key(credential.secret)],
            args=[
                "" if remaining is None else int(remaining),
                "" if reset is None else float(reset),
            ],
        )

    def get_all_credentials(self) -> Dict[str, CredentialState]:
        result = {}

        for k in self._redis.smembers(self._credentials_set_key()):
            key = k.decode() if isinstance(k, bytes) else k
            data = self._redis.hgetall(key)
            c = CredentialState.from_redis_hash(data)
            result[c.secret] = c

        return result
