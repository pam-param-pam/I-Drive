import time

from django.contrib.auth.models import User
from django.http import JsonResponse, HttpResponse
from rest_framework.decorators import api_view, throttle_classes, permission_classes
from rest_framework.permissions import IsAuthenticated

from ..models import Folder, Fragment, Preview, Thumbnail
from ..utilities.Discord import discord
from ..utilities.errors import BadRequestError
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
def folders_play(request):

    return HttpResponse(200)


@api_view(["POST"])
@throttle_classes([MediaRateThrottle])
@permission_classes([IsAuthenticated])
def proxy_discord(request):
    """Proxy file uploads to Discord while allowing streaming from the client."""
    # retarded discord >:(
    # todo secure to prevent denial of service
    json_payload = request.data.get("json_payload")
    files = request.FILES  # Django handles files as an InMemoryUploadedFile or TemporaryUploadedFile

    if not json_payload:
        raise BadRequestError("Missing json_payload")

    # Directly send files to Discord without buffering
    res = discord.send_file(request.user, json=json_payload, files=files)

    return JsonResponse(res.json(), status=res.status_code, safe=False)
