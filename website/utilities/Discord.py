import time

import asyncio
from datetime import datetime
from urllib.parse import urlparse, parse_qs

import httpx

from website.utilities.constants import cache
from website.utilities.errors import DiscordError, DiscordBlockError


def retry(func):
    def decorator(*args, **kwargs):
        # args[0].semaphore.acquire()

        response = func(*args, **kwargs)
        print(response.headers["X-ratelimit-remaining"])
        if response.status_code == 429:
            print("hit 429!!!!!!!!!!!!!!!")
            try:
                retry_after = response.json()["retry_after"]
                time.sleep(retry_after)
                args[0].switch_token()

            except KeyError:
                raise DiscordBlockError("Discord is stupid :(")
            return decorator(*args, **kwargs)

        if response.headers["X-ratelimit-remaining"] == "1":
            retry_after = float(response.headers["X-RateLimit-Reset-After"])
            time.sleep(retry_after)
            args[0].switch_token()
        # args[0].semaphore.release()

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

    def __init__(self):
        self.client = httpx.Client(timeout=10.0)
        self.bot_tokens = ["ODk0NTc4MDM5NzI2NDQwNTUy.GAqXhm.8M61gjcKM5d6krNf6oWBOt1ZSVmpO5PwPoGVa4",
                           "MTE4NjczNTE5NTg3ODA2ODI4Ng.GeXLwx.KbonHuxNcUfnl0U-rqix7t9CzUoa4MLZgvbX3E",
                           "MTE4Njc0ODE4ODA1NzY4MjA2MA.GEMHFW.eg9hT5IJKzSMpJ0nbFv4D_MqLCw72qlFR9VTTU",
                           "MTE4ODk1MTQyODYxNDU4NjQ4OA.G4CVRG.dMvoxd0Z7nQF5reiLIoFQNkstfalQmcTaGcXOY",
                           "MTIwMDExODYzNTkyMjk4OTE2Nw.GUkoOq.n6e-5qYwwiRacyKqZIsNClM5gD8G0x7e23rtxM",
                           "MTIwMDExODkyMTQ0MTg0NTI5MA.Gq4BiA.7ChveurWbuTHPBqYpFOch-P6BvPfAX5A9yVRsI",
                           ]
        # self.semaphore = asyncio.Semaphore(len(self.bot_tokens))
        self.semaphore = asyncio.Semaphore(1)

        self.BASE_URL = 'https://discord.com/api/v10'
        self.channel_id = '870781149583130644'
        self.current_token_index = 0

        self.headers = {'Authorization': f'Bot {self.current_token}', "Content-Type": 'application/json'}
        self.file_upload_headers = {'Authorization': f'Bot {self.current_token}'}

    @property
    def current_token(self):
        return self.bot_tokens[self.current_token_index]

    def switch_token(self):
        print("switching tokens!")
        self.current_token_index = (self.current_token_index + 1) % len(self.bot_tokens)
        self.headers = {'Authorization': f'Bot {self.current_token}'}

    @retry
    def send_message(self, message) -> httpx.Response:
        url = f'{self.BASE_URL}/channels/{self.channel_id}/messages'
        payload = {'content': message}

        response = self.client.post(url, headers=self.headers, json=payload)
        if response.is_success or response.status_code == 429:
            return response
        raise DiscordError(response.text, response.status_code)

    @retry
    def send_file(self, files) -> httpx.Response:
        url = f'{self.BASE_URL}/channels/{self.channel_id}/messages'
        response = self.client.post(url, headers=self.file_upload_headers, files=files, timeout=None)
        if response.is_success:
            message = response.json()
            expiry = self._calculate_expiry(message)
            cache.set(message["id"], response, timeout=expiry)
            return response

        if response.status_code == 429:
            return response
        raise DiscordError(response.text, response.status_code)

    def get_file_url(self, message_id, attachment_id) -> str:
        message = self.get_message(message_id).json()
        for attachment in message["attachments"]:
            if attachment["id"] == attachment_id:
                return attachment["url"]
        raise KeyError(f"File with {attachment_id} not found")

    @retry
    def get_message(self, message_id) -> httpx.Response:
        cached_message = cache.get(message_id)
        if cached_message:
            print("using cached message")
            return cached_message
        print("hit discord api")
        url = f'{self.BASE_URL}/channels/{self.channel_id}/messages/{message_id}'
        response = self.client.get(url, headers=self.headers)
        if response.is_success:
            message = response.json()
            expiry = self._calculate_expiry(message)
            cache.set(message["id"], response, timeout=expiry)
            return response

        if response.status_code == 429:
            return response

        raise DiscordError(response.text, response.status_code)

    @retry
    def remove_message(self, message_id) -> httpx.Response:

        url = f'{self.BASE_URL}/channels/{self.channel_id}/messages/{message_id}'
        response = self.client.delete(url, headers=self.headers)
        if response.is_success or response.status_code == 429:
            return response
        raise DiscordError(response.text, response.status_code)

    @retry
    def edit_attachments(self, webhook, message_id, attachment_ids_to_keep) -> httpx.Response:
        attachments_to_keep = []
        for attachment_id in attachment_ids_to_keep:
            attachments_to_keep.append({"id": attachment_id})
        url = f"{webhook}/messages/{message_id}"
        response = self.client.patch(url, json={"attachments": attachments_to_keep}, headers=self.headers)
        if response.is_success or response.status_code == 429:
            return response
        raise DiscordError(response.text, response.status_code)

    def _calculate_expiry(self, message):
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
