from django.conf import settings
from django.conf.urls.static import static
from django.urls import path

from website import views

urlpatterns = [
        path("", views.index, name="index"),
        path("upload", views.upload_file, name="upload"),
        path("test", views.test, name="test"),
        path("download/<file_id>", views.download, name="download"),
        path("stream/<file_id>/key", views.streamkey, name="stream key"),
        path("stream/<file_id>", views.get_m3u8, name="get m3u8 playlist"),

] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
