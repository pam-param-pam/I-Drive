from django.http import JsonResponse
from rest_framework.decorators import permission_classes, api_view, throttle_classes
from rest_framework.permissions import IsAuthenticated

from ..models import Folder, UserZIP
from ..utilities.Permissions import DownloadPerms
from ..utilities.constants import API_BASE_URL
from ..utilities.decorators import handle_common_errors
from ..utilities.errors import BadRequestError, MissingOrIncorrectResourcePasswordError
from ..utilities.other import check_resource_perms, get_resource
from ..utilities.throttle import MyUserRateThrottle


@api_view(['POST'])
@throttle_classes([MyUserRateThrottle])
@permission_classes([IsAuthenticated & DownloadPerms])
@handle_common_errors
def create_zip_model(request):
    ids = request.data['ids']

    if not isinstance(ids, list):
        raise BadRequestError("'ids' must be a list.")
    if len(ids) == 0:
        raise BadRequestError("'ids' length cannot be 0.")
    user_zip = UserZIP.objects.create(owner=request.user)

    required_folder_passwords = []
    for item_id in ids:

        item = get_resource(item_id)

        # handle multiple folder passwords
        try:
            check_resource_perms(request, item, checkTrash=True)
        except MissingOrIncorrectResourcePasswordError:
            # check if folder id is in list of tuples
            if item.lockFrom and item.lockFrom not in required_folder_passwords:
                required_folder_passwords.append(item.lockFrom)

        if isinstance(item, Folder):
            # Checking if the folder is already present in the zip model
            if user_zip.folders.filter(id=item.id).exists():
                raise BadRequestError(f"Folder({item.name}) is already in the ZIP")

            # goofy checking if folder isn't a subfolder of a folder already in zip
            re_item = item
            while re_item:
                if user_zip.folders.filter(id=re_item.id).exists():
                    raise BadRequestError(f"Folder({re_item.name}) is already a subfolder in the ZIP(1)")
                re_item = re_item.parent

            for re_folder in user_zip.folders.all():
                while re_folder:
                    if re_folder == item:
                        raise BadRequestError(f"Folder({re_folder.name}) is already a subfolder in the ZIP(2)")
                    re_folder = re_folder.parent

            user_zip.folders.add(item)

        else:
            # Checking if the folder is already present in the zip model
            if user_zip.files.filter(id=item.id).exists():
                raise BadRequestError(f"File({item.name}) is already in the ZIP")

            user_zip.files.add(item)
    if len(required_folder_passwords) > 0:
        raise MissingOrIncorrectResourcePasswordError(required_folder_passwords)
    user_zip.save()
    return JsonResponse({"download_url": f"{API_BASE_URL}/zip/{user_zip.token}"}, status=200)
