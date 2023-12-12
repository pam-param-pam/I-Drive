from channels.generic.websocket import WebsocketConsumer



class UserConsumer(WebsocketConsumer):
    def connect(self):
        pass

    def disconnect(self, close_code):
        pass

    def receive(self, text_data=None, bytes_data=None):
        pass

    def chat_message(self, event):
        pass
