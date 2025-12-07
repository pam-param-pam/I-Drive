from django.http import JsonResponse
from rest_framework.decorators import permission_classes, api_view, throttle_classes
from rest_framework.permissions import IsAuthenticated

from ..auth.Permissions import ReadPerms, DownloadPerms, default_checks
from ..auth.throttle import defaultAuthUserThrottle
from ..constants import API_BASE_URL
from ..core.decorators import check_bulk_permissions, extract_items_from_ids_annotated
from ..models import File
from ..services import zip_service


@api_view(['POST'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ReadPerms & DownloadPerms])
@extract_items_from_ids_annotated(file_values=File.STANDARD_VALUES, file_annotate=File.LOCK_FROM_ANNOTATE)
@check_bulk_permissions(default_checks)
def create_zip_model(request, items):
    user_zip = zip_service.create_zip_model(request.user, items)
    return JsonResponse({"download_url": f"{API_BASE_URL}/zip/{user_zip.token}"}, status=200)
