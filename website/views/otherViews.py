import time

from django.http import HttpResponse
from rest_framework.decorators import permission_classes, api_view, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle

import requests
from django.http import StreamingHttpResponse
from wsgiref.util import FileWrapper
import os
import re
from website.utilities.decorators import check_folder_and_permissions

DELAY_TIME = 0


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@throttle_classes([UserRateThrottle])
def index(request):
    time.sleep(DELAY_TIME)

    return HttpResponse(f"hello {request.user}")


# def test(request):
#    return HttpResponse(f"yupi", status=200)


# Example usage in a view
@check_folder_and_permissions
def test(request, folder_obj):
    # Your delete file logic here using file_obj
    print(folder_obj.get_all_children())
    return HttpResponse()


range_re = re.compile(r'bytes\s*=\s*(\d+)\s*-\s*(\d*)', re.I)


class RangeFileWrapper(object):
    def __init__(self, filelike, blksize=8192, offset=0, length=None):
        self.filelike = filelike
        self.filelike.seek(offset, os.SEEK_SET)
        self.remaining = length
        self.blksize = blksize

    def close(self):
        if hasattr(self.filelike, 'close'):
            self.filelike.close()

    def __iter__(self):
        return self

    def __next__(self):  # For Python 3 compatibility
        return self.next()

    def next(self):
        if self.remaining is None:
            # If remaining is None, we're reading the entire file.
            data = self.filelike.read(self.blksize)
            if data:
                return data
            raise StopIteration()
        else:
            if self.remaining <= 0:
                raise StopIteration()
            data = self.filelike.read(min(self.remaining, self.blksize))
            if not data:
                raise StopIteration()
            self.remaining -= len(data)
            return data


def stream(request, url):
    response = requests.get(url, stream=True)
    size = int(response.headers.get('Content-Length', 0))
    content_type = response.headers.get('Content-Type', 'application/octet-stream')

    range_header = request.META.get('HTTP_RANGE', '').strip()
    range_match = range_re.match(range_header)

    if range_match:
        first_byte, last_byte = range_match.groups()
        first_byte = int(first_byte) if first_byte else 0
        last_byte = int(last_byte) if last_byte else size - 1
        if last_byte >= size:
            last_byte = size - 1
        length = last_byte - first_byte + 1
        resp = StreamingHttpResponse(
            RangeFileWrapper(response.iter_content(chunk_size=8192), offset=first_byte, length=length),
            status=206,
            content_type=content_type
        )
        resp['Content-Length'] = str(length)
        resp['Content-Range'] = 'bytes %s-%s/%s' % (first_byte, last_byte, size)
    else:
        resp = StreamingHttpResponse(
            FileWrapper(response.raw, 8192),
            content_type=content_type
        )
        resp['Content-Length'] = str(size)
    resp['Accept-Ranges'] = 'bytes'
    return resp

"""
@api_view(['GET'])
@throttle_classes([UserRateThrottle])
#@permission_classes([IsAuthenticated])
@check_file_and_permissions
@cache_page(60 * 60 * 2)  # Cache for 2 hours (time in seconds)
@xframe_options_sameorigin
def get_file_preview(request, file_obj):
    if file_obj.size > 25 * 1023 * 1024:
        return JsonResponse(error_res(user=request.user, code=400, error_code=11,
                                      details=f"File size={file_obj.size} is too big, max allowed >25mb."),
                            status=400)
    fragments = Fragment.objects.filter(file=file_obj).order_by('sequence')
    if len(fragments) != 1:
        return JsonResponse(error_res(user=request.user, code=500, error_code=11,
                                      details=f"Unexpected, report this. File with size <25 has more than 1 fragment."),
                            status=400)

    url = discord.get_file_url(fragments[0].message_id, fragments[0].attachment_id)

    response = requests.get(url, stream=True)

    # Ensure the request was successful
    if response.status_code == 200:

        def file_iterator():
            for chunk in response.iter_content(chunk_size=8192):
                yield chunk

        streaming_response = StreamingHttpResponse(file_iterator(), content_type=file_obj.mimetype)
        streaming_response['Content-Disposition'] = 'inline'
        streaming_response['Accept-Ranges'] = 'bytes'
        streaming_response['Content-Length'] = 8192

        streaming_response['content-Range'] = file_obj.size

        return streaming_response
    else:
        # Handle the case where the file couldn't be fetched
        return HttpResponse("Failed to fetch file from URL", status=response.status_code)
"""
"""
second one
  #if file_obj.size > 25 * 1023 * 1024:
    #    return JsonResponse(error_res(user=request.user, code=400, error_code=11,
    #                                  details=f"File size={file_obj.size} is too big, max allowed >25mb."),
    #                        status=400)

    fragments = Fragment.objects.filter(file=file_obj).order_by('sequence')
    #if len(fragments) != 1:
    #    return JsonResponse(error_res(user=request.user, code=500, error_code=11,
    #                                  details=f"Unexpected, report this. File with size <25 has more than 1 fragment."),
    #                        status=400)

    url = discord.get_file_url(fragments[0].message_id, fragments[0].attachment_id)

    response = requests.get(url, stream=True)

    size = file_obj.size
    content_type = file_obj.mimetype

    range_header = request.META.get('Range', '').strip()
    range_match = range_re.match(range_header)

    if range_match:
        first_byte, last_byte = range_match.groups()
        first_byte = int(first_byte) if first_byte else 0
        last_byte = int(last_byte) if last_byte else size - 1
        if last_byte >= size:
            last_byte = size - 1
        length = last_byte - first_byte + 1
        response = requests.get(url, stream=True, headers={"Range": f"bytes={first_byte}-{last_byte}"})

        resp = StreamingHttpResponse(response.iter_content(chunk_size=8192),
                                     status=206,
                                     content_type=file_obj.mimetype
                                     )
        resp['Content-Length'] = str(length)
        resp['Content-Range'] = 'bytes %s-%s/%s' % (first_byte, last_byte, size)
    else:

        def file_iterator():
            for chunk in response.iter_content(chunk_size=8192):
                yield chunk

        resp = StreamingHttpResponse(file_iterator(), content_type=file_obj.mimetype)
        resp['Content-Length'] = str(size)

    resp['Accept-Ranges'] = 'bytes'
    return resp
"""
