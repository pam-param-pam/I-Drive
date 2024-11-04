from django.http import HttpResponse
from rest_framework.decorators import api_view, throttle_classes

from ..utilities.throttle import MediaRateThrottle
from ..utilities.decorators import check_folder_and_permissions

@api_view(['GET'])
@throttle_classes([MediaRateThrottle])
# @handle_common_errors
@check_folder_and_permissions
def get_folder_password(request, folder_obj):
    # get_folder()
    return HttpResponse("no")
    # return HttpResponse(folder_obj.password)


