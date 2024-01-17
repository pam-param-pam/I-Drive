import json
import os
import time
import uuid
from json import JSONDecodeError
from wsgiref.util import FileWrapper

import m3u8
import requests
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import HttpResponse, StreamingHttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from rest_framework.decorators import permission_classes, api_view, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle

from website.Handlers import ProgressBarUploadHandler
from website.decorators import view_cleanup
from website.forms import UploadFileForm
from website.models import File, Fragment, Folder, UserPerms, UserSettings
from website.tasks import process_download, handle_uploaded_file, delete_file_task, test_task, delete_folder_task
from website.utilities.Discord import discord
from website.utilities.other import create_temp_request_dir, create_temp_file_dir, build_folder_tree, \
    build_folder_content, create_files_dict, build_response, get_folder_path

MAX_MB = 25
MAX_STREAM_MB = 23


# TODO return only if ready=true
# TODO user_id to user lol

@csrf_exempt
@api_view(['GET', 'POST'])  # TODO maybe change it later? when removing form idk
# @permission_classes([IsAuthenticated])
def upload_file(request):
    # request.upload_handlers.insert(0, ProgressBarUploadHandler(
    #    request))  # TODO tak z lekka nie działa ale moze to dlatego ze lokalna siec? nwm

    return _upload_file(request)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@throttle_classes([UserRateThrottle])
def index(request):
    return HttpResponse(f"hello {request.user}")


@api_view(['GET'])
# @permission_classes([IsAuthenticated])
def download(request, file):
    try:
        file_obj = File.objects.get(id=file)
    except (File.DoesNotExist, ValidationError):

        return HttpResponse(f"doesn't exist", status=404)

    # owner, maintainer or viewer perms needed
    if request.user.id not in (
            file_obj.owner.id,
            getattr(file_obj.maintainer, 'id', None),
            getattr(file_obj.viewer, 'id', None)
    ):
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
            file_id = uuid.uuid4()
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
    file_id = file_id.replace(".key", "")
    try:
        file_obj = File.objects.get(id=file_id)
    except (File.DoesNotExist, ValidationError):

        return HttpResponse(f"doesn't exist", status=404)
    if not file_obj.ready:
        return HttpResponse(f"This file is not uploaded yet", status=404)
    # owner, maintainer or viewer perms needed
    if request.user.id not in (
            file_obj.owner.id,
            getattr(file_obj.maintainer, 'id', None),
            getattr(file_obj.viewer, 'id', None)
    ):
        return HttpResponse(f"unauthorized", status=403)
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
    new_key = m3u8.Key(method="AES-128", base_uri=f"http://127.0.0.1:8000/api/stream_key/{file_obj.id}.key",
                       # TODO change it back later
                       uri=f"https://pamparampam.dev/api/stream_key/{file_obj.id}.key")
    new_key = m3u8.Key(method="AES-128", base_uri=f"http://127.0.0.1:8000/api/stream_key/{file_obj.id}.key",
                       # TODO change it back later
                       uri=f"http://127.0.0.1:8000/api/stream_key/{file_obj.id}.key")
    fragments = Fragment.objects.filter(file_id=file_obj).order_by('sequence')
    for fragment, segment in zip(fragments, playlist.segments.by_key(playlist.keys[-1])):
        url = discord.get_file_url(fragment.message_id)
        segment.uri = url
        segment.key = new_key

    playlist.keys[-1] = new_key

    playlist.dump(m3u8_file_path)
    with open(m3u8_file_path, 'rb') as file:
        file_content = file.read()

    return file_content


def test(request):
    test_task.delay()
    return HttpResponse(f"yupi", status=200)


@api_view(['GET'])
# @permission_classes([IsAuthenticated])
@view_cleanup
def get_m3u8(request, file_id):
    file_id = file_id.replace(".m3u8", "")
    try:
        file_obj = File.objects.get(id=file_id)
    except (File.DoesNotExist, ValidationError):
        return HttpResponse(f"doesn't exist", status=404)
    if not file_obj.ready:
        return HttpResponse(f"This file is not uploaded yet", status=404)
    # owner, maintainer or viewer perms needed
    if request.user.id not in (
            file_obj.owner.id,
            getattr(file_obj.maintainer, 'id', None),
            getattr(file_obj.viewer, 'id', None)
    ):
        return HttpResponse(f"unauthorized", status=403)
    if not file_obj.streamable:
        return HttpResponse(f"This file is not streamable!", status=404)

    file_content = process_m3u8(request.request_id, file_obj)

    response = HttpResponse(file_content, content_type='application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="manifest.m3u8"'

    return response


@api_view(['POST'])
# @permission_classes([IsAuthenticated])
def create_folder(request):
    try:
        name = request.data['name']

        parent = Folder.objects.get(id=request.data['parent_id'])

        user = request.user

        user = 1  # todo
        folder_obj = Folder(
            name=name,
            parent=parent,
            owner_id=user,
        )
        folder_obj.save()
        return HttpResponse(f"folder created {request.request_id} id={folder_obj.id}", status=200)

    except (ValidationError, Folder.DoesNotExist):
        return HttpResponse(f"bad request: parent is not correct", status=404)

    except KeyError:
        return HttpResponse(f"bad request", status=404)


@api_view(['POST'])
# @permission_classes([IsAuthenticated])
def movefolder(request):
    try:

        folder = Folder.objects.get(id=request.data['folder_id'])  # folder to be moved

        parent = Folder.objects.get(id=request.data['parent_id'])  # destination folder

        user = request.user

        user = 1  # todo
        if parent == folder.parent or parent == folder:
            return HttpResponse(f"bad request: folders are the same", status=404)

        if folder.owner_id != user or (folder.maintainer_id and folder.maintainer_id != user) or \
                parent.owner_id != user or (parent.maintainer_id and parent.maintainer_id != user):
            return HttpResponse("unauthorized", status=403)

        folder.parent = parent

        folder.save()
        return HttpResponse(f"folder moved {request.request_id} to={parent.name}", status=200)

    except (ValidationError, Folder.DoesNotExist):
        return HttpResponse(f"bad request: folder id or parent id are not correct", status=404)

    except KeyError:
        return HttpResponse(f"bad request", status=404)


@api_view(['POST'])  # not tested lul
# @permission_classes([IsAuthenticated])
def movefile(request):
    try:

        file = Folder.objects.get(id=request.data['file_id'])  # file to be moved

        parent = Folder.objects.get(id=request.data['parent_id'])  # destination folder

        user = request.user

        user = 1  # todo
        if parent == file.parent:  # if old folder and new folder are the same, throw error
            return HttpResponse(f"bad request: folders are the same", status=404)

        if file.owner_id != user or (file.maintainer_id and file.maintainer_id != user) or \
                parent.owner_id != user or (parent.maintainer_id and parent.maintainer_id != user):
            return HttpResponse("unauthorized", status=403)

        file.parent = parent

        file.save()
        return HttpResponse(f"file moved {request.request_id} to={parent.name}", status=200)

    except (ValidationError, Folder.DoesNotExist):
        return HttpResponse(f"bad request: file id or parent id are not correct", status=404)

    except KeyError:
        return HttpResponse(f"bad request", status=404)


@api_view(['POST'])  # this should be a post or delete imo
# @permission_classes([IsAuthenticated])
def delete(request):
    try:
        user = request.user
        user.id = 1  # todo
        obj_id = request.data['id']

        try:
            obj = Folder.objects.get(id=obj_id)
        except Folder.DoesNotExist:
            try:
                obj = File.objects.get(id=obj_id)
            except File.DoesNotExist:
                return HttpResponse(f"doesn't exist", status=404)

        if obj.owner.id != user.id:  # owner perms needed
            return HttpResponse(f"unauthorized", status=403)

        if isinstance(obj, File):
            delete_file_task.delay(user.id, request.request_id, obj.id)
            return JsonResponse(build_response(request.request_id, "file is being deleted..."))
        elif isinstance(obj, Folder):
            delete_folder_task.delay(user.id, request.request_id, obj.id)
            return JsonResponse(build_response(request.request_id, "folder is being deleted..."))

    except ValidationError:
        return HttpResponse(f"doesn't exist", status=404)
    except KeyError:
        return HttpResponse(f"bad request", status=400)


@api_view(['POST'])  # this should be a post or delete imo
# @permission_classes([IsAuthenticated])
def rename(request):
    try:

        user = request.user
        user.id = 1  # todo

        obj_id = request.data['id']
        new_name = request.data['new_name']

        try:
            obj = Folder.objects.get(id=obj_id)
        except Folder.DoesNotExist:
            try:
                obj = File.objects.get(id=obj_id)
            except File.DoesNotExist:
                return HttpResponse(f"doesn't exist", status=404)

        if obj.owner.id != request.user.id:  # todo fix perms
            return HttpResponse(f"unauthorized", status=403)

        obj.name = new_name
        obj.save()

        return HttpResponse(f"Changed name to {new_name}", status=200)
    except ValidationError:
        return HttpResponse(f"bad request", status=400)
    except KeyError:
        return HttpResponse(f"bad request", status=404)


@api_view(['GET'])
# @permission_classes([IsAuthenticated])
def get_folder_tree(request):
    user = request.user

    user.id = 1  # todo
    try:

        user_folders = Folder.objects.filter(owner_id=user.id)  # todo
        folder_structure = build_folder_tree(user_folders)
        return JsonResponse(folder_structure[0])

    except (Folder.DoesNotExist, ValidationError):
        return HttpResponse(f"doesn't exist", status=404)
    except Folder.MultipleObjectsReturned:
        return HttpResponse(f"Database is malformed WHOOPS", status=404)
    except KeyError:
        return HttpResponse(f"bad request", status=404)


@api_view(['GET'])
# @permission_classes([IsAuthenticated])
def get_folder(request, folder_id):
    user = request.user

    user.id = 1  # todo
    try:

        folder_obj = Folder.objects.get(id=folder_id)
        if folder_obj.owner.id != request.user.id:  # todo fix perms
            return HttpResponse(f"unauthorized", status=403)
        folder_content = build_folder_content(folder_obj)

        return JsonResponse(folder_content)

    except (Folder.DoesNotExist, ValidationError):
        return HttpResponse(f"doesn't exist", status=404)
    except KeyError:
        return HttpResponse(f"bad request", status=404)


@api_view(['GET'])
# @permission_classes([IsAuthenticated])
def search(request, query):
    user = request.user

    user.id = 1  # todo
    try:
        filtered_files = File.objects.filter(Q(name__icontains=query) | Q(parent__name__icontains=query),
                                             owner_id=user.id)  # todo fix id
        files = create_files_dict(filtered_files)
        return JsonResponse(files, safe=False)

    except (Folder.DoesNotExist, ValidationError):
        return HttpResponse(f"doesn't exist", status=404)
    except KeyError:
        return HttpResponse(f"bad request", status=404)


@api_view(['GET'])
# @permission_classes([IsAuthenticated])
def usage(request):
    user = request.user

    user.id = 1  # todo
    try:
        used_size = 0
        used_encrypted_size = 0
        files = File.objects.filter(owner_id=user.id)
        for file in files:
            used_encrypted_size += file.encrypted_size
            used_size += file.size
        return JsonResponse({"total": used_encrypted_size, "used": used_size}, status=200)

    except (Folder.DoesNotExist, ValidationError):
        return HttpResponse(f"doesn't exist", status=404)


@api_view(['GET'])
# @permission_classes([IsAuthenticated])
def get_root(request):
    user = request.user

    user.id = 1  # todo
    try:
        folder_obj = Folder.objects.get(parent=None, owner_id=user.id)
        folder_content = build_folder_content(folder_obj)

        return JsonResponse(folder_content, safe=False)
    except (Folder.DoesNotExist, ValidationError):
        return HttpResponse(f"doesn't exist", status=404)


@api_view(['GET'])
# @permission_classes([IsAuthenticated])
def get_breadcrumbs(request, folder_id):

        user = request.user  # todo
        user.id = 1

        user_folders = Folder.objects.filter(owner_id=user.id)  # todo
        folder_structure = build_folder_tree(user_folders)
        folder_path = get_folder_path(folder_id, folder_structure[0])

        return JsonResponse(folder_path, safe=False)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def users_me(request):
    user = request.user
    user.id = 1  # todo
    perms = UserPerms.objects.get(user_id=user.id)
    settings = UserSettings.objects.get(user_id=user.id)

    response = {"user": {"id": user.id, "name": user.username},
                "perms": {"admin": perms.admin, "execute": perms.execute, "create": perms.create, "rename": perms.rename,
                         "modify": perms.modify, "delete": perms.delete, "share": perms.share,
                         "download": perms.download},
                "settings": {"locale": settings.locale, "hideDotFiles": settings.hide_dotfiles,
                             "dateFormat": settings.date_format, "singleClick": settings.single_click,
                             "viewMode": settings.view_mode, "sortingBy": settings.sorting_by,
                             "sortByAsc": settings.sort_by_asc}}

    return JsonResponse(response, safe=False, status=200)


@api_view(['POST'])
# @permission_classes([IsAuthenticated])
def update_settings(request):
    user = request.user
    user.id = 1  # todo

    locale = request.data.get('locale')
    hideDotFiles = request.data.get('hideDotFiles')
    singleClick = request.data.get('singleClick')
    dateFormat = request.data.get('dateFormat')
    viewMode = request.data.get('viewMode')
    sorting_by = request.data.get('sorting_by')
    sort_by_asc = request.data.get('sort_by_asc')

    settings = UserSettings.objects.get(user_id=user.id)

    if locale in ["pl", "en"]:
        settings.locale = locale
    if isinstance(dateFormat, bool):
        settings.dateFormat = dateFormat
    if isinstance(hideDotFiles, bool):
        settings.hideDotFiles = hideDotFiles
    if isinstance(singleClick, bool):
        settings.singleClick = singleClick
    if viewMode in ["list", "gallery", "mosaic gallery"]:
        settings.viewMode = viewMode
    if sorting_by in ["name", "size", "mosaic gallery"]:
        settings.viewMode = viewMode
    if isinstance(sort_by_asc, bool):
        settings.sort_by_asc = sort_by_asc

    return HttpResponse(status=200)
