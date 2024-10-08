import io
import re
import time
from urllib.parse import quote

import aiohttp
import exifread
import imageio
import rawpy
import requests
from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from django.db.utils import IntegrityError
from django.http import JsonResponse
from django.http import StreamingHttpResponse, HttpResponse
from django.utils.encoding import smart_str
from django.views.decorators.cache import cache_page
from rawpy._rawpy import LibRawUnsupportedThumbnailError, LibRawFileUnsupportedError
from rest_framework.decorators import api_view, throttle_classes
from zipFly import GenFile, ZipFly

from ..models import File, UserZIP
from ..models import Fragment, Preview
from ..utilities.Discord import discord
from ..utilities.constants import MAX_SIZE_OF_PREVIEWABLE_FILE, RAW_IMAGE_EXTENSIONS, EventCode, cache
from ..utilities.decorators import handle_common_errors, check_file, check_signed_url
from ..utilities.errors import DiscordError, BadRequestError
from ..utilities.other import get_flattened_children, create_zip_file_dict
from ..utilities.other import send_event
from ..utilities.throttle import MediaRateThrottle, MyUserRateThrottle


@cache_page(60 * 60 * 24)
@api_view(['GET'])
@throttle_classes([MediaRateThrottle])
@handle_common_errors
@check_signed_url
@check_file
def get_preview(request, file_obj: File):

    try:
        preview = Preview.objects.get(file=file_obj)
        url = discord.get_file_url(preview.message_id, preview.attachment_id)

        res = requests.get(url, timeout=20)
        if not res.ok:
            raise DiscordError(res.text, res.status_code)

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
    if file_obj.extension not in RAW_IMAGE_EXTENSIONS:
        raise BadRequestError(f"Resource of type {file_obj.type} is not previewable")

    if file_obj.size > MAX_SIZE_OF_PREVIEWABLE_FILE:
        raise BadRequestError("File too big: size > 100mb")

    key = file_obj.key
    iv = file_obj.encryption_iv
    cipher = Cipher(algorithms.AES(key), modes.CTR(iv), backend=default_backend())
    decryptor = cipher.decryptor()

    file_content = b''
    for fragment in fragments:
        url = discord.get_file_url(fragment.message_id, fragment.attachment_id)
        response = requests.get(url, timeout=20)
        if not response.ok:
            return HttpResponse(status=500,
                                content=f"Unexpected response from discord:\n{response.text}, status_code={response.status_code}")
        decrypted_data = decryptor.update(response.content)
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

    files = {'file': ('Kocham Alternatywki', encrypted_data)}

    response = discord.send_file(files)

    message = response.json()
    size = data.getbuffer().nbytes
    encrypted_size = encrypted_data.__sizeof__()

    preview = Preview(
        file=file_obj,
        size=size,
        attachment_id=message["attachments"][0]["id"],
        encrypted_size=encrypted_size,
        message_id=message["id"],
        key=key,
        model_name=model_name,
        focal_length=focal_length,
        aperture=aperture,
        iso=iso,
        exposure_time=exposure_time,
    )
    try:
        preview.save()
        file_dict = {"parent_id": file_obj.parent.id, "id": file_obj.id, "iso": preview.iso,
                     "model_name": preview.model_name,
                     "aperture": preview.aperture, "exposure_time": preview.exposure_time,
                     "focal_length": preview.focal_length}
        send_event(file_obj.owner.id, EventCode.ITEM_PREVIEW_INFO_ADD, request.request_id, [file_dict])

    except IntegrityError:
        pass
    return HttpResponse(data.getvalue(), content_type="image/jpeg")


@api_view(['GET'])
@throttle_classes([MediaRateThrottle])
@handle_common_errors
@check_signed_url
@check_file
def get_thumbnail(request, file_obj: File):
    thumbnail_content = cache.get(f"thumbnail:{file_obj.id}") # we have to manually cache this cuz html video poster is retarded and sends no-cache header (cringe)
    if not thumbnail_content:

        if file_obj.is_encrypted:

            cipher = Cipher(algorithms.AES(file_obj.key), modes.CTR(file_obj.encryption_iv), backend=default_backend())

            decryptor = cipher.decryptor()

        #todo potential security risk, without stream its possible to overload the server
        url = discord.get_file_url(file_obj.thumbnail.message_id, file_obj.thumbnail.attachment_id)
        discord_response = requests.get(url)
        if discord_response.ok:
            thumbnail_content = discord_response.content
            if file_obj.is_encrypted:
                thumbnail_content = decryptor.update(thumbnail_content)
                decryptor.finalize()

        else:
            return JsonResponse(status=discord_response.status_code, data=discord_response.json())

        cache.set(f"thumbnail:{file_obj.id}", thumbnail_content, timeout=2628000)  # 1 month

    response = HttpResponse(thumbnail_content, content_type="image/jpeg")
    response['Cache-Control'] = f"max-age={2628000}"  # 1 month
    return response



# todo  handle >416 Requested Range Not Satisfiable<
@api_view(['GET'])
@throttle_classes([MyUserRateThrottle])
@handle_common_errors
@check_signed_url
@check_file
def stream_file(request, file_obj: File):
    print(f"========={file_obj.name}=========")

    isInline = request.GET.get('inline', False)

    fragments = file_obj.fragments.all().order_by('sequence')

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

    # Function to increment the IV/counter
    def increment_iv(iv, bytes_to_skip):
        blocks_to_skip = bytes_to_skip // 16
        counter_int = int.from_bytes(iv, byteorder='big')  # Convert IV to integer
        counter_int += blocks_to_skip  # Increment by the number of blocks to skip
        new_iv = counter_int.to_bytes(len(iv), byteorder='big')  # Convert back to bytes
        return new_iv

    async def file_iterator(index, start_byte, end_byte, real_start_byte, chunk_size=8192):
        async with aiohttp.ClientSession() as session:
            if file_obj.is_encrypted:

                # Increment/adjust the IV counter for situations when we start decrypting in the middle of a file
                adjusted_iv = increment_iv(file_obj.encryption_iv, real_start_byte)

                cipher = Cipher(algorithms.AES(file_obj.key), modes.CTR(adjusted_iv), backend=default_backend())
                decryptor = cipher.decryptor()

            while index < len(fragments):
                url = discord.get_file_url(fragments[index].message_id, fragments[index].attachment_id)

                headers = {
                    'Range': 'bytes={}-{}'.format(start_byte, end_byte) if end_byte else 'bytes={}-'.format(start_byte)}

                async with session.get(url, headers=headers) as response:
                    if not response.ok:
                        print("===discord response error===")
                        print(response.status)
                        print(response.text())

                        print('bytes={}-{}'.format(start_byte, end_byte) if end_byte else 'bytes={}-'.format(start_byte))
                        print(fragments[index].sequence)
                        print(fragments[index].size)

                        return
                    # Asynchronously iterate over the content in chunks
                    total_decryption_time = 0
                    total_bytes = 0
                    async for raw_data in response.content.iter_chunked(chunk_size):
                        # If the file is encrypted, decrypt it asynchronously
                        if file_obj.is_encrypted:
                            start_time = time.perf_counter()
                            decrypted_data = decryptor.update(raw_data)
                            end_time = time.perf_counter()
                            total_decryption_time += (end_time - start_time)
                            total_bytes += len(raw_data)

                            yield decrypted_data
                        else:
                            # Yield raw data if not encrypted
                            yield raw_data
                    print(f"Fragment index: {fragments[index].sequence}")
                    print(f"Time taken for decryption (seconds): {total_decryption_time:.6f} for {total_bytes/1000_000}MB.")


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
    selected_fragment_index = 1
    for fragment in fragments:
        if start_byte < fragment.size:
            selected_fragment_index = int(fragment.sequence)
            break
        else:
            start_byte -= fragment.size
    # if range header was given then to allow seeking in the browser we need to return 206 - partial response.
    # Otherwise, the response was probably called by download browser function, and we need to return 200
    if range_header:
        status = 206
    else:
        status = 200

    response = StreamingHttpResponse(file_iterator(selected_fragment_index-1, start_byte, end_byte, real_start_byte), content_type=file_obj.mimetype, status=status)

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

    # if file_obj.type == "text": //todo uncomment this
    response['Cache-Control'] = "no-cache"
    # else:
    #     response['Cache-Control'] = f"max-age={2628000}"  # 1 month

    if range_header:
        response['Content-Range'] = 'bytes %s-%s/%s' % (real_start_byte, real_end_byte - 1, file_size)  # this -1 is vevy important
        response['Accept-Ranges'] = 'bytes'

        response['Content-Length'] = real_end_byte - real_start_byte

    return response


@api_view(['GET'])
@throttle_classes([MyUserRateThrottle])
@handle_common_errors
def stream_zip_files(request, token):

    async def stream_zip_file(file_obj: File, fragments, chunk_size=8192):
        print(f"========={file_obj.name}=========")

        if file_obj.is_encrypted:
            # luckily or not - we store both key and iv in the database
            key = file_obj.key
            iv = file_obj.encryption_iv

            cipher = Cipher(algorithms.AES(key), modes.CTR(iv), backend=default_backend())
            decryptor = cipher.decryptor()

        async for fragment in fragments:

            url = discord.get_file_url(fragment.message_id, fragment.attachment_id)
            async with aiohttp.ClientSession() as session:

                async with session.get(url) as response:
                    if not response.ok:
                        print("===discord response error===")
                        return
                    # Asynchronously iterate over the content in chunks
                    async for raw_data in response.content.iter_chunked(chunk_size):
                        # If the file is encrypted, decrypt it asynchronously
                        if file_obj.is_encrypted:
                            decrypted_data = decryptor.update(raw_data)
                            yield decrypted_data
                        else:
                            # Yield raw data if not encrypted
                            yield raw_data

    user_zip = UserZIP.objects.get(token=token)
    files = user_zip.files.all()
    folders = user_zip.folders.all()
    dict_files = []

    single_root = False
    if len(files) == 0 and len(folders) == 1:
        single_root = True
        dict_files += get_flattened_children(folders[0], single_root=single_root)

    else:
        for file in files:
            file_dict = create_zip_file_dict(file, file.name)
            dict_files.append(file_dict)

        for folder in folders:
            folder_tree = get_flattened_children(folder)
            dict_files += folder_tree
    zip_name = user_zip.name if not single_root else folders[0].name

    files = []
    for file in dict_files:

        if not file["isDir"]:
            fragments = file["fileObj"].fragments.all()

            file = GenFile(name=file['name'], generator=stream_zip_file(file["fileObj"], fragments), size=file["fileObj"].size)
            files.append(file)

    zipFly = ZipFly(files)

    # streamed response
    response = StreamingHttpResponse(
        zipFly.async_stream(),
        content_type="application/zip")

    response['Content-Length'] = zipFly.calculate_archive_size()

    response['Content-Disposition'] = f'attachment; filename="{zip_name}.zip"'

    return response