import io

import exifread
import imageio
import rawpy
import requests
from cryptography.fernet import Fernet
from django.db.utils import IntegrityError
from django.http import HttpResponse
from django.views.decorators.cache import cache_page
from rawpy._rawpy import LibRawUnsupportedThumbnailError, LibRawFileUnsupportedError
from rest_framework.decorators import api_view, throttle_classes

from website.models import Fragment, Preview
from website.utilities.Discord import discord
from website.utilities.OPCodes import EventCode
from website.utilities.constants import MAX_SIZE_OF_PREVIEWABLE_FILE, RAW_IMAGE_EXTENSIONS
from website.utilities.decorators import handle_common_errors, check_signed_url, check_file
from website.utilities.errors import ResourceNotPreviewableError, DiscordError
from website.utilities.other import send_event
from website.utilities.throttle import MediaRateThrottle


@cache_page(60 * 60 * 24)
@api_view(['GET'])
@throttle_classes([MediaRateThrottle])
@check_signed_url
@check_file
@handle_common_errors
def preview(request, file_obj):

    try:
        preview = Preview.objects.get(file=file_obj)
        url = discord.get_file_url(preview.message_id, preview.attachment_id)

        res = requests.get(url)
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
        raise ResourceNotPreviewableError(f"Resource of type {file_obj.type} is not previewable")

    file_content = b''
    for fragment in fragments:
        url = discord.get_file_url(fragment.message_id, fragment.attachment_id)
        response = requests.get(url)
        if not response.ok:
            return HttpResponse(status=500,
                                content=f"Unexpected response from discord:\n{response.text}, status_code={response.status_code}")
        file_content += response.content
    file_like_object = io.BytesIO(file_content)

    if file_obj.size > MAX_SIZE_OF_PREVIEWABLE_FILE:
        raise ResourceNotPreviewableError("File too big: size > 100mb")
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
        raise ResourceNotPreviewableError("Raw file cannot be read properly to extract preview image.")

    tags = exifread.process_file(file_like_object)
    # print(tags)
    model_name = str(tags.get("Image Model"))
    focal_length = str(tags.get("EXIF FocalLength"))
    aperture = str(tags.get("EXIF ApertureValue"))
    iso = str(tags.get("EXIF ISOSpeedRatings"))
    exposure_time = str(tags.get("EXIF ExposureTime"))

    # ENCRYPTION
    key = Fernet.generate_key()
    fernet = Fernet(key)
    encrypted_data = fernet.encrypt(data.getvalue())

    files = {'file': ('1', encrypted_data)}

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


def last_modified_func(request, file_obj):
    last_modified_str = file_obj.last_modified_at
    return last_modified_str

"""
#@cache_page(60 * 60 * 24)
@api_view(['GET'])
@throttle_classes([MediaRateThrottle])
@check_signed_url
@check_file
@handle_common_errors
@last_modified(last_modified_func)
def stream_file(request, file_obj):
    
    This view is used only to stream videos and songs as it supports byte range(hence seeking)
    It should not be used to display images, pdfs or for download purposes
    
    fragments = Fragment.objects.filter(file=file_obj).order_by('sequence')
    if len(fragments) == 0:
        return HttpResponse(status=204)

    def file_iterator(index, start_byte, end_byte, chunk_size=8192):
        headers = {'Range': 'bytes={}-{}'.format(start_byte, end_byte) if end_byte else 'bytes={}-'.format(start_byte)}

        url = discord.get_file_url(fragments[index].message_id, fragments[index].attachment_id)
        response = requests.get(url, headers=headers, stream=True)
        if response.ok:
            for chunk in response.iter_content(chunk_size):
                yield chunk
        else:
            print("============DISCORD ERROR============")
            print(response.status_code)
            print(response.text)
            return 

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
    real_start_byte = start_byte
    selected_fragment_index = 0
    for index, fragment in enumerate(fragments):
        print("another fragment")
        if start_byte < fragment.size:
            selected_fragment_index = index
            break
        else:
            start_byte -= fragment.size

    if len(fragments) == 1 and start_byte == 0:
        status = 200
    else:
        status = 206

    response = StreamingHttpResponse(file_iterator(selected_fragment_index, start_byte, end_byte),
                                     content_type=file_obj.mimetype,
                                     status=status
                                     )

    file_size = file_obj.size
    i = 0
    real_end_byte = 0
    while i <= selected_fragment_index:
        real_end_byte += fragments[i].size
        i += 1
    real_end_byte -= 1  # apparently this -1 is vevy important
    referer = request.headers.get('Referer')

    # Set the X-Frame-Options header to the request's origin
    if referer:
        response['X-Frame-Options'] = f'ALLOW-FROM {referer}'
    else:
        response['X-Frame-Options'] = 'DENY'

    response['Content-Length'] = file_size

    if file_obj.type == "text":
        response['Cache-Control'] = "no-cache"

    else:
        response['Cache-Control'] = f"max-age={MAX_MEDIA_CACHE_AGE}"

    if range_header:
        response['Content-Range'] = 'bytes %s-%s/%s' % (real_start_byte, real_end_byte, file_size)
        response['Accept-Ranges'] = 'bytes'
        response['Content-Length'] = real_end_byte - real_start_byte + 1  # apparently this +1 is vevy important
    return response


async def stream_test(request):
    async def fake_data_streamer():
        for i in range(10):
            yield b'some fake data\n\n'
            print(f"index {i}")
            await asyncio.sleep(0.5)


    return StreamingHttpResponse(fake_data_streamer())

def stream_test2(request):
    def fake_data_streamer():
        for i in range(10):
            yield b'some fake data\n\n'
            print(f"index2 {i}")
            time.sleep(0.5)

    return StreamingHttpResponse(fake_data_streamer())

async def stream_file_test(request):
    file_obj = File.objects.get(id="4z2yiUsVY6ZoJLMjSSRETx")
    print(file_obj.name)
    fragments = Fragment.objects.filter(file=file_obj).order_by('sequence')

    async def file_iterator(index, start_byte, end_byte, chunk_size=8192):
        while index < len(fragments):
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

            index += 1

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

    response = StreamingHttpResponse(file_iterator(selected_fragment_index, start_byte, end_byte),
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
        # response['Content-Length'] = real_end_byte - real_start_byte
        response['Content-Length'] = real_end_byte - real_start_byte + 1  # apparently this +1 is vevy important
    return response
"""

"""
@cache_page(60 * 60 * 24)
@api_view(['GET'])
@throttle_classes([MediaRateThrottle])
@check_signed_url
@check_file
@handle_common_errors
def thumbnail(request, file_obj):
    try:
        thumbnail = Thumbnail.objects.get(file=file_obj)
        url = discord.get_file_url(thumbnail.message_id, thumbnail.attachment_id)
        file_response = requests.get(url)
        response = HttpResponse(content_type="image/jpeg")
        response.write(file_response.content)
        return response

    except Thumbnail.DoesNotExist:
        raise BadRequestError("whoopsie")

# Creating a thumbnail from the image data
        image = Image.open(data)
        MAX_SIZE = (250, 250)
        image.thumbnail(MAX_SIZE)
        print("generating thumbnail!")
        # Save the thumbnail to an in-memory file-like object
        thumb_data = io.BytesIO()
        image.save(thumb_data, format='PNG')

        files = {'file': ('1', thumb_data)}
        response = discord.send_file(files)
        message = response.json()
        file_size = thumb_data.getbuffer().nbytes

        thumbnail = Thumbnail(
            file=file_obj,
            size=file_size,
            attachment_id=message["attachments"][0]["id"],
            encrypted_size=file_size,
            message_id=message["id"],
            key=b'#todo'
        )
        thumbnail.save()        
"""
