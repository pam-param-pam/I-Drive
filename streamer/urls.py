from django.urls import path

from streamer.views import stream_file
#from streamer.views import preview_file

urlpatterns = [
    path('stream/<signed_file_id>', stream_file),
    #path('preview/<signed_file_id>', preview_file),

]
