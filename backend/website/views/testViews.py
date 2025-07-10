import time

from django.contrib.auth.models import User
from django.http import JsonResponse
from rest_framework.decorators import api_view, throttle_classes

from ..discord.Discord import discord
from ..utilities.other import get_ip
from ..utilities.throttle import defaultAuthUserThrottle


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
def get_discord_state(request):
    user = User.objects.get(id=1)
    discord._get_channel_id(user)

    bots_dict = []

    state = discord.users_state[user.id]
    retry_timestamp = state.get('retry_timestamp')
    if retry_timestamp:
        remaining_time = state['retry_timestamp'] - time.time()
    else:
        remaining_time = None

    for token in state['tokens'].values():
        bots_dict.append(token)

    return JsonResponse({"blocked": state['blocked'], "retry_after": remaining_time, "bots": bots_dict}, safe=False)


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
def your_ip(request):
    ip, from_nginx = get_ip(request)

    return JsonResponse({"ip": ip, "nginx": from_nginx})

