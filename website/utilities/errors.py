import json
from json import JSONDecodeError


class IDriveException(Exception):
    """A base class for all I Drive exceptions."""


class ResourceNotFoundError(IDriveException):
    """Raised when resource can't be found in the database"""


class ResourceNotPreviewableError(IDriveException):
    """Raised when resource is too big to be previewed, or file is too corrupted to generate a preview"""


class ThumbnailAlreadyExistsError(IDriveException):
    """Raised during creation of file thumbnail but one already exists for that file"""

class ResourcePermissionError(IDriveException):
    """Raised when user has not enough privilege to access a resource"""


class MissingResourcePasswordError(IDriveException):
    """Raised when password for a resource is missing"""
    def __init__(self, lockFrom, resourceId, message="Resource password is missing"):
        self.lockFrom = lockFrom
        self.resourceId = resourceId
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return self.message


class BadRequestError(IDriveException):
    """Raised when user's request has some bad/missing data in it"""


class RootPermissionError(IDriveException):
    """Raised when user tries to manage 'root' folder"""


class DiscordBlockError(IDriveException):
    """Raised when discord blocks us for whatever reason"""


class DiscordError(IDriveException):
    def __init__(self, message="Unexpected Discord Error.", status=0):
        self.status = status
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return f'Discord error-> {self.status}: {self.message}'


class MissingOrIncorrectResourcePasswordError(IDriveException):
    """Raised when password for a resource is missing"""
    def __init__(self, requiredPasswords, message="Resource password is missing"):
        self.requiredPasswords = requiredPasswords
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return self.message
