from django.http import HttpResponse, JsonResponse
from rest_framework.authtoken.models import Token
from rest_framework.decorators import permission_classes, api_view, throttle_classes
from rest_framework.permissions import IsAuthenticated

from website.utilities.decorators import handle_common_errors
from website.utilities.errors import ResourcePermissionError
from website.utilities.throttle import PasswordChangeThrottle
from djoser import  utils


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([PasswordChangeThrottle])
@handle_common_errors
def change_password(request):

    current_password = request.data['current_password']
    new_password = request.data['new_password']
    user = request.user

    if not user.check_password(current_password):
        raise ResourcePermissionError("Password is incorrect")

    user.set_password(new_password)
    user.save()

    utils.logout_user(request)

    token, created = Token.objects.get_or_create(user=user)
    print(token)
    data = {"auth_token": str(token)}
    print(data)
    return JsonResponse(data, status=200)

