from django.http import JsonResponse, HttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.decorators import throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated

from ..auth.Permissions import ChangePassword
from ..auth.throttle import LoginThrottle, RegisterThrottle, PasswordChangeThrottle
from ..services import auth_service


@api_view(['POST'])
@throttle_classes([LoginThrottle])
@permission_classes([AllowAny])
def login_per_device_view(request):
    username = request.data['username']
    password = request.data['password']

    raw_token, token_obj = auth_service.login_device(request, username, password)
    auth_data = {"auth_token": raw_token, "device_id": token_obj.device_id}
    return JsonResponse(auth_data, status=200)


@api_view(['POST'])
@throttle_classes([LoginThrottle])
@permission_classes([IsAuthenticated])
def logout_per_device_view(request):
    auth_service.logout_device(request, request.user, request.auth.device_id)
    return HttpResponse(status=204)


@api_view(['POST'])
@throttle_classes([RegisterThrottle])
@permission_classes([AllowAny])
def register_user_view(request):
    # raise ResourcePermissionError("This functionality is turned off.")
    username = request.data['username']
    password = request.data['password']

    raw_token, token_obj = auth_service.register_user(request, username, password)
    auth_data = {"auth_token": raw_token, "device_id": token_obj.device_id}
    return JsonResponse(auth_data, status=200)


@api_view(['PATCH'])
@throttle_classes([PasswordChangeThrottle])
@permission_classes([IsAuthenticated & ChangePassword])
def change_password_view(request):
    current_password = request.data['current_password']
    new_password = request.data['new_password']
    raw_token, token_obj = auth_service.change_password(request, request.user, current_password, new_password)
    auth_data = {"auth_token": raw_token, "device_id": token_obj.device_id}
    return JsonResponse(auth_data, status=200)


@api_view(['POST'])
@throttle_classes([LoginThrottle])
@permission_classes([AllowAny])
def get_qr_session_view(request):
    session_id, expire_at = auth_service.create_qr_session(request)
    auth_dict = {"session_id": session_id, "expire_at": expire_at}
    return JsonResponse(auth_dict, status=200)


@api_view(['POST'])
@throttle_classes([LoginThrottle])
@permission_classes([IsAuthenticated])
def authenticate_qr_session_view(request, session_id):
    auth_service.authenticate_qr_session(request.user, session_id)
    return HttpResponse(status=204)


@api_view(['GET'])
@throttle_classes([LoginThrottle])
@permission_classes([IsAuthenticated])
def get_qr_session_device_info_view(request, session_id):
    session_data = auth_service.get_qr_session_device_info(request.user, session_id)
    return JsonResponse(session_data, status=200)


@api_view(['GET'])
@throttle_classes([LoginThrottle])
@permission_classes([IsAuthenticated])
def cancel_pending_qr_session_view(request, session_id):
    auth_service.cancel_pending_qr_session(session_id)
    return HttpResponse(status=204)
