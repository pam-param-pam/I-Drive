from django.http import HttpResponse, JsonResponse
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated

from website.auth.permissions import (
    PrincipalFactory, ResourceContextResolver, ResourceRef, ResourceRole, ResourceType,
    extract_resource_credentials,
)
from website.auth.throttle import defaultAuthUserThrottle
from website.core.helpers import extract_key
from website.services.file_service import FileService
from website.services.thumbnail_service import ThumbnailService


def _inputs(request):
    return PrincipalFactory.from_authenticated_request(request), extract_resource_credentials(request)


@api_view(["POST"])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated])
def create_file_view(request):
    principal, credentials = _inputs(request)
    files = FileService.create_files(principal, extract_key(request.data, "files"), credentials)
    contexts = ResourceContextResolver().resolve_many(
        (ResourceRef(ResourceType.FILE, file.id, ResourceRole.TARGET) for file in files), principal.user_id,
    )
    lock_from_by_file = {
        context.resource_id: context.effective_lock_policy_id
        for context in contexts
    }
    return JsonResponse([
        {
            "frontend_id": file.frontend_id,
            "file_id": file.id,
            "parent_id": file.parent_id,
            "name": file.name,
            "type": file.type,
            "encryption_method": file.encryption_method,
            "lockFrom": lock_from_by_file[str(file.id)],
        }
        for file in files
    ], safe=False, status=200)


@api_view(["PATCH"])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated])
def edit_file_view(request, file_id):
    principal, credentials = _inputs(request)
    FileService.replace_content(principal, file_id, extract_key(request.data, "file_data"), credentials)
    return HttpResponse(status=204)


@api_view(["POST"])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated])
def create_or_edit_thumbnail_view(request, file_id):
    principal, credentials = _inputs(request)
    ThumbnailService.replace(principal, file_id, request.data, credentials)
    return HttpResponse(status=204)
