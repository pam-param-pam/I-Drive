import json
import time

from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer

from website.models import Folder, UserPerms
from website.utilities.OPCodes import EventCode
from website.utilities.other import build_folder_content, send_event


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
        print("send event1")

        print(self.scope['user'].id)
        print(event['user_id'])
        if self.scope['user'].id == event['user_id']:
            print("send event")
            self.send(json.dumps({"op_code": event['op_code'], "data": event['data']}))


class CommandConsumer(WebsocketConsumer):

    def connect(self):
        user = self.scope['user']
        if not user.is_anonymous:

            perms = UserPerms.objects.get(user=user)
            if not perms.execute:
                self.close()
                return

            async_to_sync(self.channel_layer.group_add)("command", self.channel_name)
            self.accept(self.scope['token'])

    def disconnect(self, close_code):
        async_to_sync(self.channel_layer.group_discard)("command", self.channel_name)

    def receive(self, text_data=None, bytes_data=None):
        json_data = json.loads(text_data)
        current_folder = json_data["current_folder_id"]
        command = json_data["command"]
        item_names = []
        if command == "ls":
            folder_obj = Folder.objects.get(id=current_folder)
            folder_content = build_folder_content(folder_obj, False)
            print(folder_content)
            for item in folder_content["children"]:
                item_names.append("> " + item["name"])

        dir_content = '\n'.join(item_names)
        self.send(dir_content)
        if command == "cd":
            print("cd1")
            send_event(self.scope['user'].id, EventCode.FORCE_FOLDER_NAVIGATION, "0000", {"folder_id": "8x9XURqmWZYcCaExwk6vnB"})
            print("cd2")

        self.close()
