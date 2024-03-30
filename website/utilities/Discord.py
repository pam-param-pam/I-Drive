import json
import time
from json import JSONDecodeError

import httpx


class DiscordError(Exception):
    def __init__(self, message="Unexpected Discord Error.", status=0):
        self.status = status
        try:
            json_message = json.loads(message)

            self.message = json_message.get("message")
        except (JSONDecodeError, KeyError):
            print(message)
            self.message = "Unknown"

        super().__init__(self.message)

    def __str__(self):
        return f'Discord error-> {self.status}: {self.message}'


def retry(func):
    def decorator(*args, **kwargs):
        response = func(*args, **kwargs)
        if response.status_code == 429:  # with 4 tokens this almost never happens so no need for fancy rate limit calculations to avoid 429
            retry_after = response.json()["retry_after"]
            print("hit 429!!!!!!!!!!!!!!!")
            args[0].switch_token()

            return decorator(*args, **kwargs)

        if response.headers["x-ratelimit-remaining"] == "0":
            args[0].switch_token()

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

        self.BASE_URL = 'https://discord.com/api/v10'
        self.channel_id = '870781149583130644'
        self.current_token_index = 0

        self.headers = {'Authorization': f'Bot {self.current_token}', "Content-Type": 'application/json'}

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
        payload = {'content': message}  # Construct the payload according to Discord API requirements

        response = self.client.post(url, headers=self.headers, json=payload)
        if response.is_success or response.status_code == 429:
            return response
        raise DiscordError(response.text, response.status_code)
    @retry
    def send_file(self, files) -> httpx.Response:
        url = f'{self.BASE_URL}/channels/{self.channel_id}/messages'
        response = self.client.post(url, headers=self.headers, files=files, timeout=None)
        if response.is_success or response.status_code == 429:
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
        url = f'{self.BASE_URL}/channels/{self.channel_id}/messages/{message_id}'
        response = self.client.get(url, headers=self.headers)
        if response.is_success or response.status_code == 429:
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
    def edit_attachments(self, webhook, message_id, attachments_to_keep) -> httpx.Response:
        url = f"{webhook}/messages/{message_id}"
        response = self.client.patch(url, json={"attachments": [{"id": attachments_to_keep}]}, headers=self.headers)
        print(response.text)
        if response.is_success or response.status_code == 429:
            return response
        raise DiscordError(response.text, response.status_code)


discord = Discord()
