import logging
import random
import time
import traceback
from datetime import datetime, timezone
from threading import Lock
from typing import Union
from urllib.parse import urlparse, parse_qs

import httpx
from httpx import Response

from ..constants import DISCORD_BASE_URL, cache
from ..models import DiscordSettings, Bot, Channel, DiscordAttachmentMixin, Fragment, Thumbnail, FragmentLink, ThumbnailLink
from ..core.errors import DiscordError, DiscordBlockError, CannotProcessDiscordRequestError, BadRequestError, HttpxError, DiscordTextError
from ..queries.selectors import query_attachments

logger = logging.getLogger("Discord")
logger.setLevel(logging.INFO)

if not logger.hasHandlers():
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)


class Discord:

    def __init__(self):
        self.client = httpx.Client(timeout=10.0)
        self.current_token_index = 0
        self.users_state = {}
        self.lock = Lock()
        self.MAX_CONCURRENT_REQUESTS_PER_TOKEN = 3

    def _get_user_state(self, user):
        user_state = self.users_state.get(user.id)
        if not user_state:
            self._set_user_state(user)
        return self.users_state.get(user.id)

    def _set_user_state(self, user):
        logger.debug("===obtaining user state===")
        settings = DiscordSettings.objects.get(user=user)
        bots = Bot.objects.filter(owner=user).order_by('created_at')
        channels = Channel.objects.filter(owner=user)

        if len(bots) == 0:
            raise BadRequestError("User has no bots")

        bots_dict = {
            bot.token: {
                'name': bot.name,  # bot name
                'requests_remaining': 4,  # current remaining requests per bot/token
                'reset_time': None,  # reset time for remaining requests
                **{f'locked{i}': False for i in range(1, self.MAX_CONCURRENT_REQUESTS_PER_TOKEN + 1)},
            }
            for bot in bots
        }
        channels = [channel.discord_id for channel in channels]
        with self.lock:
            self.users_state[user.id] = {"channels": channels, "guild_id": settings.guild_id, "bots": bots_dict, "blocked": False}

    def remove_user_state(self, user):
        logger.debug("Removing user state")
        with self.lock:
            try:
                del self.users_state[user.id]
            except KeyError:
                pass

    def _get_channel_id(self, message_id):
        attachments = query_attachments(message_id=message_id)  # no change here?
        if len(attachments) > 0:
            return attachments[0].channel_id

        raise DiscordTextError(f"Unable to find channel id associated with message ID={message_id}", 404)

    def _get_channel_for_user(self, user) -> Channel:
        channels = Channel.objects.filter(owner=user).all()
        return random.choice(channels)

    def _handle_discord_block(self, user, response):
        logger.debug("HANDLING DISCORD BLOCK")
        retry_after = response.headers['retry-after']
        with self.lock:
            state = self.users_state[user.id]
            state['blocked'] = True
            current_time = time.time()
            retry_timestamp = current_time + retry_after
            state['retry_timestamp'] = retry_timestamp

        raise DiscordBlockError(message="Discord is stupid :(", retry_after=retry_after)

    def _get_token(self, user):
        slept = 0
        while slept < 5:
            current_time = datetime.now(timezone.utc).timestamp()
            with self.lock:
                user_state = self._get_user_state(user)
                bots_dict = user_state["bots"]

                for token, data in bots_dict.items():
                    if data['requests_remaining'] > 1:
                        if self._acquire_token_lock(data):
                            data['requests_remaining'] -= 1
                            return token

                    if data['reset_time']:
                        reset_time = float(data['reset_time'])
                        if current_time >= reset_time:
                            data['requests_remaining'] = 1
                            if self._acquire_token_lock(data):
                                return token

            time.sleep(0.5)
            logger.debug(f"===sleeping==={slept}")
            slept += 0.5

        raise CannotProcessDiscordRequestError("Unable to process this request at the moment, server is too busy.")

    def _update_token(self, user, token: str, headers: dict):
        logger.debug(f"Updating token: {token}")
        reset_time = headers.get('X-RateLimit-Reset')
        requests_remaining = headers.get('X-RateLimit-Remaining')

        with self.lock:
            bot_dict = self._get_user_state(user)["bots"][token]
            self._release_token_lock(bot_dict)
            if requests_remaining and reset_time:
                bot_dict['reset_time'] = reset_time
                bot_dict['requests_remaining'] = min(int(requests_remaining), int(bot_dict['requests_remaining'] - 1))
            else:
                logger.warning("Missing ratelimit headers in response")

    def _acquire_token_lock(self, token_data):
        for i in range(1, self.MAX_CONCURRENT_REQUESTS_PER_TOKEN + 1):
            if not token_data[f"locked{i}"]:
                token_data[f"locked{i}"] = True
                return True
        return False

    def _release_token_lock(self, token_data):
        for i in range(1, self.MAX_CONCURRENT_REQUESTS_PER_TOKEN + 1):
            if token_data[f"locked{i}"]:
                token_data[f"locked{i}"] = False
                return True
        return False

    def _check_discord_block(self, user):
        if self._get_user_state(user)['blocked']:
            remaining_time = self._get_user_state(user)['retry_timestamp'] - time.time()
            if remaining_time > 0:
                raise DiscordBlockError(message="This view is protected, discord blocked you, try again later", retry_after=remaining_time)
            self.remove_user_state(user)

    def _calculate_expiry(self, message: dict) -> float:
        try:
            url = message["attachments"][0]["url"]
            parsed_url = urlparse(url)
            query_params = parse_qs(parsed_url.query)
            ex_param = query_params.get('ex', [None])[0]
            if ex_param is None:
                raise ValueError("The 'ex' parameter is missing in the URL")
            expiry_timestamp = int(ex_param, 16)
            expiry_datetime = datetime.utcfromtimestamp(expiry_timestamp)
            current_datetime = datetime.utcnow()
            ttl_seconds = (expiry_datetime - current_datetime).total_seconds()
            return ttl_seconds
        except (KeyError, IndexError):
            return 60 * 60 * 24  # default value

    def _make_request(self, method: str, url: str, headers: dict = None, params: dict = None, json: dict = None, files: dict = None, timeout: Union[int, None] = 3):
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            start = time.perf_counter()
            try:
                response = self.client.request(method, url, headers=headers, params=params, json=json, files=files, timeout=timeout)
                logger.debug(f"⏱  _make_request took {time.perf_counter() - start:.4f} seconds (Attempt {attempt})")
                return response
            except httpx.RequestError as e:
                logger.warning(f"Request failed (attempt {attempt}/{max_retries}): {e}")
                if attempt == max_retries:
                    raise
                time.sleep(1)

        raise RuntimeError("Error. _make_request returned no request")

    def _make_bot_request(self, user, method: str, url: str, headers: dict = None, params: dict = None, json: dict = None, files: dict = None, timeout: Union[int, None] = 3) -> Response:
        self._check_discord_block(user)

        if not headers:
            headers = {}

        token = headers.get('Authorization')
        if token:
            token = token.replace("Bot ", "")

        response = None
        try:
            if not token:
                token = self._get_token(user)
                headers['Authorization'] = f'Bot {token}'

            logger.debug(f"Making bot request with token: {token}")
            start_time = time.monotonic()

            response = self._make_request(method, url, headers=headers, params=params, json=json, files=files, timeout=timeout)
            duration = time.monotonic() - start_time

            logger.debug(f"⏱ _make_bot_request took {duration:.3f} seconds")

            if response.is_success:
                return response

            if response.status_code == 429:
                logger.debug("==============HIT 429!!!!!=============")
                retry_after = response.json().get("retry_after")
                if not retry_after:  # retry_after is missing if discord blocked us
                    self._handle_discord_block(user, response)

                token = self._get_token(user)
                headers['Authorization'] = f'Bot {token}'

                return self._make_bot_request(user, method, url, headers=headers, params=params, json=json, files=files, timeout=timeout)

            if not response.is_success:
                raise DiscordError(response)

        except httpx.RequestError as e:
            raise HttpxError(str(e))
        finally:
            try:
                if response:
                    self._update_token(user, token, response.headers)
            except Exception as e:
                logger.error(f"ERROR HAPPENED IN DISCORD, UNABLE TO HANDLE IT: {str(e)}")
                logger.error(traceback.print_exc())
                self.remove_user_state(user)

        raise RuntimeError("Something went wrong")

    def _make_webhook_request(self, method: str, url: str, headers: dict = None, params: dict = None, json: dict = None, files: dict = None, timeout: Union[int, None] = 3):
        logger.debug(f"Making webhook request: {url}")

        response = self._make_request(method, url, headers=headers, params=params, json=json, files=files, timeout=timeout)
        # todo implement ratelimit for webhooks

        if not response.is_success:
            raise DiscordError(response)

        return response

    def get_attachment_url(self, user, resource: DiscordAttachmentMixin) -> str:
        # todo validate the url is from discord, else reject
        start = time.perf_counter()
        if isinstance(resource, Fragment):
            link_url = self.get_from_linker(user, resource)
            if link_url:
                logger.info(f"⏱ get_attachment_url used linked! Took {time.perf_counter() - start:.4f} seconds")
                return link_url

        result = self.get_file_url(user, resource.message_id, resource.attachment_id, resource.channel_id)
        logger.info(f"⏱ get_attachment_url took {time.perf_counter() - start:.4f} seconds")
        return result

    def get_from_linker(self, user, resource: Fragment | Thumbnail):
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
            return message["content"].split("\n")[seq - 1]

        embed = message["embeds"][0]

        if 11 <= seq <= 31:
            return embed["description"].split("\n")[seq - 11]

        if 32 <= seq <= 36:
            return embed["fields"][0]["value"].split("\n")[seq - 32]

        if 37 <= seq <= 41:
            return embed["fields"][1]["value"].split("\n")[seq - 37]

        if seq == 42:
            return embed["fields"][2]["value"].split("\n")[0]

        return None

    def get_file_url(self, user, message_id: str, attachment_id: str, channel_id: str) -> str:
        start = time.perf_counter()
        message = self.get_message(user, channel_id, message_id)
        for attachment in message["attachments"]:
            if attachment["id"] == attachment_id:
                logger.info(f"⏱ get_file_url took {time.perf_counter() - start:.4f} seconds")
                return attachment["url"]

        raise BadRequestError(f"File with {attachment_id} not found in the db")

    def get_message(self, user, channel_id: str, message_id: str) -> dict:
        start = time.perf_counter()
        cached_message = cache.get(message_id)
        if cached_message:
            logger.info(f"⚡ get_message served from cache in {time.perf_counter() - start:.4f} seconds")
            return cached_message

        url = f'{DISCORD_BASE_URL}/channels/{channel_id}/messages/{message_id}'
        response = self._make_bot_request(user, 'GET', url)
        message = response.json()
        expiry = self._calculate_expiry(message)
        cache.set(message["id"], message, timeout=expiry)
        logger.info(f"⏱ get_message (non-cache) took {time.perf_counter() - start:.4f} seconds")
        return message

    def remove_message(self, user, message_id: str) -> httpx.Response:
        channel_id = self._get_channel_id(message_id)
        url = f'{DISCORD_BASE_URL}/channels/{channel_id}/messages/{message_id}'
        response = self._make_bot_request(user, 'DELETE', url)
        return response

    def edit_webhook_attachments(self, webhook, message_id, attachment_ids_to_keep) -> httpx.Response:
        attachments_to_keep = []
        for attachment_id in attachment_ids_to_keep:
            attachments_to_keep.append({"id": attachment_id})
        url = f"{webhook}/messages/{message_id}"
        response = self._make_webhook_request('PATCH', url, json={"attachments": attachments_to_keep})
        return response

    def edit_attachments(self, user, token, message_id, attachment_ids_to_keep) -> httpx.Response:
        channel_id = self._get_channel_id(message_id)
        url = f'{DISCORD_BASE_URL}/channels/{channel_id}/messages/{message_id}'

        attachments_to_keep = []
        for attachment_id in attachment_ids_to_keep:
            attachments_to_keep.append({"id": attachment_id})

        headers = {'Authorization': f'Bot {token}'}
        response = self._make_bot_request(user, 'PATCH', url, json={"attachments": attachments_to_keep}, headers=headers)
        return response
    
    def fetch_messages(self, user, channel_id):
        # todo fix this
        url = f"{DISCORD_BASE_URL}/channels/{channel_id}/messages"
        params = {"limit": 100}
        number_of_errors = 0
        while True:
            try:
                res = self._make_bot_request(user, "GET", url, params=params)

                batch = res.json()
                if not batch:
                    break

                yield batch
                params["before"] = batch[-1]["id"]
                number_of_errors = 0
            except CannotProcessDiscordRequestError:
                if number_of_errors > 10:
                    raise CannotProcessDiscordRequestError("Unable to fetch more messages")
                number_of_errors += 1
                time.sleep(1)


discord = Discord()
