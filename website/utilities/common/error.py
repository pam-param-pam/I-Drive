#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
from json import JSONDecodeError


class IDriveException(Exception):
    """A base class for I Drive exceptions."""


class ResourceNotFound(IDriveException):
    """Raised when resource can't be found in the database"""
    pass


class ResourcePermissionError(IDriveException):
    """Raised when user has not enough privilege to access a resource"""
    pass


class BadRequestError(IDriveException):
    """Raised when user request has some bad/missing data in it"""
    pass


class RootPermissionError(IDriveException):
    """Raised when user tries to manage 'root' folder"""
    pass

class DiscordBlockError(IDriveException):
    """Raised when discord blocks us for whatever reason"""
    pass
class DiscordError(IDriveException):
    def __init__(self, message="Unexpected Discord Error.", status=0):
        self.status = status
        try:
            json_message = json.loads(message)

            self.message = json_message.get("message")
        except (JSONDecodeError, KeyError):
            print(message)
            self.message = "Unknown"

        super().__init__(self.message)

    def __str__(self):
        return f'Discord error-> {self.status}: {self.message}'
