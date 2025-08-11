from django.contrib.auth import authenticate
from django.http import JsonResponse, HttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.decorators import throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated

from ..utilities.errors import BadRequestError, ResourcePermissionError
from ..utilities.other import create_token
from ..utilities.throttle import LoginThrottle, RegisterThrottle


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle])
def login_per_device(request):
    username = request.data['username']
    password = request.data['password']

    user = authenticate(request, username=username, password=password)
    if not user:
        raise BadRequestError('Invalid credentials')

    raw_token, token_instance = create_token(request, user)

    return JsonResponse({'auth_token': raw_token, 'device_id': token_instance.device_id}, status=200)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([LoginThrottle])
def logout_per_device(request):
    """
    Logs out current device by deleting the token used in this request.
    """
    request.auth.revoke()
    return HttpResponse(status=204)


@api_view(['POST'])
@throttle_classes([RegisterThrottle])
def register_user(request):
    raise ResourcePermissionError("This functionality is turned off.")
    username = request.data['username']
    password = request.data['password']

    if User.objects.filter(username=username):
        return HttpResponse("This username is taken", status=409)

    user = User.objects.create_user(username=username, password=password)
    user.save()
    return HttpResponse(status=204)
