import ipaddress

from django.contrib.auth.models import User
from django.http import JsonResponse, HttpResponse
from rest_framework.decorators import api_view, throttle_classes, permission_classes
from rest_framework.permissions import AllowAny

from website.auth.Permissions import AllowedIP
from website.auth.throttle import defaultAuthUserThrottle
from website.core.helpers import get_ip
from website.core.media.stream.sources.FragmentByteSource import EncryptedFragmentedDiscordByteSource
from website.core.media.utils import build_streaming_response
from website.discord.Discord import discord
from website.models import File


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([AllowAny & AllowedIP])
def get_discord_state(request, user_id):
    ip, _ = get_ip(request)
    ip_obj = ipaddress.ip_address(ip)
    if not ip_obj.is_private:
        return HttpResponse(status=404)

    user = User.objects.get(id=user_id)
    state = discord.get_user_state(user)
    return JsonResponse(state.to_dict(), safe=False)


FILE_IDS_BY_ENCRYPTION = {
    "aes": "h4medRyz5mBrvBJH8B4qfC",
    "chacha": "fzLDRD4R6djoavmohNNZkh",
    "null": "Z3hkFJEERNBfdt6Ygyepdd",
}

@api_view(['GET', 'HEAD'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([AllowAny & AllowedIP])
def stream_file_test(request, encryption):
    file_id = FILE_IDS_BY_ENCRYPTION.get(encryption)
    if file_id is None:
        return JsonResponse({"error": "Invalid encryption type"}, status=400)

    file_obj = File.objects.get(id=file_id)

    if request.method == 'HEAD':
        response = HttpResponse()
        response["Content-Length"] = file_obj.size
        return response

    is_inline = request.GET.get("inline", False)
    fragments = file_obj.fragments.all().order_by("sequence")

    source = EncryptedFragmentedDiscordByteSource(file_obj=file_obj, fragments=fragments)

    user = file_obj.owner  # do not remove this line
    response = build_streaming_response(request=request, byte_source=source, filename=file_obj.name, inline=is_inline, etag=str(hash(file_obj.last_modified_at)))
    return response


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([AllowAny])
def your_ip(request):
    ip, from_nginx = get_ip(request)
    return JsonResponse({"ip": ip, "nginx": from_nginx})
