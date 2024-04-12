import json
import time

from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer


class UserConsumer(WebsocketConsumer):

    def connect(self):
        user = self.scope['user']
        if not user.is_anonymous:
            async_to_sync(self.channel_layer.group_add)("user", self.channel_name)
            self.accept(self.scope['token'])

    def disconnect(self, close_code):
        async_to_sync(self.channel_layer.group_discard)("user", self.channel_name)

    def receive(self, text_data=None, bytes_data=None):
        pass

    def send_message(self, event):

        if self.scope['user'].id == event['user_id']:
            self.send(json.dumps({"op_code": event['op_code'], "message": event["message"], "error": event["error"], "finished": event["finished"],
                                  "task_id": event["request_id"]}))

    def send_event(self, event):

        if self.scope['user'].id == event['user_id']:
            self.send(json.dumps({"op_code": event['op_code'], "data": event['data']}))


class CommandConsumer(WebsocketConsumer):

    def connect(self):
        user = self.scope['user']
        if not user.is_anonymous:
            async_to_sync(self.channel_layer.group_add)("command", self.channel_name)
            self.accept(self.scope['token'])

    def disconnect(self, close_code):
        async_to_sync(self.channel_layer.group_discard)("command", self.channel_name)

    def receive(self, text_data=None, bytes_data=None):
        print(text_data)
        if "sudo" in text_data:
            self.send("hecking white house...")
            time.sleep(1)
            self.send("Obama's last name is...")
            time.sleep(3)
            self.send("Connection terminated by Illuminati")
        else:
            self.send("Sending 100 nukes to your location.")

        self.close()
