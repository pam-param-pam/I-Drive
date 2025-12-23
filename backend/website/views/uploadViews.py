from django.http import JsonResponse, HttpResponse
from rest_framework.decorators import api_view, throttle_classes, permission_classes
from rest_framework.permissions import IsAuthenticated

from ..auth.Permissions import CreatePerms, default_checks, ModifyPerms
from ..auth.throttle import defaultAuthUserThrottle
from ..core.decorators import extract_file, check_resource_permissions
from ..services import create_file_service


@api_view(['POST'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & CreatePerms])
def create_file_view(request):
    files_data = request.data['files']
    # return HttpResponse(status=500)
    file_objs = create_file_service.create_files(request, request.user, files_data)

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
    file_data = request.data['file_data']
    create_file_service.edit_file(request, request.user, file_obj, file_data)
    return HttpResponse(status=204)


@api_view(['POST'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & CreatePerms])
@extract_file()
@check_resource_permissions(default_checks, resource_key="file_obj")
def create_or_edit_thumbnail_view(request, file_obj):
    create_file_service.create_or_edit_thumbnail(request, request.user, file_obj, request.data)
    return HttpResponse(status=204)


@api_view(['POST'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([IsAuthenticated & CreatePerms])
def create_linker(request):
    create_file_service.create_linker(request.user, request.data)
    return HttpResponse(status=204)
