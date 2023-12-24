import time
import httpx


def retry(func):
    def decorator(*args, **kwargs):
        response = func(*args, **kwargs)
        if response.status_code == 429:
            retry_after = response.json()["retry_after"]
            time.sleep(retry_after)

            # Retry with the new token
            args[0].switch_token()
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
                           "MTE4Njc0ODE4ODA1NzY4MjA2MA.GEMHFW.eg9hT5IJKzSMpJ0nbFv4D_MqLCw72qlFR9VTTU"]

        self.BASE_URL = 'https://discord.com/api/v10'
        self.channel_id = '870781149583130644'
        self.current_token_index = 0

        self.headers = {'Authorization': f'Bot {self.current_token}'}

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
        return response

    @retry
    def send_file(self, files) -> httpx.Response:
        url = f'{self.BASE_URL}/channels/{self.channel_id}/messages'
        response = self.client.post(url, headers=self.headers, files=files, timeout=None)
        return response

    def get_file_url(self, message_id) -> str:
        return self.get_message(message_id).json()["attachments"][0]["url"]

    @retry
    def get_message(self, message_id) -> httpx.Response:
        url = f'{self.BASE_URL}/channels/{self.channel_id}/messages/{message_id}'
        response = self.client.get(url, headers=self.headers)

        return response

    @retry
    def remove_message(self, message_id) -> httpx.Response:
        url = f'{self.BASE_URL}/channels/{self.channel_id}/messages/{message_id}'
        response = self.client.delete(url, headers=self.headers)
        return response


discord = Discord()
