from django.urls import path


from .views import stream_file, stream_zip_files, index

urlpatterns = [
    path('', index),
    path('stream/<signed_file_id>', stream_file),
    path('zip/<token>', stream_zip_files),
]
