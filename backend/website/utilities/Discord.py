import logging
import time
from datetime import datetime, timezone
from threading import Lock
from typing import Union
from urllib.parse import urlparse, parse_qs

import httpx
from httpx import Response

from ..models import DiscordSettings, Bot, Webhook
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
        self.client = httpx.Client(timeout=10.0)
        self.current_token_index = 0
        self.users_state = {}
        self.lock = Lock()
        self.MAX_CONCURRENT_REQUESTS_PER_TOKEN = 3

    def get_token(self, user):
        slept = 0
        while slept < 5:
            current_time = datetime.now(timezone.utc).timestamp()
            with self.lock:
                user_state = self._get_user_state(user)
                tokens_dict = user_state["tokens"]

                for token, data in tokens_dict.items():
                    if data['requests_remaining'] > 1:
                        if self._acquire_lock(data):
                            data['requests_remaining'] -= 1
                            return token

                    if data['reset_time']:
                        reset_time = float(data['reset_time'])
                        if current_time >= reset_time:
                            data['requests_remaining'] = 1
                            if self._acquire_lock(data):
                                return token

            time.sleep(0.5)
            logger.debug(f"===sleeping==={slept}")
            slept += 0.5

        raise CannotProcessDiscordRequestError("Unable to process this request at the moment, server is too busy.")

    def update_token(self, user, token: str, headers: dict):
        logger.debug(f"Updating token: {token}")
        reset_time = headers.get('X-RateLimit-Reset')
        requests_remaining = headers.get('X-RateLimit-Remaining')

        with self.lock:
            token_dict = self._get_user_state(user)["tokens"][token]
            self._release_lock(token_dict)
            if requests_remaining and reset_time:
                token_dict['reset_time'] = reset_time
                token_dict['requests_remaining'] = int(requests_remaining)
            else:
                logger.warning("Missing ratelimit headers in response")

    def _acquire_lock(self, token_data):
        for i in range(1, self.MAX_CONCURRENT_REQUESTS_PER_TOKEN + 1):
            if not token_data[f"locked{i}"]:
                token_data[f"locked{i}"] = True
                return True
        return False

    def _release_lock(self, token_data):
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

    def _make_request(self, method: str, url: str, headers: dict = None, params: dict = None, json: dict = None, files: dict = None, timeout: Union[int, None] = 3):
        response = self.client.request(method, url, headers=headers, params=params, json=json, files=files, timeout=timeout)
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
                token = self.get_token(user)
                headers['Authorization'] = f'Bot {token}'

            logger.debug(f"Making bot request with token: {token}")

            response = self._make_request(method, url, headers=headers, params=params, json=json, files=files, timeout=timeout)

            if response.is_success:
                return response

            if response.status_code == 429:
                logger.debug("==============HIT 429!!!!!1=============")
                retry_after = response.json().get("retry_after")
                if not retry_after:  # retry_after is missing if discord blocked us
                    self._handle_discord_block(user, response)

                return self._make_bot_request(user, method, url, headers=headers, params=params, json=json, files=files, timeout=timeout)

            if response.status_code in (403, 401):
                self._handle_bot_having_no_perms(user, token, response)

        finally:
            try:
                self.update_token(user, token, response.headers)
            except:
                self.remove_user_state(user)

    def _handle_bot_having_no_perms(self, user, token, response):
        from ..tasks import queue_ws_event
        with self.lock:
            token_dict = self._get_user_state(user)["tokens"][token]

            bot = Bot.objects.get(owner=user, token=token)
            bot.disabled = True
            bot.reason = "errors.LackOfRequiredPerms"
            bot.save()
            queue_ws_event.delay('user', {'type': 'send_message', 'op_code': EventCode.MESSAGE_SENT.value, 'user_id': user.id,
                                          'message': "toasts.botRemovedForInsufficientPerms",
                                          'args': {"name": token_dict['name']}, 'finished': True, 'error': True})
        self.remove_user_state(user)

        raise DiscordError(response.text, response.status_code)

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

    def get_attachment_url(self, user, resource: Union['Fragment', 'Thumbnail', 'Preview', 'Moment']) -> str:
        return self.get_file_url(user, resource.message_id, resource.attachment_id)

    def get_file_url(self, user, message_id: str, attachment_id: str) -> str:
        message = self.get_message(user, message_id).json()
        for attachment in message["attachments"]:
            if attachment["id"] == attachment_id:
                return attachment["url"]
        raise DiscordError(f"File with {attachment_id} not found")

    def get_message(self, user, message_id: str) -> httpx.Response:
        cached_message = cache.get(message_id)
        if cached_message:
            return cached_message

        channel_id = self._get_channel_id(user)
        url = f'{DISCORD_BASE_URL}/channels/{channel_id}/messages/{message_id}'
        response = self._make_bot_request(user, 'GET', url)

        message = response.json()
        expiry = self._calculate_expiry(message)
        cache.set(message["id"], response, timeout=expiry)
        return response

    def remove_message(self, user, message_id: str) -> httpx.Response:
        channel_id = self._get_channel_id(user)
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
        channel_id = self._get_channel_id(user)
        url = f'{DISCORD_BASE_URL}/channels/{channel_id}/messages/{message_id}'

        attachments_to_keep = []
        for attachment_id in attachment_ids_to_keep:
            attachments_to_keep.append({"id": attachment_id})

        headers = {'Authorization': f'Bot {token}'}
        response = self._make_bot_request(user, 'PATCH', url, json={"attachments": attachments_to_keep}, headers=headers)
        return response

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

    def remove_user_state(self, user):
        logger.debug("Removing user state")
        with self.lock:
            try:
                del self.users_state[user.id]
            except KeyError:
                pass

    def _get_channel_id(self, user):
        user_state = self._get_user_state(user)
        return user_state['channel_id']

    def _get_user_state(self, user):
        user_state = self.users_state.get(user.id)
        if not user_state:
            logger.debug("===obtaining user state===")

            settings, bots = self._get_discord_settings(user)

            if not bots:
                raise BadRequestError("User has no bots")

            token_dict = {
                bot.token: {
                    'requests_remaining': 4,
                    'reset_time': None,
                    **{f'locked{i}': False for i in range(1, self.MAX_CONCURRENT_REQUESTS_PER_TOKEN + 1)},
                    'name': bot.name,
                }
                for bot in bots
            }
            self.users_state[user.id] = {"channel_id": settings.channel_id, "guild_id": settings.guild_id, "tokens": token_dict, "blocked": False}
        return self.users_state.get(user.id)

    def _get_discord_settings(self, user):
        settings = DiscordSettings.objects.get(user=user)
        bots = Bot.objects.filter(owner=user, disabled=False).order_by('created_at')
        return settings, bots

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

    def fetch_messages(self, user):
        channel_id = self._get_channel_id(user)
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
