import json
import traceback

from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer

from website.models import Folder, UserPerms
from website.utilities.CommandLine.ArgumentException import IncorrectArgumentError
from website.utilities.CommandLine.ArgumentParser import ArgumentParser
from website.utilities.errors import IDriveException

# todo i think we should check if token is still valid every now and then just in case
# maybe create a base class for websocket consumer thats also includes logout method
class TallyConsumer(WebsocketConsumer):
    def connect(self):
        print(self.scope['headers'])
        # if dict(self.scope['headers']).get(b'sec-websocket-protocol') == "TALLY_KOCHAM_ALTERNATYWKI":
        self.accept()
        async_to_sync(self.channel_layer.group_add)("tally", self.channel_name)

        async_to_sync(self.channel_layer.group_send)("atem", {
            "type": "send_message",
            "data": {"op": 4, "t": -1, "d": "NEW TALLY CONNECTED"}
        })

    def disconnect(self, close_code):
        async_to_sync(self.channel_layer.group_discard)("tally", self.channel_name)

    def receive(self, text_data=None, bytes_data=None):
        async_to_sync(self.channel_layer.group_send)("atem", {
            "type": "send_message",
            "data": json.loads(text_data),
        })

    def send_message(self, event):
        self.send(event["data"])


class AtemConsumer(WebsocketConsumer):
    def connect(self):
        try:
            print(dict(self.scope['headers'])[b'authorization'].decode('utf-8'))
            if dict(self.scope['headers'])[b'authorization'].decode('utf-8') == "1234":
                self.accept()
                async_to_sync(self.channel_layer.group_add)("atem", self.channel_name)
        except (KeyError, ValueError):
            self.close()

    def disconnect(self, close_code):
        async_to_sync(self.channel_layer.group_discard)("atem", self.channel_name)

    def receive(self, text_data=None, bytes_data=None):
        async_to_sync(self.channel_layer.group_send)("tally", {
            "type": "send_message",
            "data": text_data,
        })

    def send_message(self, event):
        self.send(json.dumps(event["data"]))


class UserConsumer(WebsocketConsumer):

    def connect(self):
        user = self.scope['user']
        print(user)
        if not user.is_anonymous:
            async_to_sync(self.channel_layer.group_add)("user", self.channel_name)
            self.accept(self.scope['token'])
        else:
            self.close()

    def disconnect(self, close_code):
        print("disscconect")
        async_to_sync(self.channel_layer.group_discard)("user", self.channel_name)

    def receive(self, text_data=None, bytes_data=None):
        pass

    def send_message(self, event):

        if self.scope['user'].id == event['user_id']:
            self.send(json.dumps({"op_code": event['op_code'], "message": event["message"], "error": event["error"],
                                  "finished": event["finished"],
                                  "task_id": event["request_id"]}))

    def send_event(self, event):
        print("send event")

        print(event['op_code'])
        if self.scope['user'].id == event['user_id']:
            print("send event")
            self.send(json.dumps({"op_code": event['op_code'], "data": event['data']}))

    def logout(self, event):
        if self.scope['user'].id == event['user_id']:
            self.close()


class CommandConsumer(WebsocketConsumer):

    def __init__(self, *args, **kwargs):
        super().__init__(args, kwargs)
        self.parser = None
        self.commandLineState = {}

    def connect(self):
        user = self.scope['user']
        if not user.is_anonymous:
            async_to_sync(self.channel_layer.group_add)("command", self.channel_name)
            self.accept(self.scope['token'])
            root_folder = Folder.objects.get(owner=user, parent=None)
            self.commandLineState["folder_id"] = root_folder.id
            self.parser = ArgumentParser(self.commandLineState)
        else:
            self.close()

    def disconnect(self, close_code):
        async_to_sync(self.channel_layer.group_discard)("command", self.channel_name)

    def receive(self, text_data=None, bytes_data=None):
        perms = UserPerms.objects.get(user=self.scope['user'])
        if (not (perms.execute or perms.admin)) or perms.globalLock:
            self.send("Permission Denied\nYou are not allowed to perform this action")
            self.close()
            return
        try:
            json_data = json.loads(text_data)
            command = json_data["command"]
            for chunk in self.parser.parse_arguments(command):
                self.send(chunk)

        except IncorrectArgumentError as e:
            self.send(str(e))

        # Intentionally broad, dont annoy me
        except (ValueError, KeyError, IDriveException) as error:
            etype = type(error)
            trace = error.__traceback__
            lines = traceback.format_exception(etype, error, trace)
            traceback_text = ''.join(lines)
            self.send(traceback_text)

        finally:
            self.close()

    def logout_and_close(self, event):
        if self.scope['user'].id == event['user_id']:
            self.close()
