import mimetypes
import mimetypes
import re
import time
from io import BytesIO

import aiohttp
import requests
from PIL import Image
from asgiref.sync import sync_to_async
from django.http import JsonResponse
from django.http import StreamingHttpResponse, HttpResponse
from django.views.decorators.cache import cache_page
from rest_framework.decorators import api_view, throttle_classes, permission_classes
from rest_framework.permissions import AllowAny
from zipFly import GenFile, ZipFly
from zipFly.EmptyFolder import EmptyFolder

from ..auth.Permissions import CheckLockedFolderIP
from ..auth.throttle import MediaThrottle, defaultAuthUserThrottle
from ..auth.utils import check_resource_perms
from ..constants import ALLOWED_THUMBNAIL_SIZES, cache, MAX_MEDIA_CACHE_AGE
from ..core.crypto.Decryptor import Decryptor
from ..core.decorators import extract_file_from_signed_url, no_gzip, check_resource_permissions
from ..core.errors import BadRequestError, FailedToResizeImageError
from ..core.http.utils import get_content_disposition_string, parse_range_header
from ..discord.Discord import discord
from ..models import File, UserZIP, Moment, Subtitle
from ..queries.builders import build_flattened_children, build_zip_file_dict
from ..queries.selectors import check_if_bots_exists
from ..tasks.helper import auto_prefetch


@api_view(['GET'])
@throttle_classes([MediaThrottle])
@permission_classes([AllowAny])
@extract_file_from_signed_url
@check_resource_permissions([CheckLockedFolderIP], resource_key="file_obj")
def stream_thumbnail(request, file_obj: File):
    size_param = request.GET.get("size", "original").lower()

    # Only allow specific sizes
    if size_param not in ALLOWED_THUMBNAIL_SIZES:
        raise BadRequestError(f"Invalid size: must be one of {', '.join(ALLOWED_THUMBNAIL_SIZES)}")

    cache_key = f"thumbnail:{file_obj.id}:{size_param}"
    thumbnail_content = cache.get(cache_key)

    if not thumbnail_content:
        check_if_bots_exists(file_obj.owner)

        thumbnail = file_obj.thumbnail
        decryptor = Decryptor(
            method=file_obj.get_encryption_method(),
            key=thumbnail.key,
            iv=thumbnail.iv
        )

        url = discord.get_attachment_url(file_obj.owner, thumbnail)
        discord_response = requests.get(url)
        if not discord_response.ok:
            return JsonResponse(status=discord_response.status_code, data=discord_response.json())

        thumbnail_content = decryptor.decrypt(discord_response.content)
        thumbnail_content += decryptor.finalize()

        if size_param != "original":
            try:
                resize_start = time.perf_counter()

                target_size = int(size_param)

                image = Image.open(BytesIO(thumbnail_content))
                image = image.convert("RGB")

                orig_width, orig_height = image.size
                aspect_ratio = orig_width / orig_height

                if orig_width >= orig_height:
                    new_width = target_size
                    new_height = int(target_size / aspect_ratio)
                else:
                    new_height = target_size
                    new_width = int(target_size * aspect_ratio)

                image = image.resize((new_width, new_height), Image.LANCZOS)

                buffer = BytesIO()
                image.save(buffer, format="WEBP")
                thumbnail_content = buffer.getvalue()

                resize_duration = time.perf_counter() - resize_start
                print(f"[resize] Resized {file_obj.id} to {new_width}x{new_height} in {resize_duration:.3f}s")

            except Exception:
                raise FailedToResizeImageError("Failed to resize image")

        cache.set(cache_key, thumbnail_content, timeout=MAX_MEDIA_CACHE_AGE)

    response = HttpResponse(thumbnail_content, content_type="image/webp")
    name_ascii, name_encoded = get_content_disposition_string(f"thumbnail_{file_obj.get_name_no_extension()}.webp")
    response['Content-Disposition'] = f'attachment; filename="{name_ascii}"; filename*=UTF-8\'\'{name_encoded}'
    response["Cache-Control"] = f"max-age={MAX_MEDIA_CACHE_AGE}"

    # Set Vary header
    vary = response.get("Vary", "")
    vary_values = [v.strip() for v in vary.split(",") if v.strip()]
    for item in ["x-resource-password", "Query-Size"]:
        if item not in vary_values:
            vary_values.append(item)
    response["Vary"] = ", ".join(vary_values)

    return response


@api_view(['GET'])
@throttle_classes([MediaThrottle])
@permission_classes([AllowAny])
@extract_file_from_signed_url
@check_resource_permissions([CheckLockedFolderIP], resource_key="file_obj")
def stream_subtitle(request, file_obj: File, subtitle_id):
    check_if_bots_exists(file_obj.owner)

    subtitle = Subtitle.objects.get(file=file_obj, id=subtitle_id)
    decryptor = Decryptor(method=file_obj.get_encryption_method(), key=subtitle.key, iv=subtitle.iv)

    url = discord.get_attachment_url(file_obj.owner, subtitle)
    discord_response = requests.get(url)
    if discord_response.ok:
        subtitle_content = discord_response.content
        subtitle_content = decryptor.decrypt(subtitle_content)
        subtitle_content += decryptor.finalize()

    else:
        return JsonResponse(status=discord_response.status_code, data=discord_response.json())

    response = HttpResponse(subtitle_content)
    name_ascii, name_encoded = get_content_disposition_string(f"{subtitle.language}_subtitles_" + file_obj.get_name_no_extension() + ".vtt")
    response['Content-Disposition'] = f'attachment; filename="{name_ascii}"; filename*=UTF-8\'\'{name_encoded}'
    return response


@api_view(['GET'])
@throttle_classes([MediaThrottle])
@permission_classes([AllowAny])
@cache_page(60 * 60 * 24 * 30)
@extract_file_from_signed_url
@check_resource_permissions([CheckLockedFolderIP], resource_key="file_obj")
def stream_moment(request, file_obj: File, timestamp):
    check_if_bots_exists(file_obj.owner)

    moment = Moment.objects.get(file=file_obj, timestamp=timestamp)
    decryptor = Decryptor(method=file_obj.get_encryption_method(), key=moment.key, iv=moment.iv)

    url = discord.get_attachment_url(file_obj.owner, moment)
    discord_response = requests.get(url)
    if discord_response.ok:
        moment_content = decryptor.decrypt(discord_response.content)
    else:
        return JsonResponse(status=discord_response.status_code, data=discord_response.json())

    response = HttpResponse(moment_content, content_type="image/webp")
    name_ascii, name_encoded = get_content_disposition_string(f"moment_{file_obj.get_name_no_extension()}.webp")
    response['Content-Disposition'] = f'attachment; filename="{name_ascii}"; filename*=UTF-8\'\'{name_encoded}'
    return response


# todo  handle >416 Requested Range Not Satisfiable<
@api_view(['GET'])
@no_gzip
@throttle_classes([MediaThrottle])
@permission_classes([AllowAny])
@extract_file_from_signed_url
@check_resource_permissions([CheckLockedFolderIP], resource_key="file_obj")
def stream_file(request, file_obj: File):
    print(f"========={file_obj.name}=========")

    isInline = request.GET.get('inline', False)
    isDownload = request.GET.get('download', False)

    fragments = file_obj.fragments.all().order_by('sequence')
    user = file_obj.owner

    check_if_bots_exists(user)
    filename_ascii, encoded_filename = get_content_disposition_string(file_obj.name)
    content_disposition = f'{"inline" if isInline else "attachment"}; filename="{filename_ascii}"; filename*=UTF-8\'\'{encoded_filename}'

    # If file is empty, return no content but still allow it to be downloaded
    if len(fragments) == 0:
        response = HttpResponse()
        if not isInline:
            response['Content-Disposition'] = content_disposition
        return response

    async def file_iterator(index, start_byte, end_byte, real_start_byte, chunk_size=8192 * 16):
        async with aiohttp.ClientSession() as session:
            decryptor = Decryptor(method=file_obj.get_encryption_method(), key=file_obj.key, iv=file_obj.iv, start_byte=real_start_byte)

            while index < len(fragments):
                url = await sync_to_async(discord.get_attachment_url)(user, fragments[index])
                headers = {'Range': f'bytes={start_byte}-{end_byte}' if end_byte else f'bytes={start_byte}-'}

                async with session.get(url, headers=headers) as dc_res:
                    dc_res.raise_for_status()

                    total_decryption_time = 0
                    total_bytes = 0
                    async for raw_data in dc_res.content.iter_chunked(chunk_size):
                        start_time = time.perf_counter()
                        decrypted_data = decryptor.decrypt(raw_data)
                        end_time = time.perf_counter()
                        total_decryption_time += (end_time - start_time)
                        total_bytes += len(raw_data)

                        yield decrypted_data
                    print(f"Fragment index: {fragments[index].sequence}")
                    print(f"Time taken for decryption (seconds): {total_decryption_time:.6f} for {total_bytes / 1000_000}MB.")

                # Handle partial requests (single fragment)
                if not isDownload:
                    break

                index += 1

            if file_obj.is_encrypted():
                yield decryptor.finalize()

    # parse range header to get start byte and end byte
    range_header = request.headers.get('Range')
    is_range_header, start_byte, end_byte = parse_range_header(range_header)

    # Find the appropriate file fragment based on byte range request
    real_start_byte = start_byte
    selected_fragment_index = 1
    for fragment in fragments:
        if start_byte < fragment.size:
            selected_fragment_index = int(fragment.sequence)
            break
        else:
            start_byte -= fragment.size

    # if range header was given then to allow seeking in the browser we need to return 206 - partial response.
    # Otherwise, the response was probably called by download browser function, and we need to return 200
    if is_range_header and not isDownload:
        status = 206
    else:
        status = 200

    mime, _ = mimetypes.guess_type(file_obj.name)
    response = StreamingHttpResponse(file_iterator(selected_fragment_index - 1, start_byte, end_byte, real_start_byte), content_type=mime, status=status)

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
    if not isDownload:
        response['Accept-Ranges'] = 'bytes'

    response["ETag"] = file_obj.id

    if file_obj.type == "Text":
        response['Cache-Control'] = "no-cache"
    else:
        response['Cache-Control'] = f"max-age={MAX_MEDIA_CACHE_AGE}"  # 1 month

    if range_header:
        response['Content-Range'] = 'bytes %s-%s/%s' % (real_start_byte, real_end_byte - 1, file_size)  # this -1 is vevy important

    # if it's a download process in a browser, we want to return the entire file and not just 1 fragment
    if range_header and not isDownload:
        response['Content-Length'] = real_end_byte - real_start_byte

    return response


@api_view(['GET'])
@no_gzip
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([AllowAny])
def stream_zip_files(request, token):
    range_header = request.headers.get('Range')
    if range_header:
        range_match = re.match(r'bytes=(\d+)-(\d+)?', range_header)
        if range_match:
            start_byte = int(range_match.group(1))
        else:
            return HttpResponse(status=400)
    else:
        start_byte = 0

    user_zip = UserZIP.objects.get(token=token)
    user = user_zip.owner
    check_if_bots_exists(user)
    #todo secure for locked folders/files from wrong ip, exctract range header
    check_resource_perms(request, user_zip.files.first(), [CheckLockedFolderIP])

    async def stream_file(file_obj, fragments, chunk_size=8192 * 16):
        async with aiohttp.ClientSession() as session:
            decryptor = Decryptor(method=file_obj.get_encryption_method(), key=file_obj.key, iv=file_obj.iv)

            async for fragment in fragments:
                url = await sync_to_async(discord.get_attachment_url)(user, fragment)
                auto_prefetch(file_obj, fragment.id)

                async with session.get(url) as response:
                    response.raise_for_status()
                    async for raw_data in response.content.iter_chunked(chunk_size):
                        yield decryptor.decrypt(raw_data)

    files = user_zip.files.filter(ready=True, inTrash=False)
    folders = user_zip.folders.filter(ready=True, inTrash=False)
    dict_files = []

    single_root = False
    if len(files) == 0 and len(folders) == 1:
        single_root = True
        dict_files = build_flattened_children(folders[0], root_folder=folders[0])

    else:
        for file in files:
            file_dict = build_zip_file_dict(file, file.name)
            dict_files.append(file_dict)

        for folder in folders:
            folder_tree = build_flattened_children(folder, root_folder=folder)
            dict_files += folder_tree

    zip_name = user_zip.name if not single_root else folders[0].name
    zip_name += ".zip"
    files = []
    for file in dict_files:
        if not file["isDir"]:
            fragments = file['fileObj'].fragments.all().order_by("sequence")
            genFile = GenFile(name=file['name'], generator=stream_file(file["fileObj"], fragments), size=file["fileObj"].size, crc=file["fileObj"].crc)
            files.append(genFile)
        else:
            files.append(EmptyFolder(name=file['name']))

    zipFly = ZipFly(files, byte_offset=start_byte)
    if range_header:
        status = 206
    else:
        status = 200

    # streamed response
    response = StreamingHttpResponse(zipFly.async_stream_parallel(), content_type="application/zip", status=status)

    file_size = zipFly.calculate_archive_size()
    response['Content-Length'] = file_size
    response['Accept-Ranges'] = 'bytes'
    response["ETag"] = user_zip.id
    if range_header:
        response['Content-Range'] = 'bytes %s-%s/%s' % (start_byte, file_size - 1, file_size)
        response['Content-Length'] = file_size - start_byte

    zip_name_ascii, zip_name_encoded = get_content_disposition_string(zip_name)
    response['Content-Disposition'] = f'attachment; filename="{zip_name_ascii}"; filename*=UTF-8\'\'{zip_name_encoded}'
    return response
