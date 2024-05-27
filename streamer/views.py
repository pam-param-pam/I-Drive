import re

import requests

from django.http import StreamingHttpResponse, HttpResponse

from rest_framework.decorators import api_view, throttle_classes
from rest_framework.throttling import UserRateThrottle
"""
@api_view(['GET'])
@throttle_classes([UserRateThrottle])
def stream_file(request, signed_file_id):
    res = requests.get(f"http://127.0.0.1:8000/api/fragments/{signed_file_id}")

    if not res.ok:
        return HttpResponse(status=res.status_code)
    file = res.json()

    def file_iterator(index=1):
        while index <= file["fragments_length"]:
            res = requests.get(f"http://127.0.0.1:8000/api/fragment/{signed_file_id}/{index}")
            if not res.ok:
                return HttpResponse(status=res.status_code)

            fragment = res.json()
            url = fragment["url"]
            response = requests.get(url, stream=True, timeout=10)
            if response.ok:
                for chunk in response.iter_content(8192):
                    yield chunk

            index += 1

    response = StreamingHttpResponse(file_iterator(), content_type=file["mimetype"], status=200)
    response['Content-Disposition'] = f'attachment; filename="{file["name"]}"'

    return response


@api_view(['GET'])
@throttle_classes([UserRateThrottle])
def preview_file(request, signed_file_id):
    pass
"""

@api_view(['GET'])
@throttle_classes([UserRateThrottle])
def stream_file(request, signed_file_id):
    url = f"http://127.0.0.1:8000/api/fragments/{signed_file_id}"
    res = requests.get(url)
    print(url)
    if not res.ok:
        return HttpResponse(status=res.status_code)
    res = res.json()
    file = res["file"]
    fragments = res["fragments"]
    if len(fragments) == 0:
        return HttpResponse(status=204)

    def file_iterator(index, start_byte, end_byte, chunk_size=8192):
        while index <= len(fragments):
            url = f"http://127.0.0.1:8000/api/fragments/{signed_file_id}/{index}"
            res = requests.get(url)
            if not res.ok:
                return HttpResponse(status=res.status_code)

            fragment = res.json()
            url = fragment["url"]
            headers = {
                'Range': 'bytes={}-{}'.format(start_byte, end_byte) if end_byte else 'bytes={}-'.format(start_byte)}

            response = requests.get(url, headers=headers, stream=True)
            if response.ok:
                for chunk in response.iter_content(chunk_size):
                    yield chunk

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
        #response['Content-Disposition'] = f'attachment; filename="{file["name"]}"'
        pass
    return response

