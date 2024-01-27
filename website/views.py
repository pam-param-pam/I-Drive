import base64
import os
import time
from datetime import datetime, timedelta
from wsgiref.util import FileWrapper

import m3u8
import requests
import shortuuid
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.http import HttpResponse, StreamingHttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import cache_page
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from rest_framework.decorators import permission_classes, api_view, throttle_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.throttling import UserRateThrottle

from website.decorators import view_cleanup
from website.forms import UploadFileForm
from website.models import File, Fragment, Folder, UserPerms, UserSettings, ShareableLink
from website.tasks import process_download, handle_uploaded_file, delete_file_task, delete_folder_task
from website.utilities.Discord import discord
from website.utilities.other import create_temp_request_dir, create_temp_file_dir, build_folder_tree, \
    build_folder_content, create_file_dict, build_response, get_folder_path, create_share_dict, get_shared_folder, \
    create_folder_dict

MAX_MB = 25
MAX_STREAM_MB = 23
DELAY_TIME = 0


# TODO return only if ready=true
# TODO user_id to user lol

@csrf_exempt
@api_view(['GET', 'POST'])  # TODO maybe change it later? when removing form idk
# @permission_classes([IsAuthenticated])
def upload_file(request):
    time.sleep(DELAY_TIME)

    # request.upload_handlers.insert(0, ProgressBarUploadHandler(
    #    request))  # TODO tak z lekka nie działa ale moze to dlatego ze lokalna siec? nwm

    return _upload_file(request)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@throttle_classes([UserRateThrottle])
def index(request):
    time.sleep(DELAY_TIME)

    return HttpResponse(f"hello {request.user}")


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download(request, file):
    time.sleep(DELAY_TIME)

    try:
        file_obj = File.objects.get(id=file)
    except (File.DoesNotExist, ValidationError):

        return HttpResponse(f"doesn't exist", status=404)

    if request.user != file_obj.owner:
        return HttpResponse(f"unauthorized", status=403)

    if file_obj.streamable:
        return HttpResponse(f"This file is not downloadable on this endpoint, use m3u8 file", status=404)
    if not file_obj.ready:
        return HttpResponse(f"This file is not uploaded yet", status=404)

    # checking if the file is already downloaded
    file_path = os.path.join("temp", "downloads",
                             str(file_obj.id), file_obj.name)  # temp/downloads/file_id/name.extension
    if os.path.isfile(file_path):
        chunk_size = 8192
        response = StreamingHttpResponse(
            FileWrapper(
                open(file_path, "rb"),
                chunk_size,
            ),
            content_type='application/force-download',
        )
        response['Content-Disposition'] = f'attachment; filename={file_obj.name}'
        response['Content-Length'] = os.path.getsize(file_path)
        return response

    process_download.delay(request.user.id, request.request_id, file_obj.id)
    return JsonResponse(build_response(request.request_id, "file is being download..."))


@csrf_protect
def _upload_file(request):
    if request.method == "POST":
        form = UploadFileForm(request.POST, request.FILES)

        if form.is_valid():
            folder_id = form.data["folder_id"]
            if not Folder.objects.filter(id=folder_id).exists():
                return HttpResponse(f"doesn't exist", status=404)

            file = request.FILES["file"]
            request_dir = create_temp_request_dir(request.request_id)  # creating /temp/<int>/
            file_id = shortuuid.uuid()
            file_dir = create_temp_file_dir(request_dir, file_id)  # creating /temp/<int>/file_id/
            with open(os.path.join(file_dir, file.name),
                      "wb+") as destination:  # saving in /temp/<int>/file_id/filename
                for chunk in file.chunks():
                    destination.write(chunk)

            handle_uploaded_file.delay(request.user.id, request.request_id, file_id, request_dir, file_dir, file.name,
                                       file.size, folder_id)

            return JsonResponse(build_response(request.request_id, "file is being uploaded..."), status=200)

    else:
        form = UploadFileForm()
    return render(request, "upload.html", {"form": form})


@api_view(['GET'])
# @permission_classes([IsAuthenticated])
@view_cleanup
def stream_key(request, file_id):
    time.sleep(DELAY_TIME)

    try:
        file_obj = File.objects.get(id=file_id)
    except (File.DoesNotExist, ValidationError):

        return HttpResponse(f"doesn't exist", status=404)
    if not file_obj.ready:
        return HttpResponse(f"This file is not uploaded yet", status=404)
    # if request.user != file_obj.owner:
    #   return HttpResponse(f"unauthorized", status=403)
    if not file_obj.streamable:
        return HttpResponse(f"This file is not streamable!", status=404)

    request_dir = create_temp_request_dir(request.request_id)
    file_dir = create_temp_file_dir(request_dir, file_obj.id)

    key_file_path = os.path.join(file_dir, "enc.key")

    with open(key_file_path, 'wb+') as file:
        file.write(file_obj.key)
        # Move the file cursor to the beginning before reading
        file.seek(0)  # vevy important
        file_content = file.read()

    response = HttpResponse(file_content, content_type='application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="key.enc"'
    return response


def process_m3u8(request_id, file_obj):
    file_url = discord.get_file_url(file_obj.m3u8_message_id)

    request_dir = create_temp_request_dir(request_id)
    file_dir = create_temp_file_dir(request_dir, file_obj.id)

    response = requests.get(file_url, stream=True)

    m3u8_file_path = os.path.join(file_dir, "manifest.m3u8")
    with open(m3u8_file_path, 'wb') as file:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                file.write(chunk)

    playlist = m3u8.load(m3u8_file_path)
    new_key = m3u8.Key(method="AES-128", base_uri=f"http://127.0.0.1:8000/api/stream_key/{file_obj.id}",
                       # TODO change it back later
                       uri=f"https://pamparampam.dev/api/stream_key/{file_obj.id}")
    new_key = m3u8.Key(method="AES-128", base_uri=f"http://127.0.0.1:8000/api/stream_key/{file_obj.id}",
                       # TODO change it back later
                       uri=f"http://127.0.0.1:8000/api/stream_key/{file_obj.id}")
    fragments = Fragment.objects.filter(file_id=file_obj).order_by('sequence')
    for fragment, segment in zip(fragments, playlist.segments.by_key(playlist.keys[-1])):
        url = f"http://127.0.0.1:8000/api/stream/fragment/{fragment.id}"
        segment.uri = url
        segment.key = new_key

    playlist.keys[-1] = new_key

    playlist.dump(m3u8_file_path)
    with open(m3u8_file_path, 'rb') as file:
        file_content = file.read()

    return file_content


def test(request):
    return HttpResponse(f"yupi", status=200)


@api_view(['GET'])
# @permission_classes([IsAuthenticated])
@view_cleanup
def get_m3u8(request, file_id):
    time.sleep(DELAY_TIME)

    try:
        file_obj = File.objects.get(id=file_id)
    except (File.DoesNotExist, ValidationError):
        return HttpResponse(f"doesn't exist", status=404)
    if not file_obj.ready:
        return HttpResponse(f"This file is not uploaded yet", status=404)

    # if request.user != file_obj.owner:
    #   return HttpResponse(f"unauthorized", status=403)
    if not file_obj.streamable:
        return HttpResponse(f"This file is not streamable!", status=404)

    file_content = process_m3u8(request.request_id, file_obj)

    response = HttpResponse(file_content, content_type='application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="manifest.m3u8"'

    return response


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([UserRateThrottle])
def create_folder(request):
    time.sleep(DELAY_TIME)
    try:
        name = request.data['name']

        parent = Folder.objects.get(id=request.data['parent_id'])

        folder_obj = Folder(
            name=name,
            parent=parent,
            owner=request.user,
        )
        folder_obj.save()
        return JsonResponse(create_folder_dict(folder_obj))

    except Folder.DoesNotExist:
        return HttpResponse(f"bad request: parent is not correct", status=404)
    except ValidationError as e:
        return HttpResponse(f"bad request: {str(e)}", status=404)

    except KeyError:
        return HttpResponse(f"bad request", status=404)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([UserRateThrottle])
def move(request):
    time.sleep(DELAY_TIME)

    try:
        obj_id = request.data['id']
        parent_id = request.data['parent_id']

        user = request.user

        obj = Folder.objects.get(id=obj_id)

        parent = Folder.objects.get(id=parent_id)

        if parent == obj.parent or parent == obj:
            return HttpResponse(f"Bad request: folders are the same", status=400)

        if obj.owner != user or parent.owner != user:
            return HttpResponse("Unauthorized", status=403)

        obj.parent = parent
        obj.save()
        item_type = "File" if isinstance(obj, File) else "Folder"

        return HttpResponse(f"{item_type} moved {request.request_id} to {parent.name}", status=200)

    except (ValidationError, Folder.DoesNotExist):
        return HttpResponse("Bad request: item id or parent id are not correct", status=404)

    except KeyError:
        return HttpResponse("Bad request: Missing required parameters", status=400)


@api_view(['POST'])  # this should be a post or delete imo
@permission_classes([IsAuthenticated])
@throttle_classes([UserRateThrottle])
def delete(request):
    time.sleep(DELAY_TIME)

    try:
        user = request.user
        items = []
        ids = request.data['ids']
        if not isinstance(ids, list):
            return HttpResponse("Bad request: 'ids' should be a list", status=400)
        for item_id in ids:
            try:
                item = Folder.objects.get(id=item_id)
            except Folder.DoesNotExist:
                try:
                    item = File.objects.get(id=item_id)
                except File.DoesNotExist:
                    return HttpResponse(
                        f"Couldn't find item with ID:\n{item_id}\n(probably already deleted by other instance)",
                        status=404)

            if item.owner != user:  # owner perms needed
                return HttpResponse(f"Unauthorized!", status=403)

            items.append(item)

        for item in items:
            if isinstance(item, File):
                delete_file_task.delay(user.id, request.request_id, item.id)
            elif isinstance(item, Folder):
                delete_folder_task.delay(user.id, request.request_id, item.id)
        return JsonResponse(build_response(request.request_id, f"{len(items)} items are being deleted..."))

    except ValidationError:
        return HttpResponse(f"At least one ID is incorrect", status=404)
    except KeyError:
        return HttpResponse(f"Bad request", status=400)


@api_view(['POST'])  # this should be a post or delete imo
@permission_classes([IsAuthenticated])
@throttle_classes([UserRateThrottle])
def rename(request):
    time.sleep(DELAY_TIME)

    try:
        obj_id = request.data['id']
        new_name = request.data['new_name']

        try:
            obj = Folder.objects.get(id=obj_id)
        except Folder.DoesNotExist:
            try:
                obj = File.objects.get(id=obj_id)
            except File.DoesNotExist:
                return HttpResponse(f"doesn't exist", status=404)

        if obj.owner != request.user:  # todo fix perms
            return HttpResponse(f"unauthorized", status=403)

        obj.name = new_name
        obj.save()

        return HttpResponse(f"Changed name to {new_name}", status=200)
    except ValidationError:
        return HttpResponse(f"bad request", status=400)
    except KeyError:
        return HttpResponse(f"bad request", status=404)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@throttle_classes([UserRateThrottle])
def get_folder_tree(request):
    time.sleep(DELAY_TIME)

    try:

        user_folders = Folder.objects.filter(owner=request.user)  # todo
        folder_structure = build_folder_tree(user_folders)
        return JsonResponse(folder_structure[0])

    except (Folder.DoesNotExist, ValidationError):
        return HttpResponse(f"doesn't exist", status=404)
    except Folder.MultipleObjectsReturned:
        return HttpResponse(f"Database is malformed WHOOPS", status=404)
    except KeyError:
        return HttpResponse(f"bad request", status=404)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@throttle_classes([UserRateThrottle])
def get_folder(request, folder_id):
    time.sleep(DELAY_TIME)

    try:

        folder_obj = Folder.objects.get(id=folder_id)
        if folder_obj.owner != request.user:  # todo fix perms
            return HttpResponse(f"unauthorized", status=403)
        folder_content = build_folder_content(folder_obj)

        return JsonResponse(folder_content)

    except (Folder.DoesNotExist, ValidationError):
        return HttpResponse(f"doesn't exist", status=404)
    except KeyError:
        return HttpResponse(f"bad request", status=404)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@throttle_classes([UserRateThrottle])
def get_file(request, file_id):
    time.sleep(DELAY_TIME)
    try:
        file_obj = File.objects.get(id=file_id)
        if not file_obj.ready:
            return HttpResponse(f"file is not ready yet", status=404)
        if file_obj.owner != request.user:
            return HttpResponse(f"unauthorized", status=403)
        file_content = create_file_dict(file_obj)

        return JsonResponse(file_content)

    except (File.DoesNotExist, ValidationError):
        return HttpResponse(f"doesn't exist", status=404)
    except KeyError:
        return HttpResponse(f"bad request", status=404)


"""
@api_view(['GET'])
@permission_classes([IsAuthenticated])
@throttle_classes([UserRateThrottle])
def search(request, query):
    time.sleep(DELAY_TIME)

    try:
        filtered_files = File.objects.filter(Q(name__icontains=query) | Q(parent__name__icontains=query),
                                             owner=request.user)  # todo fix id
        files = create_files_dict(filtered_files)
        return JsonResponse(files, safe=False)

    except (Folder.DoesNotExist, ValidationError):
        return HttpResponse(f"doesn't exist", status=404)
    except KeyError:
        return HttpResponse(f"bad request", status=404)
"""


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@throttle_classes([UserRateThrottle])
def get_usage(request):
    time.sleep(DELAY_TIME)

    try:
        used_size = 0
        used_encrypted_size = 0
        files = File.objects.filter(owner=request.user)
        for file in files:
            used_encrypted_size += file.encrypted_size
            used_size += file.size
        return JsonResponse({"total": used_encrypted_size, "used": used_size}, status=200)

    except (Folder.DoesNotExist, ValidationError):
        return HttpResponse(f"doesn't exist", status=404)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@throttle_classes([UserRateThrottle])
def get_root(request):
    time.sleep(DELAY_TIME)

    try:
        folder_obj = Folder.objects.get(parent=None, owner=request.user)
        folder_content = build_folder_content(folder_obj)

        return JsonResponse(folder_content, safe=False)
    except (Folder.DoesNotExist, ValidationError):
        return HttpResponse(f"doesn't exist", status=404)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@throttle_classes([UserRateThrottle])
def get_breadcrumbs(request, folder_id):
    time.sleep(DELAY_TIME)
    try:

        Folder.objects.get(id=folder_id)  # check if folder exists

        user_folders = Folder.objects.filter(owner=request.user)
        folder_structure = build_folder_tree(user_folders)

        folder_path = get_folder_path(folder_id, folder_structure[0])
        for folder in folder_path:
            folder.pop("children")  # Remove the "children" key as it's not needed
        return JsonResponse(folder_path, safe=False)
    except (Folder.DoesNotExist, ValidationError):
        return HttpResponse(f"doesn't exist", status=404)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@throttle_classes([UserRateThrottle])
def users_me(request):
    time.sleep(DELAY_TIME)

    user = request.user
    perms = UserPerms.objects.get(user=user)
    settings = UserSettings.objects.get(user=user)
    root = Folder.objects.get(owner=request.user, parent=None)
    response = {"user": {"id": user.id, "name": user.username, "root": root.id},
                "perms": {"admin": perms.admin, "execute": perms.execute, "create": perms.create,
                          "rename": perms.rename,
                          "modify": perms.modify, "delete": perms.delete, "share": perms.share,
                          "download": perms.download},
                "settings": {"locale": settings.locale, "hideHiddenFolders": settings.hide_hidden_folders,
                             "dateFormat": settings.date_format,
                             "viewMode": settings.view_mode, "sortingBy": settings.sorting_by,
                             "sortByAsc": settings.sort_by_asc, "subfoldersInShares": settings.subfolders_in_shares}}

    return JsonResponse(response, safe=False, status=200)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([UserRateThrottle])
def update_settings(request):
    time.sleep(DELAY_TIME)

    locale = request.data.get('locale')
    hideHiddenFolders = request.data.get('hideHiddenFolders')
    dateFormat = request.data.get('dateFormat')
    viewMode = request.data.get('viewMode')
    sortingBy = request.data.get('sortingBy')
    sortByAsc = request.data.get('sortByAsc')
    subfoldersInShares = request.data.get('subfoldersInShares')

    settings = UserSettings.objects.get(user=request.user)
    if locale in ["pl", "en"]:
        settings.locale = locale
    if isinstance(dateFormat, bool):
        settings.date_format = dateFormat
    if isinstance(hideHiddenFolders, bool):
        settings.hide_hidden_folders = hideHiddenFolders
    if viewMode in ["list", "mosaic", "mosaic gallery"]:
        settings.view_mode = viewMode
    if sortingBy in ["name", "size", "created"]:
        settings.sorting_by = sortingBy
    if isinstance(sortByAsc, bool):
        settings.sort_by_asc = sortByAsc
    if isinstance(subfoldersInShares, bool):
        settings.subfolders_in_shares = subfoldersInShares
    settings.save()
    return HttpResponse(status=200)


@api_view(['GET'])
# @permission_classes([IsAuthenticated])
@throttle_classes([UserRateThrottle])
def get_shares(request):
    time.sleep(DELAY_TIME)

    user = request.user
    user.id = 1
    shares = ShareableLink.objects.filter(owner_id=1)
    items = []

    for share in shares:
        if not share.is_expired():
            item = create_share_dict(share)

            items.append(item)

    return JsonResponse(items, status=200, safe=False)


@api_view(['POST'])
# @permission_classes([IsAuthenticated])
@throttle_classes([UserRateThrottle])
def create_share(request):
    time.sleep(DELAY_TIME)

    try:
        item_id = request.data['id']
        value = abs(int(request.data['value']))

        unit = request.data['unit']
        password = request.data.get('password')

        current_time = datetime.now()
        try:
            obj = Folder.objects.get(id=item_id)
        except Folder.DoesNotExist:
            try:
                obj = File.objects.get(id=item_id)
            except File.DoesNotExist:
                return HttpResponse(f"doesn't exist", status=404)

        if obj.owner != request.user:
            return HttpResponse(f"unauthorized", status=403)

        if unit == 'minutes':
            expiration_time = current_time + timedelta(minutes=value)
        elif unit == 'hours':
            expiration_time = current_time + timedelta(hours=value)
        elif unit == 'days':
            expiration_time = current_time + timedelta(days=value)
        else:
            return HttpResponse("Invalid unit. Supported units are 'minutes', 'hours', and 'days'.", status=400)

        share = ShareableLink.objects.create(
            expiration_time=expiration_time,
            owner_id=1,
            content_type=ContentType.objects.get_for_model(obj),
            object_id=obj.id
        )
        if password:
            share.password = password

        share.save()
        item = create_share_dict(share)

        return JsonResponse(item, status=200, safe=False)

    except ValidationError:
        return HttpResponse(f"doesn't exist", status=404)
    except (ValueError, KeyError):
        return HttpResponse(f"bad request", status=404)


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([UserRateThrottle])
def view_share(request, token):
    time.sleep(DELAY_TIME)

    try:
        share = ShareableLink.objects.get(token=token)
        if share.is_expired():
            return HttpResponse(f"Share is expired :(", status=404)

        try:
            obj = Folder.objects.get(id=share.object_id)
            settings = UserSettings.objects.get(user=obj.owner)

            return JsonResponse(get_shared_folder(obj, settings.subfolders_in_shares), status=200)
        except Folder.DoesNotExist:
            obj = File.objects.get(id=share.object_id)
            return JsonResponse(create_file_dict(obj), status=200)

    except ShareableLink.DoesNotExist:
        return HttpResponse(f"doesn't exist", status=404)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@throttle_classes([UserRateThrottle])
def stream_fragment(request, fragment_id):
    try:
        fragment = Fragment.objects.get(id=fragment_id)

        # if fragment.file.owner != request.user:
        #   return HttpResponse(f"unauthorized", status=403)

        url = discord.get_file_url(fragment.message_id)
        response = requests.get(url, stream=True)

        # Set the appropriate content type for your response (e.g., video/MP2T for a TS file)
        content_type = "video/MP2T"

        # Set content disposition if you want the browser to treat it as an attachment
        # response['Content-Disposition'] = 'attachment; filename="your_filename.ts"'

        # Create a streaming response with the remote content
        streaming_response = StreamingHttpResponse(
            (chunk for chunk in response.iter_content(chunk_size=8192)),
            content_type=content_type,
        )

        return streaming_response

    except Fragment.DoesNotExist:
        return HttpResponse(f"doesn't exist", status=404)


@api_view(['GET'])
@throttle_classes([UserRateThrottle])
# @permission_classes([IsAuthenticated])
@cache_page(60 * 60 * 2)  # Cache for 2 hours (time in seconds)
#@cache_page(60 * 60 * 60 * 60)  # Cache for a long time lol
def get_fragment_urls(request, file_id):
    try:

        # if file.owner != request.user:
        #    return HttpResponse(f"unauthorized", status=403)
        fileObj = File.objects.get(id=file_id)
        if not fileObj.ready:
            return HttpResponse(f"file not ready", status=404)

        serialized_key = base64.urlsafe_b64encode(fileObj.key).decode()

        fragments = Fragment.objects.filter(file=fileObj).order_by('sequence')
        urls = []

        for fragment in fragments:
            url = discord.get_file_url(fragment.message_id)
            urls.append({"url": url, "size": fragment.size, "encrypted_size": fragment.encrypted_size})
        json_string = {"key": serialized_key, "total_size": fileObj.size, "fragment_urls": urls, "name": fileObj.name}

        return JsonResponse(json_string, safe=False, status=200)

    except File.DoesNotExist:
        return HttpResponse("Doesn't exist", status=404)
