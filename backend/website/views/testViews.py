from django.http import HttpResponse
from rest_framework.decorators import throttle_classes, api_view

from ..utilities.Discord import discord
from ..utilities.decorators import handle_common_errors
from ..utilities.throttle import MediaRateThrottle


@api_view(['GET'])
@throttle_classes([MediaRateThrottle])
# @handle_common_errors
def get_file_url_view(request):
    for i in range(40):
        discord.send_message("dupa")

    return HttpResponse("yay")