import base64
import os
import re
import time
from wsgiref.util import FileWrapper

import m3u8
import requests
from django.core.exceptions import ValidationError
from django.http import HttpResponse, StreamingHttpResponse, JsonResponse, HttpResponseBadRequest
from django.views.decorators.cache import cache_page
from django.views.decorators.clickjacking import xframe_options_sameorigin
from rest_framework.decorators import permission_classes, api_view, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle

from website.models import File, Fragment
from website.tasks import process_download
from website.utilities.Discord import discord
from website.utilities.decorators import check_file_and_permissions, view_cleanup
from website.utilities.other import create_temp_request_dir, create_temp_file_dir, build_response, error_res
from website.views.otherViews import range_re, RangeFileWrapper

DELAY_TIME = 0


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@check_file_and_permissions
def download(request, file_obj):
    time.sleep(DELAY_TIME)

    if file_obj.streamable:
        return HttpResponse(f"This file is not downloadable on this endpoint, use m3u8 file", status=404)

    # checking if the file is already downloaded
    file_path = os.path.join("temp", "downloads",
                             str(file_obj.id), file_obj.name)  # temp/downloads/file_id/name.extension
    if os.path.isfile(file_path):
        chunk_size = 8192
        response = StreamingHttpResponse(
            FileWrapper(
                open(file_path, "rb"),
                chunk_size,
            ),
            content_type='application/force-download',
        )
        response['Content-Disposition'] = f'attachment; filename={file_obj.name}'
        response['Content-Length'] = os.path.getsize(file_path)
        return response

    process_download.delay(request.user.id, request.request_id, file_obj.id)
    return JsonResponse(build_response(request.request_id, "file is being download..."))


@api_view(['GET'])
# @permission_classes([IsAuthenticated])
@view_cleanup
def stream_key(request, file_id):
    time.sleep(DELAY_TIME)

    try:
        file_obj = File.objects.get(id=file_id)
    except (File.DoesNotExist, ValidationError):

        return JsonResponse(error_res(user=request.user, code=400, error_code=8,
                                      details="File with id of 'file_id' doesn't exist."), status=400)
    if not file_obj.ready:
        return HttpResponse(f"This file is not uploaded yet", status=404)
    # if request.user != file_obj.owner:
    #   return HttpResponse(f"unauthorized", status=403)
    if not file_obj.streamable:
        return HttpResponse(f"This file is not streamable!", status=404)

    request_dir = create_temp_request_dir(request.request_id)
    file_dir = create_temp_file_dir(request_dir, file_obj.id)

    key_file_path = os.path.join(file_dir, "enc.key")

    with open(key_file_path, 'wb+') as file:
        file.write(file_obj.key)
        # Move the file cursor to the beginning before reading
        file.seek(0)  # vevy important
        file_content = file.read()

    response = HttpResponse(file_content, content_type='application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="key.enc"'
    return response


def process_m3u8(request_id, file_obj):
    file_url = discord.get_file_url(file_obj.m3u8_message_id)

    request_dir = create_temp_request_dir(request_id)
    file_dir = create_temp_file_dir(request_dir, file_obj.id)

    response = requests.get(file_url, stream=True)

    m3u8_file_path = os.path.join(file_dir, "manifest.m3u8")
    with open(m3u8_file_path, 'wb') as file:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                file.write(chunk)

    playlist = m3u8.load(m3u8_file_path)
    new_key = m3u8.Key(method="AES-128", base_uri=f"http://127.0.0.1:8000/api/stream_key/{file_obj.id}",
                       # TODO change it back later
                       uri=f"https://pamparampam.dev/api/stream_key/{file_obj.id}")
    new_key = m3u8.Key(method="AES-128", base_uri=f"http://127.0.0.1:8000/api/stream_key/{file_obj.id}",
                       # TODO change it back later
                       uri=f"http://127.0.0.1:8000/api/stream_key/{file_obj.id}")
    fragments = Fragment.objects.filter(file_id=file_obj).order_by('sequence')
    for fragment, segment in zip(fragments, playlist.segments.by_key(playlist.keys[-1])):
        url = f"http://127.0.0.1:8000/api/stream/fragment/{fragment.id}"
        segment.uri = url
        segment.key = new_key

    playlist.keys[-1] = new_key

    playlist.dump(m3u8_file_path)
    with open(m3u8_file_path, 'rb') as file:
        file_content = file.read()

    return file_content


@api_view(['GET'])
# @permission_classes([IsAuthenticated])
@view_cleanup
def get_m3u8(request, file_id):
    time.sleep(DELAY_TIME)

    try:
        file_obj = File.objects.get(id=file_id)
    except (File.DoesNotExist, ValidationError):
        return JsonResponse(error_res(user=request.user, code=400, error_code=8,
                                      details="File with id of 'file_id' doesn't exist."), status=400)
    if not file_obj.ready:
        return HttpResponse(f"This file is not uploaded yet", status=404)

    # if request.user != file_obj.owner:
    #   return HttpResponse(f"unauthorized", status=403)
    if not file_obj.streamable:
        return HttpResponse(f"This file is not streamable!", status=404)

    file_content = process_m3u8(request.request_id, file_obj)

    response = HttpResponse(file_content, content_type='application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="manifest.m3u8"'

    return response


@api_view(['GET'])
# @permission_classes([IsAuthenticated])
@throttle_classes([UserRateThrottle])
def stream_fragment(request, fragment_id):
    try:
        fragment = Fragment.objects.get(id=fragment_id)

        # if fragment.file.owner != request.user:
        #   return HttpResponse(f"unauthorized", status=403)

        url = discord.get_file_url(fragment.message_id)
        response = requests.get(url, stream=True)

        # Set the appropriate content type for your response (e.g., video/MP2T for a TS file)
        content_type = "video/MP2T"

        # Set content disposition if you want the browser to treat it as an attachment
        # response['Content-Disposition'] = 'attachment; filename="your_filename.ts"'

        # Create a streaming response with the remote content
        streaming_response = StreamingHttpResponse(
            (chunk for chunk in response.iter_content(chunk_size=8192)),
            content_type=content_type,
        )

        return streaming_response

    except Fragment.DoesNotExist:
        return JsonResponse(error_res(user=request.user, code=400, error_code=8,
                                      details="Fragment with id of 'fragment_id' doesn't exist."), status=400)


@api_view(['GET'])
@throttle_classes([UserRateThrottle])
# @permission_classes([IsAuthenticated])
@check_file_and_permissions
@cache_page(60 * 60 * 2)  # Cache for 2 hours (time in seconds)
@xframe_options_sameorigin
def get_file_preview(request, file_obj):

    fragments = Fragment.objects.filter(file=file_obj).order_by('sequence')

    def file_iterator(url, start_byte, end_byte, chunk_size=8192):
        #headers = {'Range': 'bytes={}-{}'.format(start_byte, end_byte) if end_byte else 'bytes={}-'.format(start_byte)}
        #headers=headers,
        response = requests.get(url,stream=True)
        if response.ok:  # Partial content
            for chunk in response.iter_content(chunk_size):
                yield chunk
        else:
            raise Exception("Failed to fetch partial content. Status code: {}".format(response.status_code))

    range_header = request.headers.get('Range')
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
    print("UwU")
    print(f"start_byte= {start_byte}")
    for fragment in fragments:
        print("another fragment")
        if start_byte < fragment.size:
            selected_fragment = fragment
            break
        else:
            start_byte -= fragment.size

    url = discord.get_file_url(selected_fragment.message_id, selected_fragment.attachment_id)
    print(url)
    print(start_byte)
    print(end_byte)
    response = StreamingHttpResponse(
        (chunk for chunk in file_iterator(url, 0, 0)),
        content_type='application/octet-stream',
        status=206 if range_header else 200,
    )

    file_size = file_obj.size
    if end_byte is None:
        end_byte = file_size - 1

    response['Content-Length'] = str(end_byte - start_byte + 1)
    response['Content-Range'] = 'bytes %s-%s/%s' % (start_byte, end_byte, file_size)
    response['Accept-Ranges'] = 'bytes'
    return response


@api_view(['GET'])
@throttle_classes([UserRateThrottle])
# @permission_classes([IsAuthenticated])
# @cache_page(60 * 60 * 2)  # Cache for 2 hours (time in seconds)
# @cache_page(60 * 60 * 60 * 60)  # Cache for a long time lol
def get_fragment_urls(request, file_id):
    try:

        # if file.owner != request.user:
        #    return HttpResponse(f"unauthorized", status=403)
        fileObj = File.objects.get(id=file_id)
        if not fileObj.ready:
            return HttpResponse(f"file not ready", status=404)

        serialized_key = base64.urlsafe_b64encode(fileObj.key).decode()

        fragments = Fragment.objects.filter(file=fileObj).order_by('sequence')
        fragments_list = []

        for fragment in fragments:
            fragments_list.append({
                "sequence": fragment.sequence,
                "url": f"http://127.0.0.1:8000/api/stream/fragment/{fragment.id}",
                "length": 30,
                "size": fragment.size,
                "encrypted_size": fragment.encrypted_size}
            )
        json_string = {"name": fileObj.name,
                       "id": fileObj.id,
                       "key": serialized_key,
                       "total_size": fileObj.size,
                       "fragments": fragments_list}

        return JsonResponse(json_string, safe=False, status=200)

    except File.DoesNotExist:
        return JsonResponse(error_res(user=request.user, code=400, error_code=8,
                                      details="File with id of 'file_id' doesn't exist."), status=400)
