import os
import time

import requests
from django.contrib.auth.models import User
from django.http import JsonResponse, HttpResponse, StreamingHttpResponse
from rest_framework.decorators import api_view, throttle_classes

from ..models import File
from ..utilities.Discord import discord
from ..utilities.other import get_file, get_attr
from ..utilities.throttle import MediaThrottle


@api_view(['GET'])
@throttle_classes([MediaThrottle])
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
@throttle_classes([MediaThrottle])
def test(request, file_id):
    file_values = File.objects.filter(id__in=[file_id]).annotate(**File.LOCK_FROM_ANNOTATE).values(*File.STANDARD_VALUES)
    file_obj = get_file(file_id)
    # check_resource_perms(request, file_values[0], checkRoot=False, checkOwnership=False)
    # check_resource_perms(request, file_obj, checkRoot=False, checkOwnership=False)
    print(get_attr(file_obj, "parent__password"))
    print(file_values)
    print(file_obj)
    return JsonResponse(list(file_values), status=200, safe=False)

# @no_gzip
def test1(request):
    file_id = "9FbHJVrVSV2zF3BFE4Xxch"
    file_obj = get_file(file_id)

    thumbnail = file_obj.thumbnail
    url = discord.get_attachment_url(file_obj.owner, thumbnail)

    async def streamer():
        res = requests.get(url, stream=True)
        for chunk in res.iter_content():
            yield chunk

    response = StreamingHttpResponse(streamer(), content_type="image/jpeg", status=200)
    response['Content-Length'] = file_obj.thumbnail.size
    return response

