from django.http import JsonResponse
from rest_framework.decorators import permission_classes, api_view, throttle_classes
from rest_framework.permissions import IsAuthenticated

from ..models import UserZIP, File
from ..utilities.Permissions import DownloadPerms, default_checks
from ..utilities.constants import API_BASE_URL
from ..utilities.decorators import extract_items_from_ids_annotated, check_bulk_permissions, extract_items
from ..utilities.errors import MissingOrIncorrectResourcePasswordError
from ..utilities.other import validate_and_add_to_zip
from ..utilities.throttle import defaultAuthUserThrottle


@api_view(['POST'])
@permission_classes([IsAuthenticated & DownloadPerms])
@throttle_classes([defaultAuthUserThrottle])
@extract_items(source='data')
@check_bulk_permissions([*default_checks])
def create_zip_model(request, items):
    user_zip = UserZIP.objects.create(owner=request.user)

    for item in items:
        validate_and_add_to_zip(user_zip, item)

    user_zip.save()
    return JsonResponse({"download_url": f"{API_BASE_URL}/zip/{user_zip.token}"}, status=200)


