import os
import re
import time
from datetime import datetime

import requests
from django.http import StreamingHttpResponse, HttpResponse
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.throttling import UserRateThrottle

from streamer.zipstream import ZipStream


@api_view(['GET'])
@throttle_classes([UserRateThrottle])
def thumbnail_file(request, signed_file_id):
    res = requests.get(f"http://127.0.0.1:8000/api/file/thumbnail/{signed_file_id}")
    if not res.ok:
        return HttpResponse(status=res.status_code)

    def file_iterator(url, chunk_size=8192):
        discord_response = requests.get(url, stream=True)
        if discord_response.ok:
            for chunk in discord_response.iter_content(chunk_size):
                yield chunk

    response = StreamingHttpResponse(file_iterator(res.json()["url"]), content_type="image/jpeg")
    response['Cache-Control'] = f"max-age={2628000}"  # 1 month
    return response


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
    if len(fragments) == 0:
        return HttpResponse(status=200)

    def file_iterator(index, start_byte, end_byte, chunk_size=8192):
        while index <= len(fragments):
            fragment_response = requests.get(f"http://127.0.0.1:8000/api/fragments/{signed_file_id}/{index}")
            if not fragment_response.ok:
                return HttpResponse(status=fragment_response.status_code)

            url = fragment_response.json()["url"]
            headers = {
                'Range': 'bytes={}-{}'.format(start_byte, end_byte) if end_byte else 'bytes={}-'.format(start_byte)}

            discord_response = requests.get(url, headers=headers, stream=True)
            if discord_response.ok:
                for chunk in discord_response.iter_content(chunk_size):
                    yield chunk
            else:
                print("============DISCORD ERROR============")
                print(discord_response.status_code)
                print(discord_response.text)
                return
            index += 1

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
        print("another fragment")
        if start_byte < fragment["size"]:
            selected_fragment_index = int(fragment["sequence"])
            break
        else:
            start_byte -= fragment["size"]

    if range_header:
        status = 206
    else:
        status = 200
    response = StreamingHttpResponse(file_iterator(selected_fragment_index, start_byte, end_byte),
                                     content_type=file["mimetype"],
                                     status=status
                                     )

    file_size = file["size"]
    i = 0
    real_end_byte = 0
    while i < selected_fragment_index:
        print(f"IIIIIIII {i}")
        real_end_byte += fragments[i]["size"]
        i += 1
    real_end_byte -= 1  # apparently this -1 is vevy important
    referer = request.headers.get('Referer')

    # Set the X-Frame-Options header to the request's origin
    if referer:
        response['X-Frame-Options'] = f'ALLOW-FROM {referer}'
    else:
        response['X-Frame-Options'] = 'DENY'

    response['Content-Length'] = file_size

    if file["type"] == "text":
        response['Cache-Control'] = "no-cache"
    else:
        response['Cache-Control'] = f"max-age={2628000}"  # 1 month

    if range_header:
        response['Content-Range'] = 'bytes %s-%s/%s' % (real_start_byte, real_end_byte, file_size)
        response['Accept-Ranges'] = 'bytes'
        response['Content-Length'] = real_end_byte - real_start_byte + 1  # apparently this +1 is vevy important

    else:
        if not isInline:
            response['Content-Disposition'] = f'attachment; filename="{file["name"]}"'
        pass
    return response


@api_view(['GET'])
@throttle_classes([UserRateThrottle])
def stream_zip_files(request, token):
    files = []

    def stream_zip_file(file_id, fragments, chunk_size=8192):
        for fragment in fragments:
            fragment_response = requests.get(f"http://127.0.0.1:8000/api/fragments/{file_id}/{fragment['sequence']}")
            if not fragment_response.ok:
                print("============ERROR============")
                print(fragment_response.status_code)
                print(fragment_response.text)
                return

            url = fragment_response.json()["url"]

            discord_response = requests.get(url, stream=True)
            for chunk in discord_response.iter_content(chunk_size):
                yield chunk

    res = requests.get(f"http://127.0.0.1:8000/api/zip/{token}")
    if not res.ok:
        return HttpResponse(status=res.status_code)
    res_json = res.json()
    for file in res_json["files"]:

        if not file["isDir"]:
            fragments = file["fragments"]

            modification_time = datetime.fromisoformat(file["modified_at"])
            modification_time_struct = time.localtime(modification_time.timestamp())
            file_dict = {'name': file['name'],
                         'stream': stream_zip_file(file['signed_id'], fragments),
                         "modification_time": modification_time_struct,
                         "size": file["size"],
                         "cmethod": None
            }

            files.append(file_dict)

    zip_stream = ZipStream(files)
    # streamed response
    response = StreamingHttpResponse(
        zip_stream.stream(),
        content_type="application/zip")
    response['Content-Disposition'] = f'attachment; filename="I-Drive-{res_json["id"]}.zip"'
    # response['Content-Length'] = content_length

    return response


@api_view(['GET'])
@throttle_classes([UserRateThrottle])
def stream_nonzip_files(request):
    def file_iterator(file_path, chunk_size=8192):
        with open(file_path, 'rb') as f:
            while True:
                chunk = f.read(chunk_size)
                if chunk:
                    yield chunk
                else:
                    break

    file_name = os.path.basename("The_Little_Mermaid.mp4")
    response = StreamingHttpResponse(file_iterator("streamer/The_Little_Mermaid.mp4"))
    response['Content-Type'] = 'application/octet-stream'
    response['Content-Disposition'] = 'attachment; filename="%s"' % file_name
    return response
