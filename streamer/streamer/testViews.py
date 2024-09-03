import base64
import requests
from django.http import StreamingHttpResponse
from django.views import View
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

DISCORD_API_URL = "https://discord.com/api/v9"
DISCORD_TOKEN = 'ODk0NTc4MDM5NzI2NDQwNTUy.GAqXhm.8M61gjcKM5d6krNf6oWBOt1ZSVmpO5PwPoGVa4'
CHANNEL_ID = "870781149583130644"
MESSAGE_ID = "1276552338630381712"
KEY = "tF1KV+ipqSmIdfHeS5iVyKqB6M7f3NS2bU1isrzBxjo="
IV = "wzotFW+LKD2iNfpDeR+wKg=="

def stream_decrypt(url, key, iv):
    key = base64.b64decode(key)
    iv = base64.b64decode(iv)

    response = requests.get(url, stream=True)
    response.raise_for_status()
    initial_bytes = response.raw.read(16)

    cipher = Cipher(algorithms.AES(key), modes.CTR(iv), backend=default_backend())
    decryptor = cipher.decryptor()

    for chunk in response.iter_content(chunk_size=4096):
        if chunk:
            decrypted_chunk = decryptor.update(chunk)
            yield decrypted_chunk

    # Finalize decryption
    yield decryptor.finalize()

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

class DecryptFileView(View):
    def get(self, request, *args, **kwargs):
        file_url, filename = get_file_info_from_message(CHANNEL_ID, MESSAGE_ID)

        # Stream the response using StreamingHttpResponse
        response = StreamingHttpResponse(stream_decrypt(file_url, KEY, IV), content_type='application/octet-stream')
        response['Content-Disposition'] = 'attachment; filename="1.mp4"'

        return response
