from django.urls import path

from streamer.views import stream_file, thumbnail_file, stream_zip_files, stream_nonzip_files

#from streamer.views import preview_file

urlpatterns = [
    path('stream/<signed_file_id>', stream_file),
    path('thumbnail/<signed_file_id>', thumbnail_file),
    path('zip/<token>', stream_zip_files),
    path('nonzip', stream_nonzip_files),

]
