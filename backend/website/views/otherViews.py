# views.py
import base64
import secrets

from django.http import JsonResponse, HttpResponse
from rest_framework.decorators import api_view, throttle_classes

from website.models import UserSettings
from website.utilities.throttle import MyUserRateThrottle


@api_view(['GET'])
@throttle_classes([MyUserRateThrottle])
def index(request):

    return HttpResponse(f"hello {request.user}")

@api_view(['GET'])
@throttle_classes([MyUserRateThrottle])
def test(request):
    return HttpResponse(f"hello {request.user}")

def generate_keys(request):
    encryption_key = secrets.token_bytes(32)
    # Encode the key in base64 for easier transmission over the network
    encoded_key = base64.b64encode(encryption_key).decode('utf-8')

    encoded_key = "azPde+aqukew8A47WS76bApTmZLECN/2ximV5pDsbNo="
    return JsonResponse({'key': encoded_key})