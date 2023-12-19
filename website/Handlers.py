# -*- coding: utf-8 -*-
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.cache import cache
from django.core.files.uploadhandler import TemporaryFileUploadHandler

from website.utilities.other import get_percentage


# copied from http://djangosnippets.org/snippets/678/

class ProgressBarUploadHandler(TemporaryFileUploadHandler):
    """
    Cache system for TemporaryFileUploadHandler
    """
    def __init__(self, *args, **kwargs):
        super(TemporaryFileUploadHandler, self).__init__(*args, **kwargs)
        self.received = 0
        self.percentage = None
    def handle_raw_input(self, input_data, META, content_length, boundary, encoding=None):

        self.content_length = content_length

    def new_file(self, field_name, file_name, content_type, content_length, charset=None, content_typ_extra=None):
        self.original_file_name = file_name

    def receive_data_chunk(self, raw_data, start):

        self.received += self.chunk_size

        channel_layer = get_channel_layer()
        new_percentage = get_percentage(self.received, self.content_length)

        if self.percentage != new_percentage:
            async_to_sync(channel_layer.group_send)(
                'test',
                {
                    'type': 'chat_message',
                    # 'user_id': user_id,
                    'message': f"uploading {new_percentage}%"
                }
            )
        self.percentage = new_percentage
        return raw_data

    def file_complete(self, file_size):
        pass

    def upload_complete(self):
        # deprecated in favor of setting an expiry time a-la-nginx
        # setting an expiry time fixes the race condition in which the last
        # progress request happens after the upload has finished meaning the
        # bar never gets to 100%
        pass
        #if self.cache_key:
        #    cache.delete(self.cache_key)