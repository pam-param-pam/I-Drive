import time

from django.http import HttpResponse
from rest_framework.decorators import permission_classes, api_view, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle

from website.models import Fragment, File
from website.utilities.Discord import discord
from website.utilities.decorators import check_file_and_permissions, handle_common_errors

DELAY_TIME = 0


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@throttle_classes([UserRateThrottle])
def index(request):
    time.sleep(DELAY_TIME)

    return HttpResponse(f"hello {request.user}")


# def test(request):
#    return HttpResponse(f"yupi", status=200)


# Example usage in a view
@check_file_and_permissions
@handle_common_errors
def test(request, file_obj):
    print(file_obj.name)

    fragments = Fragment.objects.filter(file=file_obj)
    attachment_id = fragments[0].attachment_id
    message_id = fragments[0].message_id
    url = discord.get_file_url(message_id, attachment_id)
    # Your delete file logic here using file_obj
    return HttpResponse(url)

@handle_common_errors
def help1(request):
    files = File.objects.filter(owner_id=1)
    for file in files:
        if not file.ready:
            file.delete()
    return HttpResponse("deleted")

