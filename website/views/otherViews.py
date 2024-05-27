from cryptography.fernet import Fernet
from django.http import JsonResponse
from rest_framework.decorators import permission_classes, api_view, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle

from website.models import File
from website.utilities.Discord import discord
from website.utilities.decorators import handle_common_errors

DELAY_TIME = 0

import requests
from django.http import HttpResponse

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import base64
@api_view(['GET'])
@permission_classes([IsAuthenticated])
@throttle_classes([UserRateThrottle])
def index(request):

    return HttpResponse(f"hello {request.user}")

def generate_keys(request):
    key = Fernet.generate_key()
    return JsonResponse({'key': key.decode()})

def test(request):
    message = discord.get_message(1244267985858986069)
    url = message.json()["attachments"][0]["url"]

    # key = request.data.get('key')
    # iv = request.data.get('iv')
    # file_url = request.data.get('file_url')

    key = "1234567890abcdef1234567890abcdef"
    iv = "/ty6CYdlQyH+3LoJh2VDIQ=="

    # Fetch the encrypted file from the URL
    response = requests.get(url)
    encrypted_data = response.content

    # Decode the base64 encoded key and IV
    key = base64.b64decode(key)
    iv = base64.b64decode(iv)

    # Decrypt the file
    backend = default_backend()
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=backend)
    decryptor = cipher.decryptor()
    decrypted_data = decryptor.update(encrypted_data) + decryptor.finalize()

    response = HttpResponse(decrypted_data, content_type='application/octet-stream')
    response['Content-Disposition'] = 'attachment; filename="decrypted_file"'
    return response


"""
# Example usage in a view
@check_file_and_permissions
@handle_common_errors
def test(request, file_obj):
    print(file_obj.name)

    fragments = Fragment.objects.filter(file=file_obj)
    attachment_id = fragments[0].attachment_id
    message_id = fragments[0].message_id
    url = discord.get_file_url(message_id, attachment_id)
    # Your delete file logic here using file_obj
    return HttpResponse(url)
"""
@handle_common_errors
def help1(request):
    files = File.objects.filter(owner_id=1)
    for file in files:
        if not file.ready:
            file.delete()
    return HttpResponse("deleted")

