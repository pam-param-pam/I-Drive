from django.urls import path

# from streamer.testViews import DecryptFileView
# from streamer.testViewsV2 import DecryptFileView2
from streamer.views import stream_file, thumbnail_file, stream_zip_files, index

#from streamer.views import preview_file

urlpatterns = [
    path('', index),
    path('stream/<signed_file_id>', stream_file),
    path('thumbnail/<signed_file_id>', thumbnail_file),
    path('zip/<token>', stream_zip_files),
    # path('decrypt-file', DecryptFileView.as_view(), name='decrypt-file'),
    # path('decrypt-file2', DecryptFileView2.as_view(), name='decrypt-file'),

]
