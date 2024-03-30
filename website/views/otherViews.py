import time

from django.http import HttpResponse
from rest_framework.decorators import permission_classes, api_view, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle

from website.utilities.decorators import check_folder_and_permissions

DELAY_TIME = 0
@api_view(['GET'])
@permission_classes([IsAuthenticated])
@throttle_classes([UserRateThrottle])
def index(request):
    time.sleep(DELAY_TIME)

    return HttpResponse(f"hello {request.user}")

#def test(request):
#    return HttpResponse(f"yupi", status=200)




# Example usage in a view
@check_folder_and_permissions
def test(request, folder_obj):
    # Your delete file logic here using file_obj
    print(folder_obj.get_all_children())
    return HttpResponse()
