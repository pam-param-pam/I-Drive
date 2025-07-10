import logging
import time
from datetime import datetime, timezone
from threading import Lock
from typing import Union
from urllib.parse import urlparse, parse_qs

import httpx
from httpx import Response

from ..models import DiscordSettings, Bot, Webhook, Channel
from ..utilities.constants import cache, DISCORD_BASE_URL, EventCode
from ..utilities.errors import DiscordError, DiscordBlockError, CannotProcessDiscordRequestError, BadRequestError

logger = logging.getLogger("Discord")
logger.setLevel(logging.DEBUG)

if not logger.hasHandlers():
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)


class Discord:

    def __init__(self):
        self.client = httpx.Client(http2=True, timeout=10.0)
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
        channels = [channel.id for channel in channels]
        with self.lock:
            self.users_state[user.id] = {"channels": channels, "guild_id": settings.guild_id, "bots": bots_dict, "blocked": False}

    def remove_user_state(self, user):
        logger.debug("Removing user state")
        with self.lock:
            try:
                del self.users_state[user.id]
            except KeyError:
                pass

    def _get_channel_id(self, user, message_id=None):
        from ..utilities.other import query_attachments

        attachments = query_attachments(message_id=message_id)
        if len(attachments) > 0:
            return attachments[0].channel_id

        raise DiscordError(f"Unable to find channel id associated with message ID={message_id}")

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
                bot_dict['requests_remaining'] = min(int(requests_remaining), int(bot_dict['requests_remaining']-1))
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
        except KeyError:
            logger.debug("Key Error attachments, message: ")
            logger.debug(message)

    def _make_request(self, method: str, url: str, headers: dict = None, params: dict = None, json: dict = None, files: dict = None, timeout: Union[int, None] = 3):
        start = time.perf_counter()
        response = self.client.request(method, url, headers=headers, params=params, json=json, files=files, timeout=timeout)
        print(f"⏱  _make_request took {time.perf_counter() - start:.4f} seconds")
        return response

    def _make_bot_request(self, user, method: str, url: str, headers: dict = None, params: dict = None, json: dict = None, files: dict = None, timeout: Union[int, None] = 3) -> Response:
        self._check_discord_block(user)

        if not headers:
            headers = {}

        token = headers.get('Authorization')
        if token:
            token = token.replace("Bot ", "")
        try:
            if not token:
                token = self._get_token(user)
                headers['Authorization'] = f'Bot {token}'

            logger.debug(f"Making bot request with token: {token}")
            start_time = time.monotonic()

            response = self._make_request(method, url, headers=headers, params=params, json=json, files=files, timeout=timeout)
            duration = time.monotonic() - start_time

            print(f"⏱ _make_bot_request took {duration:.3f} seconds")

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

            if response.status_code in (403, 401):
                raise DiscordError(response.text, response.status_code)

        finally:
            try:
                self._update_token(user, token, response.headers)
            except:
                self.remove_user_state(user)

    def _make_webhook_request(self, user, method: str, url: str, headers: dict = None, params: dict = None, json: dict = None, files: dict = None, timeout: Union[int, None] = 3):

        logger.debug(f"Making webhook request: {url}")

        response = self._make_request(method, url, headers=headers, params=params, json=json, files=files, timeout=timeout)
        # todo implement ratelimit for webhooks

        if not response.is_success:
            if response.status_code in (403, 401):
                from ..tasks import queue_ws_event
                webhook = Webhook.objects.get(owner=user, url=url)
                queue_ws_event.delay('user', {'type': 'send_message', 'op_code': EventCode.MESSAGE_SENT.value, 'user_id': user.id, 'message': "toasts.webhook403",
                                              'args': {"name": webhook.name}, 'finished': True, 'error': True})

            raise DiscordError(response.text, response.status_code)

        return response

    def send_message(self, user, message: str) -> httpx.Response:
        channel_id = self._get_channel_id(user)
        url = f'{DISCORD_BASE_URL}/channels/{channel_id}/messages'
        payload = {'content': message}
        headers = {"Content-Type": 'application/json'}

        response = self._make_bot_request(user, 'POST', url, headers=headers, json=payload)
        return response

    # def send_file(self, user, files: dict, json=None) -> httpx.Response:
    #     channel_id = self._get_channel_id(user)
    #
    #     url = f'{DISCORD_BASE_URL}/channels/{channel_id}/messages'
    #
    #     response = self._make_bot_request(user, 'POST', url, files=files, json=json, timeout=None)
    #     message = response.json()
    #     expiry = self._calculate_expiry(message)
    #     cache.set(message["id"], response, timeout=expiry)
    #
    #     return message

    def send_file(self, user, files: dict, json=None) -> httpx.Response:
        channel_id = self._get_channel_id(user)
        url = f'{DISCORD_BASE_URL}/channels/{channel_id}/messages'
        response = self._make_bot_request(user, 'POST', url, files=files, json=json, timeout=None)

        message = response.json()
        expiry = self._calculate_expiry(message)
        cache.set(message["id"], response, timeout=expiry)

        return message

    def get_attachment_url(self, user, resource: Union['Fragment', 'Thumbnail', 'Preview', 'Moment', 'Subtitle']) -> str:
        start = time.perf_counter()
        result = self.get_file_url(user, resource.message_id, resource.attachment_id, resource.channel_id)
        print(f"⏱ get_attachment_url took {time.perf_counter() - start:.4f} seconds")
        return result

    def get_file_url(self, user, message_id: str, attachment_id: str, channel_id: str) -> str:
        start = time.perf_counter()
        message = self.get_message(user, message_id, channel_id).json()
        for attachment in message["attachments"]:
            if attachment["id"] == attachment_id:
                print(f"⏱ get_file_url took {time.perf_counter() - start:.4f} seconds")
                return attachment["url"]
        raise DiscordError(f"File with {attachment_id} not found")

    def get_message(self, user, message_id: str, channel_id: str) -> httpx.Response:
        start = time.perf_counter()
        # cached_message = cache.get(message_id)
        # if cached_message:
        #     print(f"⚡ get_message served from cache in {time.perf_counter() - start:.4f} seconds")
        #     return cached_message

        url = f'{DISCORD_BASE_URL}/channels/{channel_id}/messages/{message_id}'
        response = self._make_bot_request(user, 'GET', url)

        message = response.json()
        expiry = self._calculate_expiry(message)
        cache.set(message["id"], response, timeout=expiry)
        print(f"⏱ get_message (non-cache) took {time.perf_counter() - start:.4f} seconds")
        return response

    def remove_message(self, user, message_id: str) -> httpx.Response:
        channel_id = self._get_channel_id(user, message_id)
        url = f'{DISCORD_BASE_URL}/channels/{channel_id}/messages/{message_id}'
        response = self._make_bot_request(user, 'DELETE', url)
        return response

    def edit_webhook_attachments(self, user, webhook, message_id, attachment_ids_to_keep) -> httpx.Response:
        attachments_to_keep = []
        for attachment_id in attachment_ids_to_keep:
            attachments_to_keep.append({"id": attachment_id})
        url = f"{webhook}/messages/{message_id}"
        response = self._make_webhook_request(user, 'PATCH', url, json={"attachments": attachments_to_keep})
        return response

    def edit_attachments(self, user, token, message_id, attachment_ids_to_keep) -> httpx.Response:
        channel_id = self._get_channel_id(user, message_id)
        url = f'{DISCORD_BASE_URL}/channels/{channel_id}/messages/{message_id}'

        attachments_to_keep = []
        for attachment_id in attachment_ids_to_keep:
            attachments_to_keep.append({"id": attachment_id})

        headers = {'Authorization': f'Bot {token}'}
        response = self._make_bot_request(user, 'PATCH', url, json={"attachments": attachments_to_keep}, headers=headers)
        return response

    def fetch_messages(self, user, channel_id):
        # todo
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
