import asyncio
import base64
import re
import time
from urllib.parse import quote

import aiohttp
import requests
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from django.http import StreamingHttpResponse, HttpResponse
from django.utils.encoding import smart_str
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.throttling import UserRateThrottle

from ..models import File
from ..utilities.Discord import discord
from ..utilities.decorators import handle_common_errors, check_file, check_signed_url
from ..utilities.throttle import MediaRateThrottle, MyUserRateThrottle


@api_view(['GET'])
@throttle_classes([MediaRateThrottle])
# @handle_common_errors
def get_file_url_view(request):
    async def iterable_content():
        for _ in range(1000):
            await asyncio.sleep(0.1)
            print('Returning chunk')
            yield b'a'

    return StreamingHttpResponse(iterable_content())


# todo  handle >416 Requested Range Not Satisfiable<
@api_view(['GET'])
@throttle_classes([MyUserRateThrottle])
@handle_common_errors
@check_signed_url
@check_file
def stream_file(request, file_obj: File):
    isInline = request.GET.get('inline', False)


    fragments = file_obj.fragments.all()
    print(f"========={file_obj.name}=========")

    filename_ascii = quote(smart_str(file_obj.name))
    # Encode the filename using RFC 5987
    encoded_filename = quote(file_obj.name)

    content_disposition = f'{"inline" if isInline else "attachment"}; filename="{filename_ascii}"; filename*=UTF-8\'\'{encoded_filename}'
    # If file is empty, return no content but still allow it to be downloaded
    if len(fragments) == 0:
        response = HttpResponse()
        if not isInline:
            response['Content-Disposition'] = content_disposition
        return response

    async def file_iterator(index, start_byte, end_byte, real_start_byte, chunk_size=8192):
        print("index")
        print(index)

        # file["is_encrypted"] = False
        if file_obj.is_encrypted:
            # luckily or not - we store both key and iv in the database
            key = base64.b64decode(file_obj.get_base64_key())
            iv = base64.b64decode(file_obj.get_base64_iv())

            cipher = Cipher(algorithms.AES(key), modes.CTR(iv), backend=default_backend())
            decryptor = cipher.decryptor()

            initial_bytes_to_simulate = real_start_byte
            simulated_bytes = bytearray(initial_bytes_to_simulate)
            start_time = time.perf_counter()

            decryptor.update(simulated_bytes)
            end_time = time.perf_counter()
            print(f"Time taken for fake decryption (seconds): {end_time - start_time:.6f}")

        while index < len(fragments):
            url = discord.get_file_url(fragments[index].message_id, fragments[index].attachment_id)

            headers = {
                'Range': 'bytes={}-{}'.format(start_byte, end_byte) if end_byte else 'bytes={}-'.format(start_byte)}

            # Async HTTP request using aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        # Asynchronously iterate over the content in chunks
                        async for raw_data in response.content.iter_chunked(chunk_size):
                            # If the file is encrypted, decrypt it asynchronously
                            if file_obj.is_encrypted:
                                decrypted_data = decryptor.update(raw_data)
                                yield decrypted_data
                            else:
                                # Yield raw data if not encrypted
                                yield raw_data

            index += 1
        if file_obj.is_encrypted:
            yield decryptor.finalize()

    # parse range header to get start byte and end byte
    range_header = request.headers.get('Range')
    if range_header:
        range_match = re.match(r'bytes=(\d+)-(\d+)?', range_header)
        if range_match:
            start_byte = int(range_match.group(1))
            end_byte = int(range_match.group(2)) if range_match.group(2) else None
        else:
            return HttpResponse(status=400)

    else:
        start_byte = 0
        end_byte = None

    # Find the appropriate file fragment based on byte range request
    real_start_byte = start_byte
    selected_fragment_index = 0
    for fragment in fragments:
        if start_byte < fragment.size:
            selected_fragment_index = int(fragment.sequence) - 1
            break
        else:
            start_byte -= fragment.size
    # if range header was given then to allow seeking in the browser we need to return 206 - partial response.
    # Otherwise, the response was probably called by download browser function, and we need to return 200
    if range_header:
        status = 206
    else:
        status = 200

    response = StreamingHttpResponse(file_iterator(selected_fragment_index, start_byte, end_byte, real_start_byte), content_type=file_obj.mimetype, status=status)

    file_size = file_obj.size
    real_end_byte = 0
    for i in range(selected_fragment_index):
        real_end_byte += fragments[i].size
    referer = request.headers.get('Referer')

    # Set the X-Frame-Options header to the request's origin
    if referer:
        response['X-Frame-Options'] = f'ALLOW-FROM {referer}'
    else:
        response['X-Frame-Options'] = 'DENY'

    response['Content-Length'] = file_size
    response['Content-Disposition'] = content_disposition

    if file_obj.type == "text":
        response['Cache-Control'] = "no-cache"
    else:
        response['Cache-Control'] = f"max-age={2628000}"  # 1 month

    if range_header:
        response['Content-Range'] = 'bytes %s-%s/%s' % (real_start_byte, real_end_byte - 1, file_size)  # this -1 is vevy important
        response['Accept-Ranges'] = 'bytes'

        response['Content-Length'] = real_end_byte - real_start_byte

    return response