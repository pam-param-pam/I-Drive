# views.py
import base64
import aiohttp
import requests
from django.http import HttpResponse
from django.views import View
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

DISCORD_API_URL = "https://discord.com/api/v9"
DISCORD_TOKEN = 'ODk0NTc4MDM5NzI2NDQwNTUy.GAqXhm.8M61gjcKM5d6krNf6oWBOt1ZSVmpO5PwPoGVa4'
CHANNEL_ID = "870781149583130644"
MESSAGE_ID = "1276526448563458143"
KEY = "nBJsBFfUzlIw/2ip6zU2hcigIyorhp4cLrL7h7SYhN0="


async def fetch_and_decrypt(url, key):
    key = base64.b64decode(key)

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            response.raise_for_status()
            content = await response.read()

            # Extract IV from the content
            iv = content[:16]
            encrypted_data = content[16:]

            cipher = Cipher(algorithms.AES(key), modes.CTR(iv), backend=default_backend())
            decryptor = cipher.decryptor()
            decrypted_data = decryptor.update(encrypted_data) + decryptor.finalize()

            return decrypted_data


def get_file_info_from_message(channel_id, message_id):
    url = f'https://discord.com/api/v9/channels/{channel_id}/messages/{message_id}'
    headers = {
        'Authorization': f'Bot {DISCORD_TOKEN}',
        'Content-Type': 'application/json',
    }

    response = requests.get(url, headers=headers)
    response.raise_for_status()
    message_data = response.json()

    for attachment in message_data['attachments']:
        file_url = attachment['url']
        filename = attachment['filename']
        return file_url, filename

    raise ValueError('No attachment found in the specified message')


class DecryptFileView2(View):
    async def get(self, request, *args, **kwargs):
        file_url, filename = get_file_info_from_message(CHANNEL_ID, MESSAGE_ID)
        decrypted_data = await fetch_and_decrypt(file_url, KEY)

        response = HttpResponse(decrypted_data, content_type='application/octet-stream')
        response['Content-Disposition'] = 'attachment; filename="a.txt"'
        return response
    
## this is the working version btw
