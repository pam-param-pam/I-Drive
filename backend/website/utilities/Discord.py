import logging
import os
import time

from datetime import datetime, timezone
from typing import Union
from urllib.parse import urlparse, parse_qs

import httpx

from ..utilities.constants import cache
from ..utilities.errors import DiscordError, DiscordBlockError, CannotProcessDiscordRequestError


def retry(func):
    def decorator(*args, **kwargs):
        # args[0].semaphore.acquire()

        response = func(*args, **kwargs)

        #
        # if response.status_code == 429:
        #     print("hit 429!!!!!!!!!!!!!!!")
        #     try:
        #         retry_after = response.json()["retry_after"]
        #         time.sleep(retry_after)
        #         args[0].switch_token()
        #
        #     # discord returns an error json that doesn't contain retry_after if it blocked us for longer period of time. Should make it cleaner
        #     except KeyError as e:
        #         raise DiscordBlockError("Discord is stupid :(") from e
        #     return decorator(*args, **kwargs)
        #
        # if response.headers["X-ratelimit-remaining"] == "1":
        #     retry_after = float(response.headers["X-RateLimit-Reset-After"])
        #     #time.sleep(retry_after)
        #     args[0].switch_token()
        # # args[0].semaphore.release()

        return response

    return decorator


def webhook_retry(func):
    def decorator(*args, **kwargs):
        response = func(*args, **kwargs)
        if response.status_code == 429:
            retry_after = response.json()["retry_after"]
            time.sleep(retry_after)
            return decorator(*args, **kwargs)

        if response.headers["X-ratelimit-remaining"] == "0":
            retry_after = response.json()["X-RateLimit-Reset"]
            time.sleep(retry_after)
            return decorator(*args, **kwargs)

        return response

    return decorator


class Discord:
    def __del__(self):
        self.client.close()

    # todo fix this (retry after and switching tokens)
    def __init__(self):
        self.client = httpx.Client(timeout=10.0)
        self.bot_tokens = [
            os.environ['DISCORD_TOKEN1'],
            os.environ['DISCORD_TOKEN2'],
            os.environ['DISCORD_TOKEN3'],
            os.environ['DISCORD_TOKEN4'],
            os.environ['DISCORD_TOKEN5'],
            os.environ['DISCORD_TOKEN6'],
            os.environ['DISCORD_TOKEN7'],
            os.environ['DISCORD_TOKEN8'],
            os.environ['DISCORD_TOKEN9'],
            os.environ['DISCORD_TOKEN10']

        ]

        self.token_dict = {
            token: {
                'requests_remaining': 5,  # Default discord remaining
                'reset_time': None,
                'locked': False,
            }
            for token in self.bot_tokens
        }
        self.BASE_URL = 'https://discord.com/api/v10'
        self.channel_id = '870781149583130644'
        self.current_token_index = 0

        self.headers = {"Content-Type": 'application/json'}
        self.file_upload_headers = {}

    def get_token(self):
        slept = 0

        while slept < 5:  # wait max for 5 seconds, then return service unavailable
            current_time = datetime.now(timezone.utc).timestamp()

            for token, data in self.token_dict.items():

                if data['requests_remaining'] > 3:  # I have no clue why but when its 0, we still hi 429? probably race conditions or some other shit, cannot care less
                    # self.token_dict[token]['locked'] = True
                    self.token_dict[token]['requests_remaining'] -= 1
                    return token

                if data['reset_time']:

                    reset_time = float(data['reset_time'])

                    # print(reset_time)
                    # print(current_time)
                    if current_time >= reset_time:
                        # # self.token_dict[token]['locked'] = True
                        # print("TOKEN {}")
                        # # self.token_dict[token]['requests_remaining'] = 4

                        return token

            time.sleep(1)
            print(f"===sleeping==={slept}")
            slept += 1

        raise CannotProcessDiscordRequestError("Unable to process this request at the moment")

    def update_token(self, token: str, headers: dict):
        print(f"update token: {token}")

        reset_time = headers.get('X-RateLimit-Reset')
        requests_remaining = headers.get('X-RateLimit-remaining')
        if requests_remaining and reset_time:
            self.token_dict[token]['reset_time'] = reset_time
            self.token_dict[token]['requests_remaining'] = int(requests_remaining)
        else:
            print("===Missing ratelimit headers====")

    def make_request(self, method: str, url: str, headers: dict = None, json: dict = None, files: dict = None, timeout: Union[int, None] = 3):
        token = self.get_token()
        if not headers:
            headers = {}
        headers['Authorization'] = f'Bot {token}'
        print(f"Making request with token: {token}")
        response = self.client.request(method, url, headers=headers, json=json, files=files, timeout=timeout)

        self.update_token(token, response.headers)

        if response.status_code == 429:
            print("hit 429!!!!!!!!!!!!!!!")

            retry_after = response.json().get("retry_after")
            if not retry_after:  # retry_after is missing if discord blocked us
                raise DiscordBlockError("Discord is stupid :(")

            return self.make_request(method, url, headers, json, files, timeout)
        elif not response.is_success:
            raise DiscordError(response.text, response.status_code)

        return response

    def send_message(self, message: str) -> httpx.Response:
        url = f'{self.BASE_URL}/channels/{self.channel_id}/messages'
        payload = {'content': message}
        headers = {"Content-Type": 'application/json'}

        response = self.make_request('POST', url, headers=headers, json=payload)
        return response

    def send_file(self, files: dict) -> httpx.Response:
        url = f'{self.BASE_URL}/channels/{self.channel_id}/messages'

        response = self.make_request('POST', url, files=files, timeout=None)

        message = response.json()
        expiry = self._calculate_expiry(message)
        cache.set(message["id"], response, timeout=expiry)

        return response

    def get_file_url(self, message_id: str, attachment_id: str) -> str:
        message = self.get_message(message_id).json()
        for attachment in message["attachments"]:
            if attachment["id"] == attachment_id:
                return attachment["url"]
        raise DiscordError(f"File with {attachment_id} not found")

    def get_message(self, message_id: str) -> httpx.Response:
        cached_message = cache.get(message_id)
        if cached_message:
            print("using cached message")
            return cached_message
        print("hit discord api")

        url = f'{self.BASE_URL}/channels/{self.channel_id}/messages/{message_id}'

        response = self.make_request('GET', url)

        message = response.json()
        expiry = self._calculate_expiry(message)
        cache.set(message["id"], response, timeout=expiry)
        return response

    @retry
    def remove_message(self, message_id: str) -> httpx.Response:
        url = f'{self.BASE_URL}/channels/{self.channel_id}/messages/{message_id}'
        response = self.make_request('DELETE', url)
        return response

    @retry
    def edit_attachments(self, webhook, message_id, attachment_ids_to_keep) -> httpx.Response:
        # todo
        attachments_to_keep = []
        for attachment_id in attachment_ids_to_keep:
            attachments_to_keep.append({"id": attachment_id})
        url = f"{webhook}/messages/{message_id}"
        response = self.client.patch(url, json={"attachments": attachments_to_keep}, headers=self.headers)
        if response.is_success or response.status_code == 429:
            return response
        raise DiscordError(response.text, response.status_code)

    def _calculate_expiry(self, message: dict):
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


discord = Discord()
