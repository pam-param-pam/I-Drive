import ipaddress
import os
import zlib
from dataclasses import dataclass
from datetime import datetime

import requests
import shortuuid
from django.contrib.auth.models import User
from django.http import JsonResponse, HttpResponse
from django.http import StreamingHttpResponse, Http404
from django.utils import timezone
from rest_framework.decorators import api_view, throttle_classes, permission_classes
from rest_framework.permissions import AllowAny

from ..auth.throttle import defaultAuthUserThrottle
from ..core.crypto.Decryptor import Decryptor
from ..core.helpers import get_ip
from ..discord.Discord import discord
from ..queries.selectors import get_file


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([AllowAny])
def get_discord_state(request, user_id):
    ip, _ = get_ip(request)
    ip_obj = ipaddress.ip_address(ip)
    if not ip_obj.is_private:
        return HttpResponse(status=404)

    user = User.objects.get(id=user_id)
    state = discord.get_user_state(user)
    return JsonResponse(state.to_dict(), safe=False)


@api_view(['GET'])
@throttle_classes([defaultAuthUserThrottle])
@permission_classes([AllowAny])
def your_ip(request):
    ip, from_nginx = get_ip(request)

    return JsonResponse({"ip": ip, "nginx": from_nginx})

@dataclass
class ZipEntryFile:
    id: str
    name: str
    size: int
    compressed_size: int
    offset: int
    compression_method: int

    parent_id: str | None = None
    created_at: datetime = None
    last_modified_at: datetime = None

    # optional fields
    crc: int | None = None
    encryption_method: int = 0

    def __post_init__(self):
        if not self.created_at:
            now = timezone.now()
            self.created_at = now
            self.last_modified_at = now

    @property
    def extension(self):
        return os.path.splitext(self.name)[1]

    @property
    def type(self):
        ext = self.extension.lower()
        if ext in [".mp4", ".avi"]:
            return "Video"
        if ext in [".zip"]:
            return "Archive"
        if ext in [".vue", ".py", ".js"]:
            return "Code"
        return "text"

    def to_dict(self, base_url=None):
        data = {
            "isDir": False,
            "id": self.id,
            "name": os.path.basename(self.name),
            "parent_id": self.parent_id,
            "size": self.size,
            "type": self.type,
            "extension": self.extension,
            "created": self.created_at.isoformat(),
            "last_modified": self.last_modified_at.isoformat(),
            "isLocked": False,
            "encryption_method": self.encryption_method,
        }

        if self.crc:
            data["crc"] = self.crc

        if base_url:
            data["download_url"] = f"{base_url}/{self.id}/stream"

        return data

def build_zip_tree(entries):
    tree = {}

    for e in entries:
        parts = e["name"].split("/")
        current = tree

        for part in parts[:-1]:
            current = current.setdefault(part, {"__children__": {}})["__children__"]

        current.setdefault("__files__", []).append(e)

    return tree



def folder_to_dict(name, subtree, parent_id=None):
    folder_id = shortuuid.uuid()

    children = []

    # subfolders
    for sub_name, sub_tree in subtree.items():
        if sub_name.startswith("__"):
            continue
        children.append(folder_to_dict(sub_name, sub_tree["__children__"], folder_id))

    # files
    for f in subtree.get("__files__", []):
        zip_file = ZipEntryFile(
            id=shortuuid.uuid(),
            name=f["name"],
            size=f["uncompressedSize"],
            compressed_size=f["compressedSize"],
            offset=f["offset"],
            compression_method=f["compressionMethod"],
            parent_id=folder_id,
        )
        children.append(zip_file.to_dict())

    return {
        "isDir": True,
        "id": folder_id,
        "name": name,
        "parent_id": parent_id,
        "created": timezone.now().isoformat(),
        "last_modified": timezone.now().isoformat(),
        "isLocked": False,
        "children": children,
    }


def get_zip_folder(request):
    entries = [
  {
    "name": "cwiczenia2/",
    "isDirectory": True,
    "compressionMethod": 0,
    "compressedSize": 0,
    "uncompressedSize": 0,
    "offset": 0
  },
  {
    "name": "cwiczenia2/cwiczenia2/",
    "isDirectory": True,
    "compressionMethod": 0,
    "compressedSize": 0,
    "uncompressedSize": 0,
    "offset": 73
  },
  {
    "name": "cwiczenia2/cwiczenia2/.cproject",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 3064,
    "uncompressedSize": 25288,
    "offset": 157
  },
  {
    "name": "cwiczenia2/cwiczenia2/.metadata/",
    "isDirectory": True,
    "compressionMethod": 0,
    "compressedSize": 0,
    "uncompressedSize": 0,
    "offset": 3330
  },
  {
    "name": "cwiczenia2/cwiczenia2/.metadata/.ide.log",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 136,
    "uncompressedSize": 198,
    "offset": 3424
  },
  {
    "name": "cwiczenia2/cwiczenia2/.metadata/.lock",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 2,
    "uncompressedSize": 0,
    "offset": 3678
  },
  {
    "name": "cwiczenia2/cwiczenia2/.metadata/.log",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 495,
    "uncompressedSize": 1029,
    "offset": 3795
  },
  {
    "name": "cwiczenia2/cwiczenia2/.metadata/.log4j2.xml",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 376,
    "uncompressedSize": 752,
    "offset": 4404
  },
  {
    "name": "cwiczenia2/cwiczenia2/.metadata/.plugins/",
    "isDirectory": True,
    "compressionMethod": 0,
    "compressedSize": 0,
    "uncompressedSize": 0,
    "offset": 4901
  },
  {
    "name": "cwiczenia2/cwiczenia2/.metadata/.plugins/com.st.stm32cube.ide.mcu.ide/",
    "isDirectory": True,
    "compressionMethod": 0,
    "compressedSize": 0,
    "uncompressedSize": 0,
    "offset": 5004
  },
  {
    "name": "cwiczenia2/cwiczenia2/.metadata/.plugins/com.st.stm32cube.ide.mcu.ide/2.7.100.202602191540",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 2,
    "uncompressedSize": 0,
    "offset": 5136
  },
  {
    "name": "cwiczenia2/cwiczenia2/.metadata/.plugins/com.st.stm32cube.ide.mcu.informationcenter/",
    "isDirectory": True,
    "compressionMethod": 0,
    "compressedSize": 0,
    "uncompressedSize": 0,
    "offset": 5306
  },
  {
    "name": "cwiczenia2/cwiczenia2/.metadata/.plugins/com.st.stm32cube.ide.mcu.informationcenter/2.4.200.202602102110",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 2,
    "uncompressedSize": 0,
    "offset": 5452
  },
  {
    "name": "cwiczenia2/cwiczenia2/.metadata/.plugins/org.eclipse.cdt.core/",
    "isDirectory": True,
    "compressionMethod": 0,
    "compressedSize": 0,
    "uncompressedSize": 0,
    "offset": 5636
  },
  {
    "name": "cwiczenia2/cwiczenia2/.metadata/.plugins/org.eclipse.cdt.core/.log",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 45,
    "uncompressedSize": 82,
    "offset": 5760
  },
  {
    "name": "cwiczenia2/cwiczenia2/.metadata/.plugins/org.eclipse.cdt.make.core/",
    "isDirectory": True,
    "compressionMethod": 0,
    "compressedSize": 0,
    "uncompressedSize": 0,
    "offset": 5949
  },
  {
    "name": "cwiczenia2/cwiczenia2/.metadata/.plugins/org.eclipse.cdt.make.core/specs.c",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 3,
    "uncompressedSize": 1,
    "offset": 6078
  },
  {
    "name": "cwiczenia2/cwiczenia2/.metadata/.plugins/org.eclipse.cdt.make.core/specs.cpp",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 3,
    "uncompressedSize": 1,
    "offset": 6233
  },
  {
    "name": "cwiczenia2/cwiczenia2/.metadata/.plugins/org.eclipse.cdt.make.ui/",
    "isDirectory": True,
    "compressionMethod": 0,
    "compressedSize": 0,
    "uncompressedSize": 0,
    "offset": 6390
  },
  {
    "name": "cwiczenia2/cwiczenia2/.metadata/.plugins/org.eclipse.cdt.make.ui/dialog_settings.xml",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 115,
    "uncompressedSize": 149,
    "offset": 6517
  },
  {
    "name": "cwiczenia2/cwiczenia2/.metadata/.plugins/org.eclipse.core.resources/",
    "isDirectory": True,
    "compressionMethod": 0,
    "compressedSize": 0,
    "uncompressedSize": 0,
    "offset": 6794
  },
  {
    "name": "cwiczenia2/cwiczenia2/.metadata/.plugins/org.eclipse.core.resources/.history/",
    "isDirectory": True,
    "compressionMethod": 0,
    "compressedSize": 0,
    "uncompressedSize": 0,
    "offset": 6924
  },
  {
    "name": "cwiczenia2/cwiczenia2/.metadata/.plugins/org.eclipse.core.resources/.root/",
    "isDirectory": True,
    "compressionMethod": 0,
    "compressedSize": 0,
    "uncompressedSize": 0,
    "offset": 7063
  },
  {
    "name": "cwiczenia2/cwiczenia2/.metadata/.plugins/org.eclipse.core.resources/.root/.indexes/",
    "isDirectory": True,
    "compressionMethod": 0,
    "compressedSize": 0,
    "uncompressedSize": 0,
    "offset": 7199
  },
  {
    "name": "cwiczenia2/cwiczenia2/.metadata/.plugins/org.eclipse.core.resources/.root/.indexes/history.version",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 3,
    "uncompressedSize": 1,
    "offset": 7344
  },
  {
    "name": "cwiczenia2/cwiczenia2/.metadata/.plugins/org.eclipse.core.resources/.root/.indexes/properties.version",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 3,
    "uncompressedSize": 1,
    "offset": 7523
  },
  {
    "name": "cwiczenia2/cwiczenia2/.metadata/.plugins/org.eclipse.core.resources/.root/1.tree",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 47,
    "uncompressedSize": 81,
    "offset": 7705
  },
  {
    "name": "cwiczenia2/cwiczenia2/.metadata/.plugins/org.eclipse.core.resources/.safetable/",
    "isDirectory": True,
    "compressionMethod": 0,
    "compressedSize": 0,
    "uncompressedSize": 0,
    "offset": 7910
  },
  {
    "name": "cwiczenia2/cwiczenia2/.metadata/.plugins/org.eclipse.core.resources/.safetable/org.eclipse.core.resources",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 184,
    "uncompressedSize": 441,
    "offset": 8051
  },
  {
    "name": "cwiczenia2/cwiczenia2/.metadata/.plugins/org.eclipse.core.runtime/",
    "isDirectory": True,
    "compressionMethod": 0,
    "compressedSize": 0,
    "uncompressedSize": 0,
    "offset": 8418
  },
  {
    "name": "cwiczenia2/cwiczenia2/.metadata/.plugins/org.eclipse.core.runtime/.settings/",
    "isDirectory": True,
    "compressionMethod": 0,
    "compressedSize": 0,
    "uncompressedSize": 0,
    "offset": 8546
  },
  {
    "name": "cwiczenia2/cwiczenia2/.metadata/.plugins/org.eclipse.core.runtime/.settings/com.st.stm32cube.ide.mcu.ide.oss.prefs",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 73,
    "uncompressedSize": 79,
    "offset": 8684
  },
  {
    "name": "cwiczenia2/cwiczenia2/.metadata/.plugins/org.eclipse.core.runtime/.settings/org.eclipse.cdt.debug.core.prefs",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 315,
    "uncompressedSize": 783,
    "offset": 8949
  },
  {
    "name": "cwiczenia2/cwiczenia2/.metadata/.plugins/org.eclipse.core.runtime/.settings/org.eclipse.cdt.ui.prefs",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 93,
    "uncompressedSize": 121,
    "offset": 9450
  },
  {
    "name": "cwiczenia2/cwiczenia2/.metadata/.plugins/org.eclipse.core.runtime/.settings/org.eclipse.core.resources.prefs",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 56,
    "uncompressedSize": 64,
    "offset": 9721
  },
  {
    "name": "cwiczenia2/cwiczenia2/.metadata/.plugins/org.eclipse.core.runtime/.settings/org.eclipse.debug.core.prefs",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 184,
    "uncompressedSize": 640,
    "offset": 9963
  },
  {
    "name": "cwiczenia2/cwiczenia2/.metadata/.plugins/org.eclipse.core.runtime/.settings/org.eclipse.debug.ui.prefs",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 146,
    "uncompressedSize": 165,
    "offset": 10329
  },
  {
    "name": "cwiczenia2/cwiczenia2/.metadata/.plugins/org.eclipse.core.runtime/.settings/org.eclipse.ui.browser.prefs",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 255,
    "uncompressedSize": 561,
    "offset": 10655
  },
  {
    "name": "cwiczenia2/cwiczenia2/.metadata/.plugins/org.eclipse.core.runtime/.settings/org.eclipse.ui.ide.prefs",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 94,
    "uncompressedSize": 100,
    "offset": 11092
  },
  {
    "name": "cwiczenia2/cwiczenia2/.metadata/.plugins/org.eclipse.core.runtime/.settings/org.eclipse.ui.navigator.prefs",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 205,
    "uncompressedSize": 491,
    "offset": 11364
  },
  {
    "name": "cwiczenia2/cwiczenia2/.metadata/.plugins/org.eclipse.core.runtime/.settings/org.eclipse.ui.prefs",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 50,
    "uncompressedSize": 48,
    "offset": 11753
  },
  {
    "name": "cwiczenia2/cwiczenia2/.metadata/.plugins/org.eclipse.core.runtime/.settings/org.eclipse.ui.workbench.prefs",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 245,
    "uncompressedSize": 665,
    "offset": 11977
  },
  {
    "name": "cwiczenia2/cwiczenia2/.metadata/.plugins/org.eclipse.debug.core/",
    "isDirectory": True,
    "compressionMethod": 0,
    "compressedSize": 0,
    "uncompressedSize": 0,
    "offset": 12406
  },
  {
    "name": "cwiczenia2/cwiczenia2/.metadata/.plugins/org.eclipse.debug.ui/",
    "isDirectory": True,
    "compressionMethod": 0,
    "compressedSize": 0,
    "uncompressedSize": 0,
    "offset": 12532
  },
  {
    "name": "cwiczenia2/cwiczenia2/.metadata/.plugins/org.eclipse.e4.workbench/",
    "isDirectory": True,
    "compressionMethod": 0,
    "compressedSize": 0,
    "uncompressedSize": 0,
    "offset": 12656
  },
  {
    "name": "cwiczenia2/cwiczenia2/.metadata/.plugins/org.eclipse.e4.workbench/workbench.xmi",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 33669,
    "uncompressedSize": 269414,
    "offset": 12784
  },
  {
    "name": "cwiczenia2/cwiczenia2/.metadata/.plugins/org.eclipse.ui.ide/",
    "isDirectory": True,
    "compressionMethod": 0,
    "compressedSize": 0,
    "uncompressedSize": 0,
    "offset": 46610
  },
  {
    "name": "cwiczenia2/cwiczenia2/.metadata/.plugins/org.eclipse.ui.ide/dialog_settings.xml",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 162,
    "uncompressedSize": 217,
    "offset": 46732
  },
  {
    "name": "cwiczenia2/cwiczenia2/.metadata/.plugins/org.eclipse.ui.intro/",
    "isDirectory": True,
    "compressionMethod": 0,
    "compressedSize": 0,
    "uncompressedSize": 0,
    "offset": 47051
  },
  {
    "name": "cwiczenia2/cwiczenia2/.metadata/.plugins/org.eclipse.ui.workbench/",
    "isDirectory": True,
    "compressionMethod": 0,
    "compressedSize": 0,
    "uncompressedSize": 0,
    "offset": 47175
  },
  {
    "name": "cwiczenia2/cwiczenia2/.metadata/.plugins/org.eclipse.ui.workbench/workingsets.xml",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 177,
    "uncompressedSize": 257,
    "offset": 47303
  },
  {
    "name": "cwiczenia2/cwiczenia2/.metadata/version.ini",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 89,
    "uncompressedSize": 103,
    "offset": 47639
  },
  {
    "name": "cwiczenia2/cwiczenia2/.mxproject",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 816,
    "uncompressedSize": 8967,
    "offset": 47849
  },
  {
    "name": "cwiczenia2/cwiczenia2/.project",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 353,
    "uncompressedSize": 1216,
    "offset": 48775
  },
  {
    "name": "cwiczenia2/cwiczenia2/.settings/",
    "isDirectory": True,
    "compressionMethod": 0,
    "compressedSize": 0,
    "uncompressedSize": 0,
    "offset": 49236
  },
  {
    "name": "cwiczenia2/cwiczenia2/.settings/com.st.stm32cube.ide.mcu.sfrview.prefs",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 92,
    "uncompressedSize": 115,
    "offset": 49330
  },
  {
    "name": "cwiczenia2/cwiczenia2/.settings/language.settings.xml",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 535,
    "uncompressedSize": 2193,
    "offset": 49570
  },
  {
    "name": "cwiczenia2/cwiczenia2/.settings/org.eclipse.core.resources.prefs",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 58,
    "uncompressedSize": 57,
    "offset": 50236
  },
  {
    "name": "cwiczenia2/cwiczenia2/.settings/stm32cubeide.project.prefs",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 152,
    "uncompressedSize": 232,
    "offset": 50436
  },
  {
    "name": "cwiczenia2/cwiczenia2/Core/",
    "isDirectory": True,
    "compressionMethod": 0,
    "compressedSize": 0,
    "uncompressedSize": 0,
    "offset": 50724
  },
  {
    "name": "cwiczenia2/cwiczenia2/Core/Inc/",
    "isDirectory": True,
    "compressionMethod": 0,
    "compressedSize": 0,
    "uncompressedSize": 0,
    "offset": 50813
  },
  {
    "name": "cwiczenia2/cwiczenia2/Core/Inc/gpio.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 469,
    "uncompressedSize": 1313,
    "offset": 50906
  },
  {
    "name": "cwiczenia2/cwiczenia2/Core/Inc/main.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 700,
    "uncompressedSize": 2644,
    "offset": 51490
  },
  {
    "name": "cwiczenia2/cwiczenia2/Core/Inc/stm32g4xx_hal_conf.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 2913,
    "uncompressedSize": 13323,
    "offset": 52305
  },
  {
    "name": "cwiczenia2/cwiczenia2/Core/Inc/stm32g4xx_it.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 598,
    "uncompressedSize": 2022,
    "offset": 55347
  },
  {
    "name": "cwiczenia2/cwiczenia2/Core/Inc/tim.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 495,
    "uncompressedSize": 1406,
    "offset": 56068
  },
  {
    "name": "cwiczenia2/cwiczenia2/Core/Inc/usart.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 490,
    "uncompressedSize": 1364,
    "offset": 56677
  },
  {
    "name": "cwiczenia2/cwiczenia2/Core/Src/",
    "isDirectory": True,
    "compressionMethod": 0,
    "compressedSize": 0,
    "uncompressedSize": 0,
    "offset": 57283
  },
  {
    "name": "cwiczenia2/cwiczenia2/Core/Src/gpio.c",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 734,
    "uncompressedSize": 2298,
    "offset": 57376
  },
  {
    "name": "cwiczenia2/cwiczenia2/Core/Src/main.c",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 1917,
    "uncompressedSize": 6221,
    "offset": 58225
  },
  {
    "name": "cwiczenia2/cwiczenia2/Core/Src/stm32g4xx_hal_msp.c",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 665,
    "uncompressedSize": 2352,
    "offset": 60257
  },
  {
    "name": "cwiczenia2/cwiczenia2/Core/Src/stm32g4xx_it.c",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 1256,
    "uncompressedSize": 6427,
    "offset": 61050
  },
  {
    "name": "cwiczenia2/cwiczenia2/Core/Src/syscalls.c",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 1007,
    "uncompressedSize": 2847,
    "offset": 62429
  },
  {
    "name": "cwiczenia2/cwiczenia2/Core/Src/sysmem.c",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 1006,
    "uncompressedSize": 2726,
    "offset": 63555
  },
  {
    "name": "cwiczenia2/cwiczenia2/Core/Src/system_stm32g4xx.c",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 2704,
    "uncompressedSize": 10446,
    "offset": 64678
  },
  {
    "name": "cwiczenia2/cwiczenia2/Core/Src/tim.c",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 985,
    "uncompressedSize": 4341,
    "offset": 67509
  },
  {
    "name": "cwiczenia2/cwiczenia2/Core/Src/usart.c",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 1176,
    "uncompressedSize": 3866,
    "offset": 68608
  },
  {
    "name": "cwiczenia2/cwiczenia2/Core/Startup/",
    "isDirectory": True,
    "compressionMethod": 0,
    "compressedSize": 0,
    "uncompressedSize": 0,
    "offset": 69900
  },
  {
    "name": "cwiczenia2/cwiczenia2/Core/Startup/startup_stm32g491retx.s",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 2786,
    "uncompressedSize": 13812,
    "offset": 69997
  },
  {
    "name": "cwiczenia2/cwiczenia2/cwiczenia2 Debug.launch",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 1840,
    "uncompressedSize": 9937,
    "offset": 72919
  },
  {
    "name": "cwiczenia2/cwiczenia2/cwiczenia2.ioc",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 2072,
    "uncompressedSize": 7426,
    "offset": 74882
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/",
    "isDirectory": True,
    "compressionMethod": 0,
    "compressedSize": 0,
    "uncompressedSize": 0,
    "offset": 77068
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Core/",
    "isDirectory": True,
    "compressionMethod": 0,
    "compressedSize": 0,
    "uncompressedSize": 0,
    "offset": 77158
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Core/Src/",
    "isDirectory": True,
    "compressionMethod": 0,
    "compressedSize": 0,
    "uncompressedSize": 0,
    "offset": 77253
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Core/Src/gpio.cyclo",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 42,
    "uncompressedSize": 40,
    "offset": 77352
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Core/Src/gpio.d",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 403,
    "uncompressedSize": 3433,
    "offset": 77519
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Core/Src/gpio.o",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 323777,
    "uncompressedSize": 1077168,
    "offset": 78043
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Core/Src/gpio.su",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 50,
    "uncompressedSize": 48,
    "offset": 401941
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Core/Src/main.cyclo",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 137,
    "uncompressedSize": 230,
    "offset": 402113
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Core/Src/main.d",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 420,
    "uncompressedSize": 3561,
    "offset": 402375
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Core/Src/main.o",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 327503,
    "uncompressedSize": 1083616,
    "offset": 402916
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Core/Src/main.su",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 159,
    "uncompressedSize": 288,
    "offset": 730540
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Core/Src/stm32g4xx_hal_msp.cyclo",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 54,
    "uncompressedSize": 52,
    "offset": 730821
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Core/Src/stm32g4xx_hal_msp.d",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 397,
    "uncompressedSize": 3419,
    "offset": 731013
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Core/Src/stm32g4xx_hal_msp.o",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 321282,
    "uncompressedSize": 1073196,
    "offset": 731544
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Core/Src/stm32g4xx_hal_msp.su",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 62,
    "uncompressedSize": 60,
    "offset": 1052960
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Core/Src/stm32g4xx_it.cyclo",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 181,
    "uncompressedSize": 631,
    "offset": 1053157
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Core/Src/stm32g4xx_it.d",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 406,
    "uncompressedSize": 3469,
    "offset": 1053471
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Core/Src/stm32g4xx_it.o",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 324785,
    "uncompressedSize": 1080064,
    "offset": 1054006
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Core/Src/stm32g4xx_it.su",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 187,
    "uncompressedSize": 715,
    "offset": 1378920
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Core/Src/subdir.mk",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 802,
    "uncompressedSize": 2597,
    "offset": 1379237
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Core/Src/syscalls.cyclo",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 204,
    "uncompressedSize": 712,
    "offset": 1380163
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Core/Src/syscalls.d",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 32,
    "uncompressedSize": 45,
    "offset": 1380496
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Core/Src/syscalls.o",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 30023,
    "uncompressedSize": 83460,
    "offset": 1380653
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Core/Src/syscalls.su",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 224,
    "uncompressedSize": 853,
    "offset": 1410801
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Core/Src/sysmem.cyclo",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 37,
    "uncompressedSize": 35,
    "offset": 1411151
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Core/Src/sysmem.d",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 30,
    "uncompressedSize": 41,
    "offset": 1411315
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Core/Src/sysmem.o",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 20223,
    "uncompressedSize": 55960,
    "offset": 1411468
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Core/Src/sysmem.su",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 45,
    "uncompressedSize": 43,
    "offset": 1431814
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Core/Src/system_stm32g4xx.cyclo",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 75,
    "uncompressedSize": 113,
    "offset": 1431983
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Core/Src/system_stm32g4xx.d",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 381,
    "uncompressedSize": 3377,
    "offset": 1432195
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Core/Src/system_stm32g4xx.o",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 322248,
    "uncompressedSize": 1074180,
    "offset": 1432709
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Core/Src/system_stm32g4xx.su",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 83,
    "uncompressedSize": 128,
    "offset": 1755090
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Core/Src/tim.cyclo",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 81,
    "uncompressedSize": 175,
    "offset": 1755307
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Core/Src/tim.d",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 402,
    "uncompressedSize": 3429,
    "offset": 1755512
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Core/Src/tim.o",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 326902,
    "uncompressedSize": 1083364,
    "offset": 1756034
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Core/Src/tim.su",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 93,
    "uncompressedSize": 207,
    "offset": 2083056
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Core/Src/usart.cyclo",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 81,
    "uncompressedSize": 141,
    "offset": 2083270
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Core/Src/usart.d",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 403,
    "uncompressedSize": 3437,
    "offset": 2083477
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Core/Src/usart.o",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 326479,
    "uncompressedSize": 1081292,
    "offset": 2084002
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Core/Src/usart.su",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 89,
    "uncompressedSize": 165,
    "offset": 2410603
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Core/Startup/",
    "isDirectory": True,
    "compressionMethod": 0,
    "compressedSize": 0,
    "uncompressedSize": 0,
    "offset": 2410815
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Core/Startup/startup_stm32g491retx.d",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 49,
    "uncompressedSize": 83,
    "offset": 2410918
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Core/Startup/startup_stm32g491retx.o",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 2306,
    "uncompressedSize": 7492,
    "offset": 2411109
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Core/Startup/subdir.mk",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 459,
    "uncompressedSize": 1002,
    "offset": 2413557
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/cwiczenia2.elf",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 366450,
    "uncompressedSize": 1171728,
    "offset": 2414144
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/cwiczenia2.list",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 70324,
    "uncompressedSize": 375641,
    "offset": 2780714
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/cwiczenia2.map",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 20075,
    "uncompressedSize": 364276,
    "offset": 2851159
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/",
    "isDirectory": True,
    "compressionMethod": 0,
    "compressedSize": 0,
    "uncompressedSize": 0,
    "offset": 2871354
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/",
    "isDirectory": True,
    "compressionMethod": 0,
    "compressedSize": 0,
    "uncompressedSize": 0,
    "offset": 2871452
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/",
    "isDirectory": True,
    "compressionMethod": 0,
    "compressedSize": 0,
    "uncompressedSize": 0,
    "offset": 2871571
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal.cyclo",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 506,
    "uncompressedSize": 3206,
    "offset": 2871694
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal.d",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 380,
    "uncompressedSize": 3423,
    "offset": 2872358
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal.o",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 328806,
    "uncompressedSize": 1092092,
    "offset": 2872892
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal.su",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 519,
    "uncompressedSize": 3481,
    "offset": 3201852
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_cortex.cyclo",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 453,
    "uncompressedSize": 2742,
    "offset": 3202526
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_cortex.d",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 386,
    "uncompressedSize": 3437,
    "offset": 3203144
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_cortex.o",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 329158,
    "uncompressedSize": 1091176,
    "offset": 3203691
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_cortex.su",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 506,
    "uncompressedSize": 3107,
    "offset": 3533010
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_dma.cyclo",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 295,
    "uncompressedSize": 1296,
    "offset": 3533678
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_dma.d",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 385,
    "uncompressedSize": 3431,
    "offset": 3534135
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_dma.o",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 326877,
    "uncompressedSize": 1084104,
    "offset": 3534678
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_dma.su",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 299,
    "uncompressedSize": 1414,
    "offset": 3861713
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_dma_ex.cyclo",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 163,
    "uncompressedSize": 501,
    "offset": 3862171
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_dma_ex.d",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 385,
    "uncompressedSize": 3437,
    "offset": 3862499
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_dma_ex.o",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 323411,
    "uncompressedSize": 1076360,
    "offset": 3863045
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_dma_ex.su",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 186,
    "uncompressedSize": 561,
    "offset": 4186617
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_exti.cyclo",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 199,
    "uncompressedSize": 799,
    "offset": 4186965
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_exti.d",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 383,
    "uncompressedSize": 3433,
    "offset": 4187327
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_exti.o",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 323800,
    "uncompressedSize": 1078168,
    "offset": 4187869
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_exti.su",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 208,
    "uncompressedSize": 871,
    "offset": 4511828
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_flash.cyclo",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 268,
    "uncompressedSize": 1258,
    "offset": 4512196
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_flash.d",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 384,
    "uncompressedSize": 3435,
    "offset": 4512628
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_flash.o",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 325655,
    "uncompressedSize": 1081344,
    "offset": 4513172
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_flash.su",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 291,
    "uncompressedSize": 1407,
    "offset": 4838987
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_flash_ex.cyclo",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 360,
    "uncompressedSize": 2025,
    "offset": 4839439
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_flash_ex.d",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 385,
    "uncompressedSize": 3441,
    "offset": 4839966
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_flash_ex.o",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 327512,
    "uncompressedSize": 1086264,
    "offset": 4840514
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_flash_ex.su",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 362,
    "uncompressedSize": 2196,
    "offset": 5168189
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_flash_ramfunc.cyclo",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 114,
    "uncompressedSize": 214,
    "offset": 5168715
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_flash_ramfunc.d",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 386,
    "uncompressedSize": 3451,
    "offset": 5169001
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_flash_ramfunc.o",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 320543,
    "uncompressedSize": 1071712,
    "offset": 5169555
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_flash_ramfunc.su",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 121,
    "uncompressedSize": 228,
    "offset": 5490266
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_gpio.cyclo",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 183,
    "uncompressedSize": 682,
    "offset": 5490556
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_gpio.d",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 383,
    "uncompressedSize": 3433,
    "offset": 5490902
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_gpio.o",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 324522,
    "uncompressedSize": 1078848,
    "offset": 5491444
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_gpio.su",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 190,
    "uncompressedSize": 744,
    "offset": 5816125
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_pwr.cyclo",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 266,
    "uncompressedSize": 1403,
    "offset": 5816475
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_pwr.d",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 382,
    "uncompressedSize": 3431,
    "offset": 5816903
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_pwr.o",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 324618,
    "uncompressedSize": 1080864,
    "offset": 5817443
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_pwr.su",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 292,
    "uncompressedSize": 1560,
    "offset": 6142219
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_pwr_ex.cyclo",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 496,
    "uncompressedSize": 3585,
    "offset": 6142670
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_pwr_ex.d",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 382,
    "uncompressedSize": 3437,
    "offset": 6143331
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_pwr_ex.o",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 327968,
    "uncompressedSize": 1090868,
    "offset": 6143874
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_pwr_ex.su",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 521,
    "uncompressedSize": 3912,
    "offset": 6472003
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_rcc.cyclo",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 283,
    "uncompressedSize": 1401,
    "offset": 6472686
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_rcc.d",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 383,
    "uncompressedSize": 3431,
    "offset": 6473131
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_rcc.o",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 329407,
    "uncompressedSize": 1088524,
    "offset": 6473672
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_rcc.su",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 295,
    "uncompressedSize": 1519,
    "offset": 6803237
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_rcc_ex.cyclo",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 334,
    "uncompressedSize": 1855,
    "offset": 6803691
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_rcc_ex.d",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 384,
    "uncompressedSize": 3437,
    "offset": 6804190
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_rcc_ex.o",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 330467,
    "uncompressedSize": 1092232,
    "offset": 6804735
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_rcc_ex.su",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 344,
    "uncompressedSize": 1993,
    "offset": 7135363
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_tim.cyclo",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 1258,
    "uncompressedSize": 10860,
    "offset": 7135869
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_tim.d",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 385,
    "uncompressedSize": 3431,
    "offset": 7137289
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_tim.o",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 349139,
    "uncompressedSize": 1173856,
    "offset": 7137832
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_tim.su",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 1194,
    "uncompressedSize": 11783,
    "offset": 7487129
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_tim_ex.cyclo",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 865,
    "uncompressedSize": 6752,
    "offset": 7488482
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_tim_ex.d",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 385,
    "uncompressedSize": 3437,
    "offset": 7489512
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_tim_ex.o",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 338530,
    "uncompressedSize": 1126744,
    "offset": 7490058
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_tim_ex.su",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 823,
    "uncompressedSize": 7286,
    "offset": 7828749
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_uart.cyclo",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 866,
    "uncompressedSize": 6340,
    "offset": 7829734
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_uart.d",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 384,
    "uncompressedSize": 3433,
    "offset": 7830763
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_uart.o",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 347446,
    "uncompressedSize": 1149872,
    "offset": 7831306
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_uart.su",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 908,
    "uncompressedSize": 7578,
    "offset": 8178911
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_uart_ex.cyclo",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 365,
    "uncompressedSize": 1770,
    "offset": 8179979
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_uart_ex.d",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 384,
    "uncompressedSize": 3439,
    "offset": 8180510
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_uart_ex.o",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 329155,
    "uncompressedSize": 1088508,
    "offset": 8181056
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_uart_ex.su",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 391,
    "uncompressedSize": 1993,
    "offset": 8510373
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/Drivers/STM32G4xx_HAL_Driver/Src/subdir.mk",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 1001,
    "uncompressedSize": 8277,
    "offset": 8510927
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/makefile",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 1086,
    "uncompressedSize": 3004,
    "offset": 8512076
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/objects.list",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 205,
    "uncompressedSize": 1291,
    "offset": 8513276
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/objects.mk",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 118,
    "uncompressedSize": 285,
    "offset": 8513599
  },
  {
    "name": "cwiczenia2/cwiczenia2/Debug/sources.mk",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 286,
    "uncompressedSize": 631,
    "offset": 8513833
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/",
    "isDirectory": True,
    "compressionMethod": 0,
    "compressedSize": 0,
    "uncompressedSize": 0,
    "offset": 8514235
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/CMSIS/",
    "isDirectory": True,
    "compressionMethod": 0,
    "compressedSize": 0,
    "uncompressedSize": 0,
    "offset": 8514327
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/CMSIS/Device/",
    "isDirectory": True,
    "compressionMethod": 0,
    "compressedSize": 0,
    "uncompressedSize": 0,
    "offset": 8514425
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/CMSIS/Device/ST/",
    "isDirectory": True,
    "compressionMethod": 0,
    "compressedSize": 0,
    "uncompressedSize": 0,
    "offset": 8514530
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/CMSIS/Device/ST/STM32G4xx/",
    "isDirectory": True,
    "compressionMethod": 0,
    "compressedSize": 0,
    "uncompressedSize": 0,
    "offset": 8514638
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/CMSIS/Device/ST/STM32G4xx/Include/",
    "isDirectory": True,
    "compressionMethod": 0,
    "compressedSize": 0,
    "uncompressedSize": 0,
    "offset": 8514756
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/CMSIS/Device/ST/STM32G4xx/Include/stm32g491xx.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 121210,
    "uncompressedSize": 1033960,
    "offset": 8514882
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/CMSIS/Device/ST/STM32G4xx/Include/stm32g4xx.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 2051,
    "uncompressedSize": 8920,
    "offset": 8636247
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/CMSIS/Device/ST/STM32G4xx/Include/system_stm32g4xx.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 814,
    "uncompressedSize": 2252,
    "offset": 8638451
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/CMSIS/Device/ST/STM32G4xx/LICENSE.txt",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 204,
    "uncompressedSize": 371,
    "offset": 8639425
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/CMSIS/Device/ST/STM32G4xx/Source/",
    "isDirectory": True,
    "compressionMethod": 0,
    "compressedSize": 0,
    "uncompressedSize": 0,
    "offset": 8639774
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/CMSIS/Device/ST/STM32G4xx/Source/Templates/",
    "isDirectory": True,
    "compressionMethod": 0,
    "compressedSize": 0,
    "uncompressedSize": 0,
    "offset": 8639899
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/CMSIS/Include/",
    "isDirectory": True,
    "compressionMethod": 0,
    "compressedSize": 0,
    "uncompressedSize": 0,
    "offset": 8640034
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/CMSIS/Include/cmsis_armcc.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 5547,
    "uncompressedSize": 29026,
    "offset": 8640140
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/CMSIS/Include/cmsis_armclang.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 7159,
    "uncompressedSize": 47343,
    "offset": 8645822
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/CMSIS/Include/cmsis_armclang_ltm.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 7487,
    "uncompressedSize": 57115,
    "offset": 8653119
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/CMSIS/Include/cmsis_compiler.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 1587,
    "uncompressedSize": 9764,
    "offset": 8660748
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/CMSIS/Include/cmsis_gcc.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 8479,
    "uncompressedSize": 64795,
    "offset": 8662473
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/CMSIS/Include/cmsis_iccarm.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 5085,
    "uncompressedSize": 29127,
    "offset": 8671085
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/CMSIS/Include/cmsis_version.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 715,
    "uncompressedSize": 1715,
    "offset": 8676306
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/CMSIS/Include/core_armv81mml.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 23625,
    "uncompressedSize": 171740,
    "offset": 8677158
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/CMSIS/Include/core_armv8mbl.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 14703,
    "uncompressedSize": 98060,
    "offset": 8700921
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/CMSIS/Include/core_armv8mml.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 22727,
    "uncompressedSize": 161332,
    "offset": 8715761
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/CMSIS/Include/core_cm0.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 8046,
    "uncompressedSize": 42382,
    "offset": 8738625
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/CMSIS/Include/core_cm0plus.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 9198,
    "uncompressedSize": 50609,
    "offset": 8746803
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/CMSIS/Include/core_cm1.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 8222,
    "uncompressedSize": 43605,
    "offset": 8756137
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/CMSIS/Include/core_cm23.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 15383,
    "uncompressedSize": 104693,
    "offset": 8764491
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/CMSIS/Include/core_cm3.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 17281,
    "uncompressedSize": 111357,
    "offset": 8780007
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/CMSIS/Include/core_cm33.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 23425,
    "uncompressedSize": 167995,
    "offset": 8797420
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/CMSIS/Include/core_cm35p.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 23424,
    "uncompressedSize": 168005,
    "offset": 8820978
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/CMSIS/Include/core_cm4.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 18666,
    "uncompressedSize": 122991,
    "offset": 8844536
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/CMSIS/Include/core_cm7.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 22173,
    "uncompressedSize": 151761,
    "offset": 8863334
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/CMSIS/Include/core_sc000.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 8680,
    "uncompressedSize": 47432,
    "offset": 8885639
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/CMSIS/Include/core_sc300.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 17115,
    "uncompressedSize": 110326,
    "offset": 8894453
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/CMSIS/Include/mpu_armv7.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 2934,
    "uncompressedSize": 11962,
    "offset": 8911702
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/CMSIS/Include/mpu_armv8.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 2891,
    "uncompressedSize": 11601,
    "offset": 8914769
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/CMSIS/Include/tz_context.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 1019,
    "uncompressedSize": 2757,
    "offset": 8917793
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/CMSIS/LICENSE.txt",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 3963,
    "uncompressedSize": 11558,
    "offset": 8918946
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/",
    "isDirectory": True,
    "compressionMethod": 0,
    "compressedSize": 0,
    "uncompressedSize": 0,
    "offset": 8923034
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Inc/",
    "isDirectory": True,
    "compressionMethod": 0,
    "compressedSize": 0,
    "uncompressedSize": 0,
    "offset": 8923147
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Inc/Legacy/",
    "isDirectory": True,
    "compressionMethod": 0,
    "compressedSize": 0,
    "uncompressedSize": 0,
    "offset": 8923264
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Inc/Legacy/stm32_hal_legacy.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 31631,
    "uncompressedSize": 238453,
    "offset": 8923388
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Inc/stm32g4xx_hal.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 4616,
    "uncompressedSize": 28432,
    "offset": 8955177
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Inc/stm32g4xx_hal_cortex.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 2822,
    "uncompressedSize": 17496,
    "offset": 8959941
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Inc/stm32g4xx_hal_def.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 2146,
    "uncompressedSize": 6966,
    "offset": 8962918
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Inc/stm32g4xx_hal_dma.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 5441,
    "uncompressedSize": 36647,
    "offset": 8965216
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Inc/stm32g4xx_hal_dma_ex.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 2125,
    "uncompressedSize": 12359,
    "offset": 8970809
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Inc/stm32g4xx_hal_exti.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 2201,
    "uncompressedSize": 12393,
    "offset": 8973089
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Inc/stm32g4xx_hal_flash.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 7952,
    "uncompressedSize": 46690,
    "offset": 8975443
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Inc/stm32g4xx_hal_flash_ex.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 704,
    "uncompressedSize": 2407,
    "offset": 8983549
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Inc/stm32g4xx_hal_flash_ramfunc.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 622,
    "uncompressedSize": 1917,
    "offset": 8984410
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Inc/stm32g4xx_hal_gpio.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 2762,
    "uncompressedSize": 13950,
    "offset": 8985194
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Inc/stm32g4xx_hal_gpio_ex.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 2179,
    "uncompressedSize": 15425,
    "offset": 8988109
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Inc/stm32g4xx_hal_pwr.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 3009,
    "uncompressedSize": 15124,
    "offset": 8990444
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Inc/stm32g4xx_hal_pwr_ex.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 4788,
    "uncompressedSize": 30706,
    "offset": 8993605
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Inc/stm32g4xx_hal_rcc.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 17113,
    "uncompressedSize": 166562,
    "offset": 8998548
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Inc/stm32g4xx_hal_rcc_ex.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 8806,
    "uncompressedSize": 75435,
    "offset": 9015813
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Inc/stm32g4xx_hal_tim.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 19757,
    "uncompressedSize": 159250,
    "offset": 9024774
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Inc/stm32g4xx_hal_tim_ex.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 8256,
    "uncompressedSize": 122240,
    "offset": 9044683
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Inc/stm32g4xx_hal_uart.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 13763,
    "uncompressedSize": 90289,
    "offset": 9053094
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Inc/stm32g4xx_hal_uart_ex.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 3474,
    "uncompressedSize": 52124,
    "offset": 9067010
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Inc/stm32g4xx_ll_bus.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 5483,
    "uncompressedSize": 74753,
    "offset": 9070640
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Inc/stm32g4xx_ll_cortex.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 4382,
    "uncompressedSize": 24173,
    "offset": 9076274
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Inc/stm32g4xx_ll_crs.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 4196,
    "uncompressedSize": 24277,
    "offset": 9080810
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Inc/stm32g4xx_ll_dma.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 8984,
    "uncompressedSize": 104723,
    "offset": 9085157
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Inc/stm32g4xx_ll_dmamux.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 7896,
    "uncompressedSize": 94605,
    "offset": 9094292
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Inc/stm32g4xx_ll_exti.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 4253,
    "uncompressedSize": 54310,
    "offset": 9102342
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Inc/stm32g4xx_ll_gpio.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 4517,
    "uncompressedSize": 38040,
    "offset": 9106747
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Inc/stm32g4xx_ll_lpuart.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 12536,
    "uncompressedSize": 96038,
    "offset": 9111416
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Inc/stm32g4xx_ll_pwr.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 6151,
    "uncompressedSize": 50980,
    "offset": 9124106
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Inc/stm32g4xx_ll_rcc.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 12936,
    "uncompressedSize": 113531,
    "offset": 9130408
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Inc/stm32g4xx_ll_system.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 7986,
    "uncompressedSize": 59248,
    "offset": 9143495
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Inc/stm32g4xx_ll_tim.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 32638,
    "uncompressedSize": 309101,
    "offset": 9151635
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Inc/stm32g4xx_ll_usart.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 19321,
    "uncompressedSize": 175099,
    "offset": 9184424
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Inc/stm32g4xx_ll_utils.h",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 2857,
    "uncompressedSize": 12120,
    "offset": 9203898
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/LICENSE.txt",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 208,
    "uncompressedSize": 377,
    "offset": 9206908
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Src/",
    "isDirectory": True,
    "compressionMethod": 0,
    "compressedSize": 0,
    "uncompressedSize": 0,
    "offset": 9207256
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal.c",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 5450,
    "uncompressedSize": 23896,
    "offset": 9207373
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_cortex.c",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 4128,
    "uncompressedSize": 21167,
    "offset": 9212971
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_dma.c",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 6074,
    "uncompressedSize": 35354,
    "offset": 9217254
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_dma_ex.c",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 2211,
    "uncompressedSize": 10377,
    "offset": 9223480
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_exti.c",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 3392,
    "uncompressedSize": 17501,
    "offset": 9225846
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_flash.c",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 5159,
    "uncompressedSize": 24008,
    "offset": 9229391
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_flash_ex.c",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 7735,
    "uncompressedSize": 48966,
    "offset": 9234704
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_flash_ramfunc.c",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 2241,
    "uncompressedSize": 7937,
    "offset": 9242596
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_gpio.c",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 4484,
    "uncompressedSize": 18490,
    "offset": 9244999
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_pwr.c",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 6083,
    "uncompressedSize": 24469,
    "offset": 9249636
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_pwr_ex.c",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 6842,
    "uncompressedSize": 38165,
    "offset": 9255871
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_rcc.c",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 10511,
    "uncompressedSize": 51118,
    "offset": 9262868
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_rcc_ex.c",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 9980,
    "uncompressedSize": 63965,
    "offset": 9273531
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_tim.c",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 24137,
    "uncompressedSize": 261847,
    "offset": 9283666
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_tim_ex.c",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 15463,
    "uncompressedSize": 137272,
    "offset": 9307955
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_uart.c",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 22286,
    "uncompressedSize": 160192,
    "offset": 9323573
  },
  {
    "name": "cwiczenia2/cwiczenia2/Drivers/STM32G4xx_HAL_Driver/Src/stm32g4xx_hal_uart_ex.c",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 7895,
    "uncompressedSize": 36414,
    "offset": 9346012
  },
  {
    "name": "cwiczenia2/cwiczenia2/STM32G491RETX_FLASH.ld",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 1611,
    "uncompressedSize": 5341,
    "offset": 9354063
  },
  {
    "name": "cwiczenia2/cwiczenia2/STM32G491RETX_RAM.ld",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 1611,
    "uncompressedSize": 5334,
    "offset": 9355796
  }
]

    tree = build_zip_tree(entries)

    root = folder_to_dict("root", tree)

    response = {
        "folder": root
    }

    return JsonResponse(data=response, status=200)


def stream_entry(file, url, offset, compressed_size, chunk_size=4096):
    session = requests.Session()

    # read slightly more to ensure header fits in first chunk
    extra = 1024

    start = offset
    end = offset + compressed_size + extra - 1

    r = session.get(url, headers={"Range": f"bytes={start}-{end}"}, stream=True)
    r.raise_for_status()

    decryptor = Decryptor(
        method=file.get_encryption_method(),
        key=file.key,
        iv=file.iv,
        start_byte=offset
    )

    decompressor = zlib.decompressobj(-zlib.MAX_WBITS)

    buffer = b""
    header_parsed = False
    consumed = 0  # compressed bytes fed to zlib

    for chunk in r.iter_content(chunk_size):
        if not chunk:
            continue

        dec = decryptor.decrypt(chunk)

        if not dec:
            continue

        buffer += dec

        # ---- parse header once ----
        if not header_parsed:
            if len(buffer) < 30:
                continue

            if buffer[0:4] != b"PK\x03\x04":
                raise ValueError("Invalid ZIP header")

            filename_len = int.from_bytes(buffer[26:28], "little")
            extra_len = int.from_bytes(buffer[28:30], "little")

            header_size = 30 + filename_len + extra_len

            if len(buffer) < header_size:
                continue

            buffer = buffer[header_size:]
            header_parsed = True

        # ---- feed only compressed data ----
        remaining = compressed_size - consumed
        if remaining <= 0:
            break

        chunk_to_feed = buffer[:remaining]
        buffer = buffer[len(chunk_to_feed):]

        consumed += len(chunk_to_feed)

        if chunk_to_feed:
            out = decompressor.decompress(chunk_to_feed)
            if out:
                yield out

    tail = decompressor.flush()
    if tail:
        yield tail

# ---- Django view ----
@api_view(['GET'])
def test_stream_zip_entry(request):
    # no n5gG2tDMjNHKFKdrDcDx3h
    # yes C3dDrVaDS3K7eALC3bmSt3
    file = get_file("C3dDrVaDS3K7eALC3bmSt3")

    meta =  {
    "name": "cwiczenia2/cwiczenia2/Core/Src/gpio.c",
    "isDirectory": False,
    "compressionMethod": 8,
    "compressedSize": 734,
    "uncompressedSize": 2298,
    "offset": 57376
  }

    if meta["isDirectory"]:
        raise Http404("Cannot stream directory")

    if meta["compressionMethod"] != 8:
        raise Http404("Unsupported compression method")

    user = User.objects.get(id=1)

    url = discord.get_attachment_url(user, file.fragments.all()[0])


    generator = stream_entry(file, url, meta["offset"], meta["compressedSize"])

    response = StreamingHttpResponse(
        generator,
        content_type="application/octet-stream"
    )
    response["Content-Disposition"] = f'inline; filename="test.txt"'

    return response


