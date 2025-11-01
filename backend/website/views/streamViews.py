import io
import re
import time
from io import BytesIO
from urllib.parse import quote

import aiohttp
import exifread
import imageio
import rawpy
import requests
from PIL import Image
from asgiref.sync import sync_to_async
from cryptography.fernet import Fernet
from django.contrib.contenttypes.models import ContentType
from django.db.utils import IntegrityError
from django.http import JsonResponse
from django.http import StreamingHttpResponse, HttpResponse
from django.views.decorators.cache import cache_page
from rawpy._rawpy import LibRawUnsupportedThumbnailError, LibRawFileUnsupportedError
from rest_framework.decorators import api_view, throttle_classes, permission_classes
from rest_framework.permissions import AllowAny
from zipFly import GenFile, ZipFly
from zipFly.EmptyFolder import EmptyFolder

from ..discord.Discord import discord
from ..models import File, UserZIP, Moment, Subtitle
from ..models import Fragment, Preview
from ..utilities.Decryptor import Decryptor
from ..utilities.Permissions import CheckLockedFolderIP
from ..utilities.Serializers import FileSerializer
from ..utilities.constants import MAX_SIZE_OF_PREVIEWABLE_FILE, EventCode, cache, MAX_MEDIA_CACHE_AGE, ALLOWED_THUMBNAIL_SIZES
from ..utilities.decorators import extract_file_from_signed_url, no_gzip, check_resource_permissions
from ..utilities.errors import DiscordError, BadRequestError, FailedToResizeImage
from ..utilities.other import get_flattened_children, create_zip_file_dict, check_if_bots_exists, auto_prefetch, get_discord_author, get_content_disposition_string
from ..utilities.other import send_event
from ..utilities.throttle import MediaThrottle, defaultAuthUserThrottle


@api_view(['GET'])
@throttle_classes([MediaThrottle])
@permission_classes([AllowAny])
@cache_page(60 * 60 * 24)
@extract_file_from_signed_url
@check_resource_permissions([CheckLockedFolderIP], resource_key="file_obj")
def stream_preview(request, file_obj: File):
    try:
        preview = Preview.objects.get(file=file_obj)
        url = discord.get_attachment_url(file_obj.owner, preview)

        res = requests.get(url, timeout=20)
        if not res.ok:
            raise DiscordError(res)

        file_content = res.content
        fernet = Fernet(preview.key)
        decrypted_data = fernet.decrypt(file_content)
        response = HttpResponse(content_type="image/jpeg")
        response.write(decrypted_data)

        return response

    except Preview.DoesNotExist:
        pass

    fragments = Fragment.objects.filter(file=file_obj).order_by('sequence')
    if len(fragments) == 0:
        return HttpResponse(status=204)

    # RAW IMAGE FILE
    if file_obj.type == "Raw image":
        raise BadRequestError(f"Resource of type {file_obj.type} is not previewable")

    if file_obj.size > MAX_SIZE_OF_PREVIEWABLE_FILE:
        raise BadRequestError("File too big: size > 100mb")

    check_if_bots_exists(file_obj.owner)
    decryptor = Decryptor(method=file_obj.get_encryption_method(), key=file_obj.key, iv=file_obj.iv)

    file_content = b''
    for fragment in fragments:
        url = discord.get_attachment_url(file_obj.owner, fragment)
        response = requests.get(url, timeout=20)
        if not response.ok:
            raise DiscordError(response)

        decrypted_data = decryptor.decrypt(response.content)
        file_content += decrypted_data

    file_content += decryptor.finalize()
    file_like_object = io.BytesIO(file_content)

    try:
        with rawpy.imread(file_like_object) as raw:
            thumb = raw.extract_thumb()

        if thumb.format == rawpy.ThumbFormat.JPEG:
            data = io.BytesIO(thumb.data)

        elif thumb.format == rawpy.ThumbFormat.BITMAP:

            # thumb.data is an RGB numpy array, convert with imageio
            data = io.BytesIO()
            imageio.imwrite(data, thumb.data)

    except (LibRawFileUnsupportedError, LibRawUnsupportedThumbnailError):
        raise BadRequestError("Raw file cannot be read properly to extract preview image.")

    tags = exifread.process_file(file_like_object)
    model_name = str(tags.get("Image Model"))
    focal_length = str(tags.get("EXIF FocalLength"))
    aperture = str(tags.get("EXIF ApertureValue"))
    iso = str(tags.get("EXIF ISOSpeedRatings"))
    exposure_time = str(tags.get("EXIF ExposureTime"))

    # ENCRYPTION
    key = Fernet.generate_key()
    fernet = Fernet(key)
    encrypted_data = fernet.encrypt(data.getvalue())
    user = file_obj.owner
    attachment_name = user.discordsettings.attachment_name
    files = {'file': (attachment_name, encrypted_data)}

    message = discord.send_file(user, files) # todo migrate to webhooks

    size = data.getbuffer().nbytes
    encrypted_size = encrypted_data.__sizeof__()

    author = get_discord_author(request, message['author']['id'])

    try:
        preview = Preview.objects.create(
            file=file_obj,
            size=size,
            encrypted_size=encrypted_size,
            key=key,
            model_name=model_name,
            focal_length=focal_length,
            aperture=aperture,
            iso=iso,
            exposure_time=exposure_time,
            message_id=message["id"],
            attachment_id=message["attachments"][0]["id"],
            content_type=ContentType.objects.get_for_model(author),
            object_id=author.discord_id
        )

        file_dict = FileSerializer().serialize_object(file_obj)
        send_event(request.context, file_obj.parent, EventCode.ITEM_UPDATE, file_dict)

    except IntegrityError:
        pass
    response = HttpResponse(data.getvalue(), content_type="image/webp")
    name_ascii, name_encoded = get_content_disposition_string(f"preview_{file_obj.get_name_no_extension()}.webp")
    response['Content-Disposition'] = f'attachment; filename="{name_ascii}"; filename*=UTF-8\'\'{name_encoded}'
    return response


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
                raise FailedToResizeImage("Failed to resize image")

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
        if start_byte < fragment.size:
            selected_fragment_index = int(fragment.sequence)
            break
        else:
            start_byte -= fragment.size
    # if range header was given then to allow seeking in the browser we need to return 206 - partial response.
    # Otherwise, the response was probably called by download browser function, and we need to return 200
    if range_header and not isDownload:
        status = 206
    else:
        status = 200

    if request.META.get('share_context') and (status == 200 or isDownload):
        discord.send_message(file_obj.owner, f"{file_obj.name} has been downloaded!")

    elif request.META.get('share_context'):
        discord.send_message(file_obj.owner, f"{file_obj.name} has been watched!")

    response = StreamingHttpResponse(file_iterator(selected_fragment_index - 1, start_byte, end_byte, real_start_byte), content_type=file_obj.mimetype, status=status)

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
    #todo secure for locked folders/files from wrong ip
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
        dict_files = get_flattened_children(folders[0], root_folder=folders[0])

    else:
        for file in files:
            file_dict = create_zip_file_dict(file, file.name)
            dict_files.append(file_dict)

        for folder in folders:
            folder_tree = get_flattened_children(folder, root_folder=folder)
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
