import base64
import os
import re
import time
from urllib.parse import quote

import requests
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from django.core.cache import caches
from django.http import StreamingHttpResponse, HttpResponse, JsonResponse
from django.utils.encoding import smart_str
from django.views.decorators.cache import cache_page
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.throttling import UserRateThrottle

from .zipFly import ZipFly

iDriveBackend = os.environ['BACKEND_BASE_URL']
cache = caches["default"]

@api_view(['GET'])
@throttle_classes([UserRateThrottle])
def index(request):
    return HttpResponse(status=404)

@api_view(['GET'])
@throttle_classes([UserRateThrottle])
def thumbnail_file(request, signed_file_id):
    thumbnail = cache.get(signed_file_id) # we have to manually cache this cuz html video poster is retarded and sends no-cache header (cringe)
    if not thumbnail:
        res = requests.get(f"{iDriveBackend}/file/thumbnail/{signed_file_id}")
        if not res.ok:
            return JsonResponse(status=res.status_code, data=res.json())
        res_json = res.json()


        if res_json["is_encrypted"]:
            # luckily or not - we store both key and iv in the database
            key = base64.b64decode(res_json['key'])
            iv = base64.b64decode(res_json['iv'])

            cipher = Cipher(algorithms.AES(key), modes.CTR(iv), backend=default_backend())
            decryptor = cipher.decryptor()
        #todo potential security risk, without stream its possible to overload the server
        discord_response = requests.get(res_json["url"])
        if discord_response.ok:
            thumbnail = discord_response.content
            if res_json["is_encrypted"]:
                thumbnail = decryptor.update(thumbnail)
                decryptor.finalize()

        else:
                print("============DISCORD ERROR============")
                print(discord_response.status_code)
                print(discord_response.text)
                return JsonResponse(status=res.status_code, data=res.json())

    cache.set(signed_file_id, thumbnail, timeout=2628000)  # 1 month

    response = HttpResponse(thumbnail, content_type="image/jpeg")
    response['Cache-Control'] = f"max-age={2628000}"  # 1 month
    return response


# todo  handle >416 Requested Range Not Satisfiable<
@api_view(['GET'])
@throttle_classes([UserRateThrottle])
def stream_file(request, signed_file_id):
    isInline = request.GET.get('inline', False)
    res = requests.get(f"{iDriveBackend}/fragments/{signed_file_id}")
    if not res.ok:
        return JsonResponse(status=res.status_code, data=res.json())
    res = res.json()
    file = res["file"]
    fragments = res["fragments"]
    print(f"========={file['name']}=========")

    filename_ascii = quote(smart_str(file["name"]))
    # Encode the filename using RFC 5987
    encoded_filename = quote(file["name"])

    content_disposition = f'{"inline" if isInline else "attachment"}; filename="{filename_ascii}"; filename*=UTF-8\'\'{encoded_filename}'
    # If file is empty, return no content but still allow it to be downloaded
    if len(fragments) == 0:
        response = HttpResponse()
        if not isInline:
            response['Content-Disposition'] = content_disposition
        return response

    def file_iterator(index, start_byte, end_byte, real_start_byte, chunk_size=8192):
        # file["is_encrypted"] = False
        if file["is_encrypted"]:
            # luckily or not - we store both key and iv in the database
            key = base64.b64decode(file['key'])
            iv = base64.b64decode(file['iv'])

            cipher = Cipher(algorithms.AES(key), modes.CTR(iv), backend=default_backend())
            decryptor = cipher.decryptor()
            
            initial_bytes_to_simulate = real_start_byte
            simulated_bytes = bytearray(initial_bytes_to_simulate)
            start_time = time.perf_counter()

            decryptor.update(simulated_bytes)
            end_time = time.perf_counter()
            print(f"Time taken for fake decryption (seconds): {end_time - start_time:.6f}")

        while index <= len(fragments):
            fragment_response = requests.get(f"{iDriveBackend}/fragments/{signed_file_id}/{index}")
            if not fragment_response.ok:
                return HttpResponse(status=fragment_response.status_code)

            url = fragment_response.json()["url"]
            headers = {
                'Range': 'bytes={}-{}'.format(start_byte, end_byte) if end_byte else 'bytes={}-'.format(start_byte)}

            discord_response = requests.get(url, headers=headers, stream=True)
            if discord_response.ok:
                for raw_data in discord_response.iter_content(chunk_size):
                    if file["is_encrypted"]:
                        decrypted_data = decryptor.update(raw_data)
                        yield decrypted_data
                    else:
                        yield raw_data
            else:
                print("============DISCORD ERROR============")
                print(discord_response.status_code)
                print(discord_response.text)
                return
            index += 1
        if file["is_encrypted"]:
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
    selected_fragment_index = 1
    for fragment in fragments:
        if start_byte < fragment["size"]:
            selected_fragment_index = int(fragment["sequence"])
            break
        else:
            start_byte -= fragment["size"]
    # if range header was given then to allow seeking in the browser we need to return 206 - partial response. 
    # Otherwise, the response was probably called by download browser function, and we need to return 200
    if range_header:
        status = 206
    else:
        status = 200

    response = StreamingHttpResponse(file_iterator(selected_fragment_index, start_byte, end_byte, real_start_byte), content_type=file["mimetype"], status=status)

    file_size = file["size"]
    real_end_byte = 0
    for i in range(selected_fragment_index):
        real_end_byte += fragments[i]["size"]
    referer = request.headers.get('Referer')

    # Set the X-Frame-Options header to the request's origin
    if referer:
        response['X-Frame-Options'] = f'ALLOW-FROM {referer}'
    else:
        response['X-Frame-Options'] = 'DENY'

    response['Content-Length'] = file_size
    response['Content-Disposition'] = content_disposition

    if file["type"] == "text":
        response['Cache-Control'] = "no-cache"
    else:
        response['Cache-Control'] = f"max-age={2628000}"  # 1 month

    if range_header:
        response['Content-Range'] = 'bytes %s-%s/%s' % (real_start_byte, real_end_byte - 1, file_size)  # this -1 is vevy important
        response['Accept-Ranges'] = 'bytes'

        response['Content-Length'] = real_end_byte - real_start_byte

    return response


@api_view(['GET'])
@throttle_classes([UserRateThrottle])
def stream_zip_files(request, token):
    files = []

    def stream_zip_file(file, chunk_size=8192):
        signed_id = file['signed_id']
        fragments = file['fragments']
        is_encrypted = file['is_encrypted']
        key = file['key']
        iv = file['iv']
        if is_encrypted:
            # luckily or not - we store both key and iv in the database
            key = base64.b64decode(key)
            iv = base64.b64decode(iv)

            cipher = Cipher(algorithms.AES(key), modes.CTR(iv), backend=default_backend())
            decryptor = cipher.decryptor()

        for fragment in fragments:
            fragment_response = requests.get(f"{iDriveBackend}/fragments/{signed_id}/{fragment['sequence']}")
            print(f"{iDriveBackend}/fragments/{signed_id}/{fragment['sequence']}")
            if not fragment_response.ok:
                print("============ERROR============")
                print(fragment_response.status_code)
                print(fragment_response.text)
                return
            url = fragment_response.json()["url"]

            discord_response = requests.get(url, stream=True)
            for raw_data in discord_response.iter_content(chunk_size):
                if is_encrypted:
                    decrypted_data = decryptor.update(raw_data)
                    yield decrypted_data
                else:
                    yield raw_data

    res = requests.get(f"{iDriveBackend}/zip/{token}")
    print(f"{iDriveBackend}/zip/{token}")
    if not res.ok:
        return JsonResponse(status=res.status_code, data=res.json())
    res_json = res.json()
    for file in res_json["files"]:

        if not file["isDir"]:
            print(file)
            file = GenFile(name=file['name'], generator=stream_zip_file(file), size=file["size"])
            files.append(file)

    zipFly = ZipFly(files)

    # streamed response
    response = StreamingHttpResponse(
        zipFly.stream(),
        content_type="application/zip")

    response['Content-Length'] = zipFly.calculate_archive_size()

    response['Content-Disposition'] = f'attachment; filename="{res_json["name"]}.zip"'

    return response


