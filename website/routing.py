from django.urls import path
from .consumers import UserConsumer

ws_urlpatterns = [
    path('user', UserConsumer.as_asgi()),


]
