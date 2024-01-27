from django.urls import path
from .consumers import UserConsumer, CommandConsumer

ws_urlpatterns = [
    path('user', UserConsumer.as_asgi()),
    path('command', CommandConsumer.as_asgi()),

]
