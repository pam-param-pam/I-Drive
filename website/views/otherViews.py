import time

from django.http import HttpResponse
from rest_framework.decorators import permission_classes, api_view, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle

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
def test(request, file_obj):
    # Your delete file logic here using file_obj
    return HttpResponse(file_obj.name)
