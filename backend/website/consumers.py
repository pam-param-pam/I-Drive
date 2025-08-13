import hashlib
import json

from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer

from .utilities.constants import EventCode


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
            self.close()

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
        print(f"SENT_EVENT: {EventCode(event['message']['event']['op_code'])}")
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
