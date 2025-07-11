class IDriveException(Exception):
    """A base class for all I Drive exceptions."""

class MalformedDatabaseRecord(Exception):
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

class DiscordBlockError(IDriveException):
    """Raised when discord blocks us for whatever reason"""
    def __init__(self, message, retry_after):
        self.message = message
        self.retry_after = retry_after
        super().__init__(self.message)

class CannotProcessDiscordRequestError(IDriveException):
    """Raised when we are unable to make requests to discord due to being overloaded"""

class FailedToResizeImage(IDriveException):
    """Raised when we are unable to resize an image for unknown reasons"""

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
