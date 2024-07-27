from website.utilities.errors import IDriveException


class IncorrectArgumentError(IDriveException):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return self.message
