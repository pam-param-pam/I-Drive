import json

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.http import JsonResponse, HttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.decorators import throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated

from ..utilities.constants import cache
from ..utilities.errors import BadRequestError, ResourcePermissionError, ResourceNotFoundError
from ..utilities.other import create_token, create_qr_session, create_token_from_qr_session
from ..utilities.throttle import LoginThrottle, RegisterThrottle
from ..tasks import queue_ws_event


@api_view(['POST'])
@throttle_classes([LoginThrottle])
@permission_classes([AllowAny])
def login_per_device(request):
    username = request.data['username']
    password = request.data['password']

    user = authenticate(request, username=username, password=password)
    if not user:
        raise BadRequestError('Invalid credentials')

    raw_token, token_instance, auth_dict = create_token(request, user)

    return JsonResponse(auth_dict, status=200)


@api_view(['POST'])
@throttle_classes([LoginThrottle])
@permission_classes([IsAuthenticated])
def logout_per_device(request):
    """
    Logs out current device by deleting the token used in this request.
    """
    request.auth.revoke()
    return HttpResponse(status=204)


@api_view(['POST'])
@throttle_classes([RegisterThrottle])
@permission_classes([AllowAny])
def register_user(request):
    raise ResourcePermissionError("This functionality is turned off.")
    username = request.data['username']
    password = request.data['password']

    if User.objects.filter(username=username):
        return HttpResponse("This username is taken", status=409)

    user = User.objects.create_user(username=username, password=password)
    user.save()
    auth_dict, token_instance, auth_dict = create_token(request, user)
    return JsonResponse(auth_dict, status=200)


@api_view(['POST'])
@throttle_classes([LoginThrottle])
@permission_classes([AllowAny])
def get_qr_session(request):
    auth_dict = create_qr_session(request)
    return JsonResponse(auth_dict, status=200)


@api_view(['POST'])
@throttle_classes([LoginThrottle])
@permission_classes([IsAuthenticated])
def authenticate_qr_session(request, session_id):
    key = f"qr_session:{session_id}"
    session_json = cache.get(key)

    if not session_json:
        raise ResourceNotFoundError("Invalid or expired session")

    session_data = json.loads(session_json)

    session_data["authenticated"] = True
    session_data["approved_by_user_id"] = request.user.id
    session_data["approved_by_username"] = request.user.username

    desktop_user = request.user
    raw_token, token_instance, token_info = create_token_from_qr_session(request, desktop_user, session_data)

    # Save updated session data back to cache
    session_data["token"] = token_info
    cache.delete(key)

    auth_data = {"auth_token": token_info["auth_token"], "device_id": token_info["device_id"]}

    queue_ws_event.delay(
        'qrcode',
        {
            'type': 'approve_session',
            'session_id': session_id,
            'message': auth_data
        }
    )

    return HttpResponse(status=200)


@api_view(['GET'])
@throttle_classes([LoginThrottle])
@permission_classes([IsAuthenticated])
def get_qr_session_device_info(request, session_id):
    key = f"qr_session:{session_id}"
    session_json = cache.get(key)

    if not session_json:
        raise ResourceNotFoundError("Invalid or expired session")

    session_data = json.loads(session_json)
    return JsonResponse(session_data, status=200)
