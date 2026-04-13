from json import JSONDecodeError

from httpx import Response

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

class RangeNotSatisfiable(IDriveException):
    """Raised when the supplied header range is not satisfiable"""

class UsernameTakenError(IDriveException):
    """Raised on register, when a user with this username already exists"""

class URLInvalidOrExpired(IDriveException):
    """Raised when signed url is not valid or expired"""

class RootFolderError(IDriveException):
    """Raised when user has no root folder or has multiple root"""

class DiscordBotAttachmentAuthor(IDriveException):
    """Raised when a bot is a message author. This should not happen"""

class FailedToParseRawImage(IDriveException):
    """Raised when metadata extraction fails for a raw image"""

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
        self.response = response
        self.code = None
        headers = response.headers

        try:
            self._json_error = response.json()
            self.message = self._json_error.get('message') or self._json_error
            self.code = self._json_error.get('code')
        except JSONDecodeError:
            self.message = self.response.text[:200]
            pass

        self.retry_after = self._parse_float(headers.get("X-RateLimit-Reset-After")) or 5
        super().__init__(self.message)

    @staticmethod
    def _parse_float(v):
        try:
            return float(v) if v is not None else None
        except Exception:
            return None

    def __str__(self):
        return f'Discord error-> {self.status}: {self.message}\ncode={self.code}'

class DiscordErrorMaxRetries(IDriveException):
    def __init__(self, errors: list[Response]):
        self.errors = errors

    def __str__(self):
        lines = []

        for idx, res in enumerate(self.errors, start=1):
            try:
                body_preview = res.text
                if len(body_preview) > 300:
                    body_preview = body_preview[:300] + "…"
            except:
                body_preview = "<no body>"

            lines.append(
                f"Attempt {idx}: "
                f"status={res.status_code} "
                f"body={body_preview}"
            )

        return "\n".join(lines)

class MissingOrIncorrectResourcePasswordError(IDriveException):
    """Raised when password for a resource is missing"""
    def __init__(self, requiredPasswords, message="Resource password is missing or incorrect"):
        self.requiredPasswords = requiredPasswords
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return self.message
