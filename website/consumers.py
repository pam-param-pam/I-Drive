from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer


class UserConsumer(WebsocketConsumer):
    def connect(self):
        user = self.scope['user']
        if not user.is_anonymous:
            async_to_sync(self.channel_layer.group_add)("test", self.channel_name)
            print(self.channel_name)
            self.accept()

    def disconnect(self, close_code):
        async_to_sync(self.channel_layer.group_discard)("test", self.channel_name)

    def receive(self, text_data=None, bytes_data=None):
        pass

    def chat_message(self, event):
        print(event)
        self.send(text_data=event['message'])

