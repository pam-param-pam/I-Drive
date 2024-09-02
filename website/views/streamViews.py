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

from website.models import Fragment, Preview, File
from website.utilities.Discord import discord
from website.utilities.constants import MAX_SIZE_OF_PREVIEWABLE_FILE, RAW_IMAGE_EXTENSIONS, EventCode
from website.utilities.decorators import handle_common_errors, check_signed_url, check_file
from website.utilities.errors import ResourceNotPreviewableError, DiscordError
from website.utilities.other import send_event
from website.utilities.throttle import MediaRateThrottle

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

@cache_page(60 * 60 * 24)
@api_view(['GET'])
@throttle_classes([MediaRateThrottle])
@check_signed_url
@check_file
@handle_common_errors
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
        raise ResourceNotPreviewableError(f"Resource of type {file_obj.type} is not previewable")

    if file_obj.size > MAX_SIZE_OF_PREVIEWABLE_FILE:
        raise ResourceNotPreviewableError("File too big: size > 100mb")

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


