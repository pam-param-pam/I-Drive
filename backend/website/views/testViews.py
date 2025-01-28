import time

from django.contrib.auth.models import User
from django.http import JsonResponse, HttpResponse
from rest_framework.decorators import api_view, throttle_classes

from ..models import Folder
from ..utilities.Discord import discord
from ..utilities.other import is_subitem
from ..utilities.throttle import MediaRateThrottle


@api_view(['GET'])
@throttle_classes([MediaRateThrottle])
# @handle_common_errors
def get_folder_password(request):
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
@throttle_classes([MediaRateThrottle])
# @handle_common_errors
def folders_play(request, folder_id):

    folder = Folder.objects.get(id=folder_id)
    print(folder.get_all_subfolders())
    files = folder.get_all_files()
    print(len(files))
    print(is_subitem(files[100], folder))


    return HttpResponse(200)

