import base64
import re
import time
from datetime import datetime
from urllib.parse import quote

import requests
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from django.http import StreamingHttpResponse, HttpResponse
from django.utils.encoding import smart_str
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.throttling import UserRateThrottle

from zipFly import GenFile, ZipFly


@api_view(['GET'])
@throttle_classes([UserRateThrottle])
def index(request):
    return HttpResponse(status=404)


@api_view(['GET'])
@throttle_classes([UserRateThrottle])
def thumbnail_file(request, signed_file_id):
    res = requests.get(f"http://127.0.0.1:8000/api/file/thumbnail/{signed_file_id}")
    if not res.ok:
        return HttpResponse(status=res.status_code)
    res_json = res.json()
    
    def file_iterator(url, chunk_size=8192):
        if res_json["is_encrypted"]:
            # luckily or not - we store both key and iv in the database
            key = base64.b64decode(res_json['key'])
            iv = base64.b64decode(res_json['iv'])

            cipher = Cipher(algorithms.AES(key), modes.CTR(iv), backend=default_backend())
            decryptor = cipher.decryptor()
        
        discord_response = requests.get(url, stream=True)
        if discord_response.ok:
            for raw_data in discord_response.iter_content(chunk_size):
                if res_json["is_encrypted"]:
                    decrypted_data = decryptor.update(raw_data)
                    yield decrypted_data
                else:
                    yield raw_data
            yield decryptor.finalize()
            
    response = StreamingHttpResponse(file_iterator(res_json["url"]), content_type="image/jpeg")
    response['Cache-Control'] = f"max-age={2628000}"  # 1 month
    return response


# todo  handle >416 Requested Range Not Satisfiable<
@api_view(['GET'])
@throttle_classes([UserRateThrottle])
def stream_file(request, signed_file_id):
    isInline = request.GET.get('inline', False)
    res = requests.get(f"http://127.0.0.1:8000/api/fragments/{signed_file_id}")
    if not res.ok:
        return HttpResponse(status=res.status_code)
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
            fragment_response = requests.get(f"http://127.0.0.1:8000/api/fragments/{signed_file_id}/{index}")
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

    # if file["type"] == "text":
    #     response['Cache-Control'] = "no-cache"
    # else:
    #     response['Cache-Control'] = f"max-age={2628000}"  # 1 month

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
            fragment_response = requests.get(f"http://127.0.0.1:8000/api/fragments/{signed_id}/{fragment['sequence']}")
            print(f"http://127.0.0.1:8000/api/fragments/{signed_id}/{fragment['sequence']}")
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

    res = requests.get(f"http://127.0.0.1:8000/api/zip/{token}")
    print(f"http://127.0.0.1:8000/api/zip/{token}")
    if not res.ok:
        return HttpResponse(status=res.status_code)
    res_json = res.json()
    for file in res_json["files"]:

        if not file["isDir"]:
            fragments = file["fragments"]
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
    # response['Content-Length'] = content_length

    return response


