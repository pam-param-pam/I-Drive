import io

import requests
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from django.http import HttpResponse
from rest_framework.decorators import api_view, throttle_classes

from ..utilities.Decryptor import Decryptor
from ..utilities.Discord import discord
from ..utilities.errors import DiscordError
from ..utilities.other import get_file
from ..utilities.throttle import MediaRateThrottle


# @api_view(['GET'])
# @throttle_classes([MediaRateThrottle])
# # @handle_common_errors
# def get_folder_password(request, file_id):
#     file_obj = get_file(file_id)
#     print(file_obj)
#     fragments = file_obj.fragments.all().order_by('sequence')
#
#     urls = []
#
#     for fragment in fragments:
#         url = discord.get_file_url(request.user, fragment.message_id, fragment.attachment_id)
#         # Create an HTML anchor tag for the URL
#         urls.append(f'<a href="{url}" target="_blank">{url}</a><br>')
#
#     # Join all the links and return as an HTML response
#     html_content = ''.join(urls)
#     return HttpResponse(html_content, content_type="text/html")

@api_view(['GET'])
@throttle_classes([MediaRateThrottle])
# @handle_common_errors
def get_folder_password(request, file_id):
    file_obj = get_file(file_id)
    print(file_obj)
    fragments = file_obj.fragments.all().order_by('sequence')

    blocks_to_skip = 0 // 16
    counter_int = int.from_bytes(file_obj.iv, byteorder='big')
    counter_int += blocks_to_skip

    new_iv = counter_int.to_bytes(len(file_obj.iv), byteorder='big')

    cipher = Cipher(algorithms.AES(file_obj.key), modes.CTR(new_iv), backend=default_backend())

    decryptor = cipher.decryptor()
    file_content = b''
    for fragment in fragments:
        url = discord.get_file_url(file_obj.owner, fragment.message_id, fragment.attachment_id)
        response = requests.get(url, timeout=20)
        if not response.ok:
            raise DiscordError(response.text, response.status_code)

        content_length = response.headers['content-length']

        decrypted_data = decryptor.update(response.content)
        file_content += decrypted_data
        print(content_length)
        if len(decrypted_data) != int(content_length) or int(content_length) != len(response.content):
            print(len(decrypted_data))
            print(content_length)
            print(len(response.content))
            print("UGA BUGA")

    file_content += decryptor.finalize()
    file_like_object = io.BytesIO(file_content)

    response = HttpResponse(file_like_object, content_type='video/mp4')
    response['Content-Disposition'] = 'inline; filename="video.mp4"'

    return response
