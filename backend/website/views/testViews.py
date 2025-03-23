import time

from django.contrib.auth.models import User
from django.http import JsonResponse, HttpResponse
from rest_framework.decorators import api_view, throttle_classes

from ..models import File
from ..utilities.Discord import discord
from ..utilities.other import get_file, get_attr
from ..utilities.throttle import MediaThrottle


@api_view(['GET'])
@throttle_classes([MediaThrottle])
# @handle_common_errors
def get_discord_state(request):
    user = User.objects.get(id=1)
    discord._get_channel_id(user)

    bots_dict = []

    state = discord.users[user.id]
    retry_timestamp = state.get('retry_timestamp')
    if retry_timestamp:
        remaining_time = state['retry_timestamp'] - time.time()
    else:
        remaining_time = None

    for token in state['tokens'].values():
        bots_dict.append(token)

    return JsonResponse({"locked": state['locked'], "retry_after": remaining_time, "bots": bots_dict}, safe=False)

@api_view(['GET'])
@throttle_classes([MediaThrottle])
# @handle_common_errors
def test(request, file_id):
    file_values = File.objects.filter(id__in=[file_id]).annotate(**File.LOCK_FROM_ANNOTATE).values(*File.STANDARD_VALUES)
    file_obj = get_file(file_id)
    # check_resource_perms(request, file_values[0], checkRoot=False, checkOwnership=False)
    # check_resource_perms(request, file_obj, checkRoot=False, checkOwnership=False)
    print(get_attr(file_obj, "parent__password"))
    print(file_values)
    print(file_obj)
    return JsonResponse(list(file_values), status=200, safe=False)
