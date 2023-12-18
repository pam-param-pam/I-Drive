import time
import httpx

def retry():
    def decorator(func):
        def newfn(*args, **kwargs):
            response = func(*args, **kwargs)
            if response.status_code == 429:
                retry_after = response.json()["retry_after"]
                time.sleep(retry_after)
                return func(*args, **kwargs)
            return response
        return newfn

    return decorator

class Discord:
    def __del__(self):
        self.client.close()

    def __init__(self):
        self.client = httpx.Client(timeout=10.0)

        self.BOT_TOKEN = "ODk0NTc4MDM5NzI2NDQwNTUy.GAqXhm.8M61gjcKM5d6krNf6oWBOt1ZSVmpO5PwPoGVa4"
        self.BASE_URL = 'https://discord.com/api/v10'
        self.channel_id = '870781149583130644'
        self.headers = {'Authorization': f'Bot {self.BOT_TOKEN}'}

    @retry()
    def send_message(self, message) -> httpx.Response:
        url = f'{self.BASE_URL}/channels/{self.channel_id}/messages'
        payload = {'content': message}  # Construct the payload according to Discord API requirements

        response = self.client.post(url, headers=self.headers, json=payload)
        return response

    @retry()
    def send_file(self, files) -> httpx.Response:
        url = f'{self.BASE_URL}/channels/{self.channel_id}/messages'
        response = self.client.post(url, headers=self.headers, files=files, timeout=None)
        return response

    def get_file_url(self, message_id) -> str:
        return self.get_message(message_id).json()["attachments"][0]["url"]

    @retry()
    def get_message(self, message_id) -> httpx.Response:
        url = f'{self.BASE_URL}/channels/{self.channel_id}/messages/{message_id}'
        response = self.client.get(url, headers=self.headers)

        return response

    @retry()
    def delete_file(self, message_id) -> httpx.Response:
        url = f'{self.BASE_URL}/channels/{self.channel_id}/messages/{message_id}'
        response = self.client.delete(url, headers=self.headers)
        return response


discord = Discord()


