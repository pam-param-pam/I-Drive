from dataclasses import dataclass

from website.core.errors import MissingOrIncorrectResourcePasswordError


@dataclass(frozen=True)
class PasswordChallenge:
    id: str
    name: str


class PermissionPasswordError(MissingOrIncorrectResourcePasswordError):
    def __init__(self, challenges: tuple[PasswordChallenge, ...], message: str = "Resource password is missing or incorrect"):
        self.challenges = challenges
        super().__init__([{"id": challenge.id, "name": challenge.name} for challenge in challenges], message)
