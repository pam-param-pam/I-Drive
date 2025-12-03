from httpx import Response

from ..core.deviceControl.constants import ErrorType


class IDriveException(Exception):
    """A base class for all I Drive exceptions."""

class MalformedDatabaseRecord(IDriveException):
    """Raised when data is malformed in the database."""

class ResourceNotFoundError(IDriveException):
    """Raised when resource can't be found in the database"""

class ResourcePermissionError(IDriveException):
    """Raised when user has not enough privilege to access a resource"""

class BadRequestError(IDriveException):
    """Raised when user's request has some bad/missing data in it"""

class NoBotsError(IDriveException):
    """Raised when user's has no bots and tries to fetch files"""

class RootPermissionError(IDriveException):
    """Raised when user tries to manage 'root' folder"""

class HttpxError(IDriveException):
    """Raised when httpx fails"""

class CannotProcessDiscordRequestError(IDriveException):
    """Raised when we are unable to make requests to discord due to being overloaded"""

class FailedToResizeImageError(IDriveException):
    """Raised when we are unable to resize an image for unknown reasons"""

class LockedFolderWrongIpError(IDriveException):
    """Raised when locked folder is trying to be accessed from wrong IP"""
    def __init__(self, ip):
        self.ip = ip

class DiscordBlockError(IDriveException):
    """Raised when discord blocks us for whatever reason"""
    def __init__(self, message, retry_after):
        self.message = message
        self.retry_after = retry_after
        super().__init__(self.message)

class DeviceControlBadStateError(IDriveException):
    """Raised when attempted to do something illegal with device control state"""
    def __init__(self, code: ErrorType):
        self.code = code

    def __str__(self):
        return self.code

class DiscordTextError(IDriveException):
    def __init__(self, message, status):
        self.status = status
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return f'Discord error-> {self.status}: {self.message}'

class DiscordError(IDriveException):
    def __init__(self, response: Response):
        self.status = response.status_code
        self._json_error = response.json()
        self.message = self._json_error['message']
        self.code = self._json_error['code']
        super().__init__(self.message)

    def __str__(self):
        return f'Discord error-> {self.status}: {self.message}'

class MissingOrIncorrectResourcePasswordError(IDriveException):
    """Raised when password for a resource is missing"""
    def __init__(self, requiredPasswords, message="Resource password is missing or incorrect"):
        self.requiredPasswords = requiredPasswords
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return self.message
