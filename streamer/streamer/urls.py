from django.urls import path


from streamer.views import stream_file, thumbnail_file, stream_zip_files, index

urlpatterns = [
    path('get/', index),
    path('get/stream/<signed_file_id>', stream_file),
    path('get/thumbnail/<signed_file_id>', thumbnail_file),
    path('get/zip/<token>', stream_zip_files),
]
