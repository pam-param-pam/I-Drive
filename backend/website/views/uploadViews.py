from django.http import JsonResponse, HttpResponse
from rest_framework.decorators import api_view, throttle_classes, permission_classes
from rest_framework.permissions import IsAuthenticated

from website.auth.Permissions import CreatePerms, ModifyPerms, default_checks
from website.auth.throttle import defaultAuthUserThrottle
from website.core.decorators import extract_file, check_resource_permissions
from website.core.helpers import extract_key
from website.core.http.utils import extract_resource_credentials
from website.services import file_service, thumbnail_service


@api_view(['POST'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & CreatePerms])
def create_file_view(request):
    files_data = extract_key(request.data, "files")

    file_objs = file_service.file_service.create_files(
        request.user,
        files_data,
        extract_resource_credentials(request),
    )

    response_json = []
    for file in file_objs:
        file_response_dict = {
            "frontend_id": file.frontend_id,
            "file_id": file.id,
            "parent_id": file.parent.id,
            "name": file.name,
            "type": file.type,
            "encryption_method": file.encryption_method,
            "lockFrom": file.lockFrom.id if file.lockFrom else None
        }
        response_json.append(file_response_dict)

    return JsonResponse(response_json, safe=False, status=200)


@api_view(['PATCH'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & ModifyPerms])
@extract_file()
@check_resource_permissions(default_checks, resource_key="file_obj")
def edit_file_view(request, file_obj):
    file_data = extract_key(request.data, "file_data")
    file_service.file_service.edit_file(
        request.user,
        file_obj,
        file_data,
        credentials=extract_resource_credentials(request),
    )
    return HttpResponse(status=204)


@api_view(['POST'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & CreatePerms & ModifyPerms])
@extract_file()
@check_resource_permissions(default_checks, resource_key="file_obj")
def create_or_edit_thumbnail_view(request, file_obj):
    thumbnail_service.thumbnail_service.replace(
        request.user,
        str(file_obj.id),
        request.data,
        credentials=extract_resource_credentials(request),
    )
    return HttpResponse(status=204)
