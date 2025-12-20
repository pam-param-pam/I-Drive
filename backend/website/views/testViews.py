import time

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.http import JsonResponse, HttpResponse
from rest_framework.decorators import api_view, throttle_classes, permission_classes
from rest_framework.permissions import AllowAny

from ..auth.throttle import defaultAuthUserThrottle
from ..discord.Discord import discord
from ..core.helpers import get_ip
from ..models import Fragment, Channel
# from ..models.file_related_models import FragmentLinker, FragmentLink
from ..queries.selectors import get_discord_author


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([AllowAny])
def get_discord_state(request):
    user = User.objects.get(id=1)
    discord._get_channel_for_user(user)

    bots_dict = []

    state = discord.users_state[user.id]
    retry_timestamp = state.get('retry_timestamp')
    if retry_timestamp:
        remaining_time = state['retry_timestamp'] - time.time()
    else:
        remaining_time = None

    for token in state['bots'].values():
        bots_dict.append(token)

    return JsonResponse({"blocked": state['blocked'], "retry_after": remaining_time, "bots": bots_dict}, safe=False)


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([AllowAny])
def your_ip(request):
    ip, from_nginx = get_ip(request)

    return JsonResponse({"ip": ip, "nginx": from_nginx})


@api_view(['POST'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([AllowAny])
def create_linker(request):
    links = request.data['links']
    channel_id = request.data['channel_id']
    message_id = request.data['message_id']
    message_author_id = request.data['author_id']

    channel = Channel.objects.get(discord_id=channel_id, owner=request.user)
    author = get_discord_author(request.user, message_author_id)

    with transaction.atomic():
        linker = FragmentLinker.objects.create(
            message_id=message_id,
            channel=channel,
            object_id=author.discord_id,
            content_type=ContentType.objects.get_for_model(author),
        )

        fragment_links = []
        for frag_attachment_id, sequence in links:
            fragment = Fragment.objects.get(attachment_id=frag_attachment_id)
            fragment_links.append(
                FragmentLink(
                    linker=linker,
                    fragment=fragment,
                    sequence=sequence,
                )
            )

        FragmentLink.objects.bulk_create(fragment_links)

    return HttpResponse(status=204)
