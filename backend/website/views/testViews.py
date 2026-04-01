import ipaddress

from django.contrib.auth.models import User
from django.http import JsonResponse, HttpResponse
from rest_framework.decorators import api_view, throttle_classes, permission_classes
from rest_framework.permissions import AllowAny

from ..auth.throttle import defaultAuthUserThrottle
from ..core.helpers import get_ip
from ..discord.Discord import discord


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([AllowAny])
def get_discord_state(request, user_id):
    ip, _ = get_ip(request)
    ip_obj = ipaddress.ip_address(ip)
    if not ip_obj.is_private:
        return HttpResponse(status=404)

    user = User.objects.get(id=user_id)
    state = discord._get_user_state(user)
    return JsonResponse(state.to_dict(), safe=False)


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([AllowAny])
def your_ip(request):
    ip, from_nginx = get_ip(request)

    return JsonResponse({"ip": ip, "nginx": from_nginx})
