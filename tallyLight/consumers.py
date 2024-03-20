import json
import time

from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer


class TallyConsumer(WebsocketConsumer):

    def connect(self):
        user = self.scope['user']
        if user.superuser:
            async_to_sync(self.channel_layer.group_add)("tally", self.channel_name)
            self.accept(self.scope['token'])

    def disconnect(self, close_code):
        async_to_sync(self.channel_layer.group_discard)("tally", self.channel_name)

    def receive(self, text_data=None, bytes_data=None):
        pass

    def chat_message(self, event):
        self.send(json.dumps({"message": event["message"], "error": event["error"], "finished": event["finished"],
                              "task_id": event["request_id"]}))


class AtemConsumer(WebsocketConsumer):

    def connect(self):
        user = self.scope['user']
        if user.superuser:
            async_to_sync(self.channel_layer.group_add)("test", self.channel_name)
            self.accept(self.scope['token'])

    def disconnect(self, close_code):
        async_to_sync(self.channel_layer.group_discard)("test", self.channel_name)

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
