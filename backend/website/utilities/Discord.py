import time
from datetime import datetime, timezone
from threading import Lock
from typing import Union
from urllib.parse import urlparse, parse_qs

import httpx

from ..models import DiscordSettings, Bot, Webhook
from ..utilities.constants import cache, DISCORD_BASE_URL, EventCode
from ..utilities.errors import DiscordError, DiscordBlockError, CannotProcessDiscordRequestError, BadRequestError


class Discord:
    def __del__(self):
        self.client.close()

    # todo fix this (retry after and switching tokens)
    def __init__(self):
        self.client = httpx.Client(timeout=10.0)

        self.current_token_index = 0

        self.file_upload_headers = {}
        self.users = {}

        self.lock = Lock()

    def get_token(self, user):
        slept = 0

        while slept < 5:  # wait max for 5 seconds, then return service unavailable
            current_time = datetime.now(timezone.utc).timestamp()
            token_dict = self.users[user.id]["tokens"]
            for token, data in token_dict.items():
                with self.lock:
                    if data['requests_remaining'] > 2:  # I have no clue why but when its 0, we still hi 429? probably race conditions or some other shit, cannot care less
                        token_dict[token]['requests_remaining'] -= 1
                        return token

                    if data['reset_time']:

                        reset_time = float(data['reset_time'])

                        if current_time >= reset_time:
                            token_dict[token]['requests_remaining'] = 1
                            return token

            time.sleep(0.5)
            print(f"===sleeping==={slept}")
            slept += 0.5

        raise CannotProcessDiscordRequestError("Unable to process this request at the moment, server is too busy.")

    def update_token(self, user, token: str, headers: dict):
        print(f"update token: {token}")
        reset_time = headers.get('X-RateLimit-Reset')
        requests_remaining = headers.get('X-RateLimit-remaining')
        token_dict = self.users[user.id]["tokens"]

        with self.lock:  # Ensure thread safety when updating token_dict
            if requests_remaining and reset_time:
                token_dict[token]['reset_time'] = reset_time
                token_dict[token]['requests_remaining'] = int(requests_remaining)
            else:
                print("===Missing ratelimit headers====")

    def _make_request(self, method: str, url: str, headers: dict = None, json: dict = None, files: dict = None, timeout: Union[int, None] = 3):
        response = self.client.request(method, url, headers=headers, json=json, files=files, timeout=timeout)
        if not headers:
            headers = {}
        headers['Content-Type'] = 'application/json'

        if response.status_code == 429:
            print("hit 429 !!!!!!!!!!!!!!!")

            retry_after = response.json().get("retry_after")
            if not retry_after:  # retry_after is missing if discord blocked us
                raise DiscordBlockError("Discord is stupid :(")

            return self._make_request(method, url, headers, json, files, timeout)

        return response

    def _make_bot_request(self, user, method: str, url: str, headers: dict = None, json: dict = None, files: dict = None, timeout: Union[int, None] = 3):
        token = self.get_token(user)
        if not headers:
            headers = {}
        headers['Authorization'] = f'Bot {token}'
        print(f"Making bot request with token: {token}")

        response = self._make_request(method, url, headers=headers, json=json, files=files, timeout=timeout)
        self.update_token(user, token, response.headers)

        if not response.is_success:
            if response.status_code == 403:
                from ..tasks import queue_ws_event
                with self.lock:
                    token_dict = self.users[user.id]["tokens"][token]

                    bot = Bot.objects.get(owner=user, token=token)
                    bot.disabled = True
                    bot.reason = "errors.LackOfRequiredPerms"
                    bot.save()

                    queue_ws_event.delay('user', {'type': 'send_message', 'op_code': EventCode.MESSAGE_SENT.value, 'user_id': user.id, 'message': "toasts.botRemovedForInsufficientPerms",
                                                  'args': {"name": token_dict['name']}, 'finished': True, 'error': True})
                    del token_dict

            raise DiscordError(response.text, response.status_code)
        return response

    def _make_webhook_request(self, user, method: str, url: str, headers: dict = None, json: dict = None, files: dict = None, timeout: Union[int, None] = 3):

        print(f"Making webhook request with: {url}")

        response = self._make_request(method, url, headers=headers, json=json, files=files, timeout=timeout)
        # todo implement ratelimit for webhooks

        if not response.is_success:
            if response.status_code == 403:
                from ..tasks import queue_ws_event
                webhook = Webhook.objects.get(owner=user, url=url)
                queue_ws_event.delay('user', {'type': 'send_message', 'op_code': EventCode.MESSAGE_SENT.value, 'user_id': user.id, 'message': "toasts.webhook403",
                                              'args': {"name": webhook.name}, 'finished': True, 'error': True})

            raise DiscordError(response.text, response.status_code)

    def send_message(self, user, message: str) -> httpx.Response:
        channel_id = self._get_channel_id(user)
        url = f'{DISCORD_BASE_URL}/channels/{channel_id}/messages'
        payload = {'content': message}
        headers = {"Content-Type": 'application/json'}

        response = self._make_bot_request(user, 'POST', url, headers=headers, json=payload)
        return response

    def send_file(self, user, files: dict) -> httpx.Response:
        channel_id = self._get_channel_id(user)

        url = f'{DISCORD_BASE_URL}/channels/{channel_id}/messages'

        response = self._make_bot_request(user, 'POST', url, files=files, timeout=None)

        message = response.json()
        expiry = self._calculate_expiry(message)
        cache.set(message["id"], response, timeout=expiry)

        return response

    def get_file_url(self, user, message_id: str, attachment_id: str) -> str:
        message = self.get_message(user, message_id).json()
        for attachment in message["attachments"]:
            if attachment["id"] == attachment_id:
                return attachment["url"]
        raise DiscordError(f"File with {attachment_id} not found")

    def get_message(self, user, message_id: str) -> httpx.Response:
        cached_message = cache.get(message_id)
        if cached_message:
            print("using cached message")
            return cached_message
        print("hit discord api")

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

    def edit_attachments(self, user, webhook, message_id, attachment_ids_to_keep) -> httpx.Response:
        # todo
        attachments_to_keep = []
        for attachment_id in attachment_ids_to_keep:
            attachments_to_keep.append({"id": attachment_id})
        url = f"{webhook}/messages/{message_id}"
        response = self._make_webhook_request(user, 'PATCH', url, json={"attachments": attachments_to_keep})
        return response

    def _calculate_expiry(self, message: dict) -> float:
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

    def remove_user_state(self, user):
        print("===removing user state===")
        with self.lock:
            try:
                del self.users[user.id]
            except KeyError:
                pass

    def _get_channel_id(self, user):
        user_state = self.users.get(user.id)
        if not user_state:
            print("===obtaining user state===")
            settings, bots = self._get_discord_settings(user)

            if not bots:
                raise BadRequestError("User has no bots")

            token_dict = {
                bot.token: {
                    'requests_remaining': 4,  # Default discord remaining
                    'reset_time': None,
                    'name': bot.name,
                }
                for bot in bots
            }
            self.users[user.id] = {"channel_id": settings.channel_id, "guild_id": settings.guild_id, "tokens": token_dict}

            return settings.channel_id

        return user_state['channel_id']

    def _get_discord_settings(self, user):
        settings = DiscordSettings.objects.get(user=user)
        bots = Bot.objects.filter(owner=user, disabled=False).order_by('created_at')
        return settings, bots

    def get_webhook(self, webhook_url):
        # todo this call uses bots token auth
        response = self._make_request('GET', webhook_url)
        return response.json()


discord = Discord()
