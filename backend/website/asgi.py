import os
from django.core.asgi import get_asgi_application
from django.urls import path



# NO IMPORTS BEFORE THIS LINE
# ============================================================
# those 2 lines have to be here, in the middle of imports, do not move it elsewhere
# for more info refer to
# https://stackoverflow.com/questions/53683806/django-apps-arent-loaded-yet-when-using-asgi
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'website.settings')
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from .websockets import QrLoginConsumer
from .websockets import UserConsumer
from .websockets import ShareConsumer

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': URLRouter([
        path('user', UserConsumer.as_asgi()),
        path('qrcode', QrLoginConsumer.as_asgi()),
        path('share', ShareConsumer.as_asgi()),

    ]),
})


