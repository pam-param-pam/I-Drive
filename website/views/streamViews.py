import re

import requests
from django.http import StreamingHttpResponse, HttpResponseBadRequest
from django.views.decorators.cache import cache_page
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle

from website.models import Fragment
from website.utilities.Discord import discord
from website.utilities.decorators import check_file_and_permissions, handle_common_errors, check_signed_url, check_file


@cache_page(60 * 60 * 24)
@api_view(['GET'])
@throttle_classes([AnonRateThrottle])
@check_signed_url
@check_file
@handle_common_errors
def stream_file(request, file_obj):
    print(file_obj.name)
    fragments = Fragment.objects.filter(file=file_obj).order_by('sequence')

    def file_iterator(index, start_byte, end_byte, chunk_size=8192):
        print(f"==file iterator==\nSTART_BYTE={start_byte}\nEND_BYTE={end_byte}")
        headers = {'Range': 'bytes={}-{}'.format(start_byte, end_byte) if end_byte else 'bytes={}-'.format(start_byte)}
        # headers = {}
        print(f"fragments lenght: {len(fragments)}")

        url = discord.get_file_url(fragments[index].message_id, fragments[index].attachment_id)
        print(url)
        response = requests.get(url, headers=headers, stream=True)
        if response.ok:  # Partial content
            for chunk in response.iter_content(chunk_size):
                yield chunk
        else:
            print("============DISCORD ERROR============")
            print(response.status_code)
            print(response.text)

    range_header = request.headers.get('Range')
    print(f"range_header: {range_header}")
    if range_header:
        range_match = re.match(r'bytes=(\d+)-(\d+)?', range_header)
        if range_match:
            start_byte = int(range_match.group(1))
            end_byte = int(range_match.group(2)) if range_match.group(2) else None
        else:
            return HttpResponseBadRequest("Invalid byte range request")
    else:
        start_byte = 0
        end_byte = None

    # Find the appropriate file fragment based on byte range request
    print(f"start_byte= {start_byte}")
    real_start_byte = start_byte
    print(f"real_start_byte= {start_byte}")
    selected_fragment_index = 0
    for index, fragment in enumerate(fragments):
        print("another fragment")
        if start_byte < fragment.size:
            selected_fragment_index = index
            break
        else:
            start_byte -= fragment.size
    print(f"selected_fragment_index = {selected_fragment_index}")

    print(f"start_byte after= {start_byte}")
    print(f"end_byte after= {end_byte}")
    print(f"real_start_byte after= {real_start_byte}")

    if len(fragments) == 1 and start_byte == 0:
        status = 200
    else:
        status = 206

    response = StreamingHttpResponse(
        (chunk for chunk in file_iterator(selected_fragment_index, start_byte, end_byte)),
        content_type=file_obj.mimetype,
        status=status,
    )

    file_size = file_obj.size
    i = 0
    real_end_byte = 0
    while i <= selected_fragment_index:
        real_end_byte += fragments[i].size
        i += 1
    real_end_byte -= 1  # apparently this -1 is vevy important
    # TODO calculate real fragments size here for real_end_byte

    response['Content-Length'] = file_size
    response['Cache-Control'] = "max-age=3600"
    if range_header:
        response['Content-Range'] = 'bytes %s-%s/%s' % (real_start_byte, real_end_byte, file_size)
        response['Accept-Ranges'] = 'bytes'
        #response['Content-Length'] = real_end_byte - real_start_byte
        response['Content-Length'] = real_end_byte - real_start_byte + 1  # apparently this +1 is vevy important
    return response


@api_view(['GET'])
# @permission_classes([IsAuthenticated])
@throttle_classes([UserRateThrottle])
@check_file_and_permissions
@handle_common_errors
def download_file(request, file_obj):
    raise NotImplementedError("Come back later :3")


