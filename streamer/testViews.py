# views.py

import requests
from django.http import StreamingHttpResponse
from django.views import View
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

DISCORD_API_URL = "https://discord.com/api/v9"
DISCORD_TOKEN = 'ODk0NTc4MDM5NzI2NDQwNTUy.GAqXhm.8M61gjcKM5d6krNf6oWBOt1ZSVmpO5PwPoGVa4'
CHANNEL_ID = "870781149583130644"
MESSAGE_ID = "1264911884369399829"
KEY = "azPde+aqukew8A47WS76bApTmZLECN/2ximV5pDsbNo="


def sync_fetch_and_decrypt(url, key):
    response = requests.get(url, stream=True)
    response.raise_for_status()

    # Read the IV (16 bytes) from the start of the response
    iv = response.raw.read(16)

    # Initialize AES-GCM cipher
    cipher = Cipher(algorithms.AES(key), modes.GCM(iv), backend=default_backend())
    decryptor = cipher.decryptor()

    buffer_size = 2024

    while True:
        chunk = response.raw.read(buffer_size)
        if not chunk:
            break
        # Decrypt the chunk
        decrypted_chunk = decryptor.update(chunk)
        yield decrypted_chunk

    # Finalize decryption
    try:
        yield decryptor.finalize()
    except ValueError:
        # Handle cases where finalization might not be possible
        pass


class DecryptFileView(View):
    def get(self, request, *args, **kwargs):
        file_url, filename = get_file_info_from_message(CHANNEL_ID, MESSAGE_ID)

        def sync_gen():
            for item in sync_fetch_and_decrypt(file_url, KEY):
                yield item

        response = StreamingHttpResponse(sync_gen(), content_type='application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


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


def audio_stream(request):
    def generate_audio():
        ws = create_connection("wss://api.pamparampam.dev/ws/audio/")

        wav_file = io.BytesIO()
        wav_writer = wave.open(wav_file, "wb")
        try:
            wav_writer.setframerate(44100)
            wav_writer.setsampwidth(2)  # Assuming 16-bit PCM
            wav_writer.setnchannels(1)

            while True:
                message = ws.recv()
                wav_writer.writeframes(message)
                wav_data = wav_file.getvalue()
                yield wav_data

                # Reset the BytesIO object for next iteration
                wav_file.seek(0)
                wav_file.truncate()

        finally:
            wav_writer.close()

    a = 0
    for chunk in generate_audio():
        with open("audio.wav", "wb") as wav_writer:
            wav_writer.write(chunk)
            a += 1
            if a > 1000:
                print("breaking")
                break
    response = StreamingHttpResponse(generate_audio(), content_type="audio/wav")
    return response