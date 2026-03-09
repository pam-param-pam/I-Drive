import json
import logging
import random
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from threading import Lock
from typing import Optional, Dict, Literal, Any
from urllib.parse import urlparse, parse_qs

import httpx
from httpx import Response

from ..constants import DISCORD_BASE_URL, cache, USE_CACHE
from ..core.errors import DiscordError, DiscordBlockError, CannotProcessDiscordRequestError, BadRequestError, DiscordTextError, DiscordErrorMaxRetries
from ..core.helpers import normalize_blocked_until
from ..models import DiscordSettings, Bot, Channel, DiscordAttachmentMixin, Fragment, Thumbnail, FragmentLink, ThumbnailLink, Webhook
from ..queries.selectors import query_attachments
from ..services import cache_service

logger = logging.getLogger("Discord")
logger.setLevel(logging.INFO)

if not logger.hasHandlers():
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

CredentialType = Literal["bot", "webhook"]

@dataclass
class CredentialState:
    name: str
    secret: str          # bot token or webhook url
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

class UserState:
    def __init__(self, user, max_concurrent_per_token: int = 3):
        self.user = user
        self.max_concurrent_per_token = max_concurrent_per_token

        self.guild_id: Optional[str] = None
        self.channels: list[str] = []

        self._credentials: Dict[str, CredentialState] = {}
        self._blocked_until: Optional[float] = None

        self._lock = Lock()

        self._initialize()

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            bots = []
            webhooks = []

            for state in self._credentials.values():
                if state.credential_type == "bot":
                    bots.append(state.to_dict())
                elif state.credential_type == "webhook":
                    webhooks.append(state.to_dict())

            return {
                "user_id": self.user.id,
                "guild_id": self.guild_id,
                "channels": self.channels,
                "max_concurrent_per_token": self.max_concurrent_per_token,
                "_blocked_until": normalize_blocked_until(self._blocked_until),
                "bots": bots,
                "webhooks": webhooks,
            }

    def _initialize(self):
        settings = DiscordSettings.objects.get(user=self.user)
        bots = Bot.objects.filter(owner=self.user).order_by("created_at")
        webhooks = Webhook.objects.filter(owner=self.user).order_by("created_at")
        channels = Channel.objects.filter(owner=self.user)

        if not settings.auto_setup_complete:
            raise BadRequestError("No discord settings. Perform auto complete")

        self.guild_id = settings.guild_id
        self.channels = [c.discord_id for c in channels]

        for bot in bots:
            self._credentials[bot.token] = CredentialState(
                secret=bot.token,
                credential_type="bot",
                discord_id=bot.discord_id,
                name=bot.name,
                requests_remaining=5,
                reset_timestamp=None,
            )

        for webhook in webhooks:
            self._credentials[webhook.url] = CredentialState(
                secret=webhook.url,
                credential_type="webhook",
                name=webhook.name,
                discord_id=webhook.discord_id,
                requests_remaining=5,
                reset_timestamp=None,
            )

    def ensure_not_blocked(self):
        with self._lock:
            if self._blocked_until:
                if time.time() < self._blocked_until:
                    remaining = self._blocked_until - time.time()
                    raise DiscordBlockError("Discord temporarily blocked us :(", retry_after=remaining)
                self._blocked_until = None

    def _acquire(self, credential_type: Optional[CredentialType] = None, secret: Optional[str] = None) -> CredentialState:
        self.ensure_not_blocked()
        now = time.time()

        with self._lock:
            # If specific secret requested
            if secret:
                state = next((c for c in self._credentials.values() if c.secret == secret), None)
                if not state:
                    raise CannotProcessDiscordRequestError("Requested credential not found")

                if credential_type and state.credential_type != credential_type:
                    raise CannotProcessDiscordRequestError("Credential type mismatch")

                if state.blocked_until and now < state.blocked_until:
                    raise CannotProcessDiscordRequestError("Credential is temporarily blocked")

                if state.reset_timestamp and now >= state.reset_timestamp:
                    state.requests_remaining = 5
                    state.reset_timestamp = None

                if state.requests_remaining > 0 and state.in_flight < self.max_concurrent_per_token:
                    state.requests_remaining -= 1
                    state.in_flight += 1
                    return state

                raise CannotProcessDiscordRequestError("Credential currently unavailable")

            # Otherwise iterate normally
            for state in self._credentials.values():

                if credential_type and state.credential_type != credential_type:
                    continue

                if state.blocked_until and now < state.blocked_until:
                    continue

                if state.reset_timestamp and now >= state.reset_timestamp:
                    state.requests_remaining = 5
                    state.reset_timestamp = None

                if state.requests_remaining > 0 and state.in_flight < self.max_concurrent_per_token:
                    state.requests_remaining -= 1
                    state.in_flight += 1
                    return state

        raise CannotProcessDiscordRequestError("No credentials available right now")

    def acquire_token(self, bot: Optional[Bot] = None) -> CredentialState:
        secret = bot.token if bot else None
        return self._acquire("bot", secret)

    def acquire_webhook(self, webhook: Optional[Webhook] = None) -> CredentialState:
        secret = webhook.url if webhook else None
        return self._acquire("webhook", secret)

    def release(self, credential: CredentialState):
        with self._lock:
            if credential.in_flight > 0:
                credential.in_flight -= 1

    def block_credential(self, credential: CredentialState, retry_after_seconds: Optional[float], reason: str, discord_error_code: int):
        with self._lock:
            credential.block_reason = reason
            credential.discord_error_code = discord_error_code

            if retry_after_seconds is None:
                # Permanent block
                credential.blocked_until = float("inf")
            else:
                credential.blocked_until = time.time() + float(retry_after_seconds)

    def get_credential_from_id(self, credential_id: str) -> Optional[CredentialState]:
        with self._lock:
            for cred in self._credentials.values():
                if cred.discord_id == credential_id:
                    return cred
            return None

    def unblock_credential(self, credential: CredentialState):
        with self._lock:
            credential.blocked_until = None
            credential.block_reason = ""
            credential.discord_error_code = None

    def update_from_headers(self, credential: CredentialState, headers: dict):
        remaining = headers.get("X-RateLimit-Remaining")
        reset = headers.get("X-RateLimit-Reset")

        with self._lock:
            if remaining is not None:
                credential.requests_remaining = int(remaining)

            if reset is not None:
                credential.reset_timestamp = float(reset)

class RawDiscordAPI:
    def __init__(self, timeout: float = 10.0):
        self.base_url = DISCORD_BASE_URL
        self.client = httpx.Client(timeout=timeout)

    def request(self, method: str, path: str, token: Optional[str] = None, params: dict = None, json: dict = None, files: dict = None, headers: dict = None) -> httpx.Response:
        if headers is None:
            headers = {}

        if token:
            headers["Authorization"] = f"Bot {token}"

        url = f"{self.base_url}{path}"

        return self.client.request(
            method=method,
            url=url,
            params=params,
            json=json,
            files=files,
            headers=headers,
        )


class DiscordManager:
    MAX_RETRIES = 5

    def __init__(self):
        self._raw = RawDiscordAPI()
        self._users: dict[int, UserState] = {}
        self._lock = Lock()

    def _get_user_state(self, user) -> UserState:
        with self._lock:
            if user.id not in self._users:
                self._users[user.id] = UserState(user)
            return self._users[user.id]

    def remove_user_state(self, user) -> None:
        with self._lock:
            self._users.pop(user.id, None)

    def _post_request_check(self, state: UserState, credential: CredentialState, response):
        if response.is_success:
            return

        status = response.status_code

        try:
            data = response.json()
        except Exception:
            data = {}

        print(response.text)
        discord_code = data.get("code")
        if status == 401:
            state.block_credential(credential, None, "unauthorized", discord_code)
            return

        if status == 403:
            state.block_credential(credential, None, "forbidden", discord_code)
            return

        if status == 404:
            # 10015: Unknown Webhook
            # 10008: Unknown Message
            # 10003: Unknown Channel
            if discord_code in (10015, 10003):
                state.block_credential(credential, None, "notFound", discord_code)
            return

        if status == 429:
            is_global = data.get("global", False)
            if is_global:
                state.block_credential(credential, None, "cloudflareGlobalLimit", discord_code)
                return

    def execute_bot_once(self, user, method: str, url: str, bot: Optional[Bot] = None, json=None, params=None, files=None):
        state = self._get_user_state(user)
        credential = state.acquire_token(bot)

        headers = {}
        if credential.credential_type == "bot":
            headers["Authorization"] = f"Bot {credential.secret}"

        try:
            response = self._raw.request(
                method=method,
                path=url,
                headers=headers,
                json=json,
                params=params,
                files=files,
            )
            self._post_request_check(state, credential, response)

            # todo fix this to ensure its ALWAYS called
            state.update_from_headers(credential, response.headers)

            if response.is_error:
                raise DiscordError(response)

        finally:
            state.release(credential)

        return response

    def execute_bot_with_retries(self, user, method: str, url: str, bot: Optional[Bot] = None, json=None, params=None, files=None):
        errors = []

        for attempt in range(1, self.MAX_RETRIES + 1):
            response = self.execute_bot_once(user, method, url, bot=bot, json=json, params=params, files=files)

            if response.is_success:
                return response

            errors.append(response)

            if response.status_code == 429:
                retry_after = response.json().get("retry_after", 1)
                time.sleep(float(retry_after))
                continue

            if response.status_code in {500, 502, 503, 504}:
                time.sleep(min(2 ** attempt, 30))
                continue

            raise DiscordError(response)

        raise DiscordErrorMaxRetries(errors)

    def execute_webhook_once(self, user, method: str, path: str, webhook: Optional[Webhook] = None, json=None, params=None, files=None):
        state = self._get_user_state(user)
        credential = state.acquire_webhook(webhook)

        url = f"{credential.secret}{path}"

        try:
            response = self._raw.client.request(
                method=method,
                url=url,
                json=json,
                params=params,
                files=files,
            )
            self._post_request_check(state, credential, response)
            if response.is_error:
                raise DiscordError(response)

        finally:
            state.release(credential)

        return response

    def execute_webhook_with_retries(self, user, method: str, path: str, webhook: Optional[Webhook] = None, json=None, params=None, files=None):
        errors = []

        for attempt in range(1, self.MAX_RETRIES + 1):
            response = self.execute_webhook_once(user, method, path=path, webhook=webhook, json=json, params=params, files=files)

            if response.is_success:
                return response

            errors.append(response)

            if response.status_code == 429:
                retry_after = response.json().get("retry_after", 1)
                time.sleep(float(retry_after))
                continue

            if response.status_code in {500, 502, 503, 504}:
                time.sleep(min(2 ** attempt, 30))
                continue

            raise DiscordError(response)

        raise DiscordErrorMaxRetries(errors)


class DiscordService:
    def __init__(self, base_url: str = DISCORD_BASE_URL):
        self.manager = DiscordManager()
        self.base_url = base_url

    # -------------------------
    # Internal helpers
    # -------------------------
    def remove_user_state(self, user):
        self.manager.remove_user_state(user)

    def get_author(self, message_id):
        attachments = query_attachments(message_id=message_id)
        if attachments:
            return attachments[0].author
        raise DiscordTextError(f"Unable to find author associated with message ID={message_id}", 404)

    def _get_user_state(self, user) -> UserState:
        return self.manager._get_user_state(user)

    def _choose_channel_id(self, user) -> str:
        state = self._get_user_state(user)
        if not state.channels:
            raise BadRequestError("User has no channels configured")
        return random.choice(state.channels)

    def _get_channel_id_for_message(self, message_id: str) -> str:
        attachments = query_attachments(message_id=message_id)
        if attachments:
            return attachments[0].channel.discord_id
        raise DiscordTextError(f"Unable to find channel id associated with message ID={message_id}", 404)

    def _calculate_expiry(self, message: dict) -> float:
        try:
            url = message["attachments"][0]["url"]
            parsed_url = urlparse(url)
            query_params = parse_qs(parsed_url.query)
            ex_param = query_params.get("ex", [None])[0]
            if ex_param is None:
                raise ValueError("The 'ex' parameter is missing in the URL")
            expiry_timestamp = int(ex_param, 16)
            expiry_datetime = datetime.utcfromtimestamp(expiry_timestamp)
            current_datetime = datetime.utcnow()
            ttl_seconds = (expiry_datetime - current_datetime).total_seconds()
            return max(ttl_seconds, 0)
        except (KeyError, IndexError, ValueError):
            return 60 * 60 * 24

    def _discord_path(self, path: str) -> str:
        # append / if needed
        return path if path.startswith("/") else f"/{path}"

    # -------------------------
    # Core Discord operations (bot)
    # -------------------------

    def get_message(self, user, channel_id: str, message_id: str) -> dict:
        key = cache_service.get_discord_message_key(message_id)
        cached = cache.get(key)
        if cached and USE_CACHE:
            return cached

        path = self._discord_path(f"/channels/{channel_id}/messages/{message_id}")
        response = self.manager.execute_bot_once(user, "GET", path)
        message = response.json()
        key = cache_service.get_discord_message_key(message["id"])
        cache.set(key, message, timeout=self._calculate_expiry(message))
        return message

    def delete_message(self, user, channel_id, message_id: str) -> Response:
        path = self._discord_path(f"/channels/{channel_id}/messages/{message_id}")
        return self.manager.execute_bot_with_retries(user, "DELETE", path)

    def _get_file_url(self, user, message_id: str, attachment_id: str, channel_id: str) -> str:
        message = self.get_message(user, channel_id, message_id)
        for attachment in message.get("attachments", []):
            if attachment.get("id") == attachment_id:
                return attachment.get("url")
        raise BadRequestError(f"File with attachment_id={attachment_id} not found in message_id={message_id}")

    def _get_from_linker(self, user, resource: Fragment | Thumbnail) -> Optional[str]:
        if isinstance(resource, Fragment):
            link = FragmentLink.objects.select_related("linker").filter(fragment=resource).first()
        elif isinstance(resource, Thumbnail):
            link = ThumbnailLink.objects.select_related("linker").filter(thumbnail=resource).first()
        else:
            raise KeyError(f"Resource type {type(resource)} is not supported for linker")

        if not link:
            return None

        message = self.get_message(user, link.linker.channel.discord_id, link.linker.message_id)
        seq = link.sequence

        if 1 <= seq <= 10:
            return message.get("content", "").split("\n")[seq - 1] if message.get("content") else None

        embeds = message.get("embeds") or []
        if not embeds:
            return None
        embed = embeds[0]

        if 11 <= seq <= 31:
            return (embed.get("description") or "").split("\n")[seq - 11] if embed.get("description") else None

        fields = embed.get("fields") or []

        if 32 <= seq <= 36 and len(fields) > 0:
            return (fields[0].get("value") or "").split("\n")[seq - 32] if fields[0].get("value") else None

        if 37 <= seq <= 41 and len(fields) > 1:
            return (fields[1].get("value") or "").split("\n")[seq - 37] if fields[1].get("value") else None

        if seq == 42 and len(fields) > 2:
            return (fields[2].get("value") or "").split("\n")[0] if fields[2].get("value") else None

        return None

    def get_attachment_url(self, user, resource: DiscordAttachmentMixin) -> str:
        if isinstance(resource, Fragment):
            linked = self._get_from_linker(user, resource)
            if linked:
                return linked
        return self._get_file_url(user, resource.message_id, resource.attachment_id, resource.channel.discord_id)

    # -------------------------
    # Attachment editing
    # -------------------------
    def edit_attachments_webhook(self, user, webhook: Webhook, message_id: str, attachment_ids_to_keep: list[str]) -> httpx.Response:
        payload = {"attachments": [{"id": a_id} for a_id in attachment_ids_to_keep]}
        print(payload)
        path = self._discord_path(f"/messages/{message_id}")
        return self.manager.execute_webhook_with_retries(user, "PATCH", path, webhook, json=payload)

    # -------------------------
    # Fetch / pagination
    # -------------------------

    def fetch_messages(self, user, channel_id: str, limit: int = 100):
        path = self._discord_path(f"/channels/{channel_id}/messages")
        params = {"limit": int(limit)}
        errors = 0

        while True:
            try:
                response = self.manager.execute_with_retries(user, "GET", path, params=params)
                batch = response.json()
                if not batch:
                    break
                yield batch
                params["before"] = batch[-1]["id"]
                errors = 0
            except CannotProcessDiscordRequestError:
                errors += 1
                if errors > 10:
                    raise CannotProcessDiscordRequestError("Unable to fetch more messages")
                time.sleep(1)

    def fetch_all_messages(self, user, channel_id: str, limit: int = 100):
        for batch in self.fetch_messages(user, channel_id, limit=limit):
            for msg in batch:
                yield msg

discord = DiscordService()
