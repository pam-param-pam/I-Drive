import os
from django.core.asgi import get_asgi_application

# those 2 lines have to be here, in the middle of imports, do not move it elsewhere
# for more info refer to
# https://stackoverflow.com/questions/53683806/django-apps-arent-loaded-yet-when-using-asgi
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'website.settings')
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from .routing import ws_urlpatterns
from .utilities.middlewares import TokenAuthMiddleware


application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': TokenAuthMiddleware(URLRouter(ws_urlpatterns))

})


