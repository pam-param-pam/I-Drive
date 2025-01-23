import json
import traceback

from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer

from .models import UserPerms
from .utilities.CommandLine.ArgumentException import IncorrectArgumentError
from .utilities.CommandLine.CommandParser import CommandParser
from .utilities.errors import IDriveException


class UserConsumer(WebsocketConsumer):

    def connect(self):
        user = self.scope['user']
        if not user.is_anonymous:
            async_to_sync(self.channel_layer.group_add)("user", self.channel_name)
            self.accept(self.scope['token'])
        else:
            self.close()

    def disconnect(self, close_code):
        async_to_sync(self.channel_layer.group_discard)("user", self.channel_name)

    def receive(self, text_data=None, bytes_data=None):
        pass

    def send_message(self, event):

        if self.scope['user'].id == event['user_id']:
            message = {"op_code": event['op_code'], "message": event["message"], "args": event.get('args'), "error": event["error"],
                       "finished": event["finished"]}
            task_id = event.get("request_id")
            if task_id:
                message['task_id'] = task_id

            self.send(json.dumps(message))

    def send_event(self, event):
        if self.scope['user'].id == event['user_id']:
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
        if user.is_anonymous:
            self.close()
        else:
            self.accept()
            async_to_sync(self.channel_layer.group_add)("command", self.channel_name)
            self.parser = CommandParser(self.commandLineState)

    def disconnect(self, close_code):
        async_to_sync(self.channel_layer.group_discard)("command", self.channel_name)

    def receive(self, text_data=None, bytes_data=None):
        """
        command protocol is made from json messages each representing a different command
        An example json message can look like this:
        {"cmd_name": string, "args": list[string], "working_dir_id": string}
        then the server sends replies in this format:
        {"type": string, "message: string, "action" {"type": "", "args": {} } }
        """

        perms = UserPerms.objects.get(user=self.scope['user'])
        if (not (perms.execute or perms.admin)) or perms.globalLock:
            self.send("Permission Denied\nYou are not allowed to perform this action")
            self.close()
            return
        try:

            for chunk in self.parser.process_command(text_data):
                self.send(chunk)

        except IncorrectArgumentError as e:
            self.send(str(e))

        # Intentionally broad, don't annoy me
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
