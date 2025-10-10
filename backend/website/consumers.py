import hashlib
import json
import threading

from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer

from .utilities.constants import QR_CODE_SESSION_EXPIRY


class UserConsumer(WebsocketConsumer):

    def connect(self):
        is_standard_protocol = self.scope['is_standard_protocol']
        user = self.scope['user']
        if not user.is_anonymous:
            async_to_sync(self.channel_layer.group_add)("user", self.channel_name)
            if is_standard_protocol:
                self.accept()
            else:
                self.accept(self.scope['token'])
        else:
            self.close(code=4001)

    def disconnect(self, close_code):
        async_to_sync(self.channel_layer.group_discard)("user", self.channel_name)

    def send_message(self, event):
        if self.scope['user'].id == event['user_id']:
            message = {"is_encrypted": False, "event": {"op_code": event['op_code'], "message": event["message"], "args": event.get('args'), "error": event["error"],
                       "finished": event["finished"]}}

            task_id = event.get("request_id")
            if task_id:
                message['event']['task_id'] = task_id

            self.send(json.dumps(message))

    def send_event(self, event):
        if self.scope['user'].id == event['user_id']:
            self.send(json.dumps(event['message']))

    def logout(self, event):
        if self.scope['user'].id == event['user_id']:
            if event['token_hash']:  # specific connection to close
                token_hash = hashlib.sha256(self.scope['token'].encode()).hexdigest()
                if token_hash == event['token_hash']:
                    self.close()
            else:  # close all connections
                self.close()


class QrLoginConsumer(WebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(args, kwargs)
        self.close_timer = None
        self.group_name = None
        self.session_data = None
        self.session_id = None

    def connect(self):
        self.session_id = self.scope.get('session_id')
        self.session_data = self.scope.get('session_data')

        if not self.session_id or not self.session_data:
            self.close(code=4001)
            return

        async_to_sync(self.channel_layer.group_add)("qrcode", self.channel_name)
        self.accept(self.scope['session_id'])

        self.close_timer = threading.Timer(QR_CODE_SESSION_EXPIRY + 5, lambda: self.close(code=4000))
        self.close_timer.start()

    def disconnect(self, close_code):
        async_to_sync(self.channel_layer.group_discard)("qrcode", self.channel_name)

    def approve_session(self, event):
        if event['session_id'] == self.session_id:
            self.send(text_data=json.dumps(event['message']))
            self.close(code=4000)
