import json
from typing import Optional

from .BaseConsumer import RateLimitedWebsocketConsumer
from .utils import send_event
from ..constants import EventCode
from ..core.Serializers import DeviceTokenSerializer
from ..core.dataModels.http import RequestContext
from ..core.dataModels.websocket import WebsocketEvent, WebsocketLogoutEvent
from ..core.deviceControl.DeviceControlState import DeviceControlState
from ..core.errors import DeviceControlBadStateError
from ..models import PerDeviceToken


class UserConsumer(RateLimitedWebsocketConsumer):
    connection_limit = 10        # how many new connections allowed

    message_limit = 30
    message_window = 30

    def __init__(self, *args, **kwargs):
        super().__init__(args, kwargs)
        self.token_obj = None
        self.device_id = None
        self.user = None
        self.token = None

    def get_token(self, raw_token) -> Optional[PerDeviceToken]:
        if not raw_token:
            return None

        token = PerDeviceToken.objects.get_token_from_raw_token(raw_token=raw_token)
        return token

    def get_group_name(self) -> str:
        return "user"

    def authorize(self) -> tuple[bool, bool, str]:
        token_key, is_standard_protocol = self.get_token_key()

        token = self.get_token(token_key)
        if not token:
            return False, is_standard_protocol, token_key

        self.user = token.user
        self.token_obj = token
        self.token = token_key
        self.device_id = self.token_obj.device_id
        return token.user.is_authenticated, is_standard_protocol, token_key

    def on_message(self, text_data=None, bytes_data=None):
        json_data = json.loads(text_data)
        op_code = json_data.get('op_code')

        if op_code == EventCode.DEVICE_CONTROL_REQUEST.value:
            self.handle_device_control_request(json_data)

        elif op_code == EventCode.DEVICE_CONTROL_STATUS.value:
            self.send_device_control_status()

        elif op_code == EventCode.DEVICE_CONTROL_REPLY.value:
            self.handle_device_control_reply(json_data)

        elif op_code == EventCode.DEVICE_CONTROL_COMMAND.value:
            self.handle_device_control_command(json_data)

    def on_accept(self):
        master_device_id = DeviceControlState.slave_has_pending(self.device_id)
        if master_device_id:
            self.send_device_control_pending(self.device_id)

        self.send_device_control_status()

    def send_event(self, event: WebsocketEvent):
        if self.user.id == event['context']['user_id'] and (not self.device_id or not event['context'].get('device_id') or self.device_id == event['context'].get('device_id')):
            self.send(json.dumps(event['ws_payload']))

    def logout(self, event: WebsocketLogoutEvent):
        if self.user.id == event['context']['user_id']:
            if event['device_id']:  # specific connection to close
                if self.device_id == event['device_id']:
                    self.close()
            else:  # close all connections
                self.close()

    def on_error(self, exception: Exception) -> bool:
        if isinstance(exception, DeviceControlBadStateError):
            self.send_error("errors." + str(exception))
            return True
        return False

    def get_context(self, device_id: str) -> RequestContext:
        context = RequestContext.from_user(self.user.id)
        context.device_id = device_id
        return context

    def handle_device_control_request(self, json_data: dict) -> None:
        slave_device_id = json_data['message']['device_id']
        DeviceControlState.create_pending(master_id=self.device_id, slave_id=slave_device_id)
        self.send_device_control_status(device_id=self.device_id)
        self.send_device_control_pending(slave_device_id)

    def handle_device_control_command(self, json_data: dict) -> None:
        if not DeviceControlState.master_has_active(master_id=self.device_id):
            raise DeviceControlBadStateError("notActiveMaster")

        slave_id = DeviceControlState.get_active_slave_for_master(master_id=self.device_id)

        context = self.get_context(slave_id)
        send_event(context, None, EventCode.DEVICE_CONTROL_COMMAND, json_data['message'])

    def send_device_control_pending(self, slave_device_id: str) -> None:
        """Sends a pending request from this device(master) to slave device"""
        context = self.get_context(slave_device_id)
        device = DeviceTokenSerializer().serialize_object(self.token_obj)
        expiry = DeviceControlState.get_status(slave_device_id)["expiry"]
        send_event(context, None, EventCode.DEVICE_CONTROL_REQUEST, {"master_device": device, "expiry": expiry})

    def send_device_control_status(self, device_id=None) -> None:
        """Sends current device control status to this device"""
        if not device_id:
            device_id = self.device_id
        context = self.get_context(device_id)
        send_event(context, None, EventCode.DEVICE_CONTROL_STATUS, DeviceControlState.get_status(device_id))

    def handle_device_control_reply(self, json_data: dict) -> None:
        device_id = self.device_id
        reply_type = json_data["message"]["type"]

        pending_master = DeviceControlState.master_has_pending(device_id)
        pending_slave = DeviceControlState.slave_has_pending(device_id)

        active_master = DeviceControlState.master_has_active(device_id)
        active_slave = DeviceControlState.slave_has_active(device_id)
        peer = DeviceControlState.get_status(device_id=self.device_id)["peer"]

        # --- 1) REJECT (slave rejects pending request) ---
        if reply_type == "reject" and pending_slave:
            DeviceControlState.reject_pending(master_id=pending_slave, slave_id=device_id)

        # --- 2) APPROVE (slave approves pending request) ---
        elif reply_type == "approve":
            if pending_slave:
                DeviceControlState.approve_pending(master_id=pending_slave, slave_id=device_id)
            else:
                from ..tasks.helper import send_message

                send_message(message="toasts.deviceControlApprovedFailed", args=None, finished=True, context=self.get_context(device_id), isError=True)

        # --- 3) CANCEL (master cancels pending) ---
        elif reply_type == "cancel":
            if pending_master:
                DeviceControlState.clear_pending(master_id=device_id, slave_id=pending_master)

        # --- 4) STOP (end active session) ---
        elif reply_type == "stop":
            # End active session regardless of direction
            if active_master:
                DeviceControlState.stop_active(master_id=device_id, slave_id=active_master)

            if active_slave:
                DeviceControlState.stop_active(master_id=active_slave, slave_id=device_id)

        # send current status to both
        self.send_device_control_status(device_id=device_id)
        self.send_device_control_status(device_id=peer)
