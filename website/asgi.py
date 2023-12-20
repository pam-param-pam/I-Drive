import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

from .middleware import TokenAuthMiddleware
from .routing import ws_urlpatterns

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'website.settings')


application = ProtocolTypeRouter({
    'http': get_asgi_application(),
    'websocket': TokenAuthMiddleware(URLRouter(ws_urlpatterns))

    })


