from django.http import JsonResponse
from rest_framework.decorators import permission_classes, api_view, throttle_classes
from rest_framework.permissions import IsAuthenticated

from ..auth.Permissions import ReadPerms, DownloadPerms, default_checks
from ..auth.throttle import defaultAuthUserThrottle
from ..constants import API_BASE_URL
from ..core.helpers import get_attr
from ..models import UserZIP, File
from ..core.decorators import check_bulk_permissions, extract_items_from_ids_annotated


@api_view(['POST'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ReadPerms & DownloadPerms])
@extract_items_from_ids_annotated(file_values=File.STANDARD_VALUES, file_annotate=File.LOCK_FROM_ANNOTATE)
@check_bulk_permissions(default_checks)
def create_zip_model(request, items):
    user_zip = UserZIP.objects.create(owner=request.user)

    file_relations = []
    folder_relations = []

    # Get the through tables
    file_through = UserZIP.files.through
    folder_through = UserZIP.folders.through

    for item in items:
        item_id = get_attr(item, 'id')

        if get_attr(item, 'is_dir', True):
            folder_relations.append(folder_through(userzip_id=user_zip.pk, folder_id=item_id))
        else:
            file_relations.append(file_through(userzip_id=user_zip.pk, file_id=item_id))

    if file_relations:
        file_through.objects.bulk_create(file_relations, ignore_conflicts=True)
    if folder_relations:
        folder_through.objects.bulk_create(folder_relations, ignore_conflicts=True)

    return JsonResponse({"download_url": f"{API_BASE_URL}/zip/{user_zip.token}"}, status=200)
