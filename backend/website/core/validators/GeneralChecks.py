import re

from website.config import MAX_RESOURCE_NAME_LENGTH
from website.core.validators.Check import Check


class NotEmpty(Check):
    def check(self, value) -> bool:
        return value != ""

class NotNull(Check):
    def check(self, value) -> bool:
        return value is not None

class IsPositive(Check):
    def check(self, value: int) -> bool:
        return self.is_number_type(value) and value > 0

class NotNegative(Check):
    def check(self, value: int) -> bool:
        return self.is_number_type(value) and value >= 0

class IsSnowflake(Check):
    DISCORD_SNOWFLAKE_MAX = 9223372036854775807  # 2^63 - 1

    def check(self, value: str) -> bool:
        if not isinstance(value, str):
            return False

        if not value.isdigit():
            return False

        length = len(value)
        if length < 17 or length > 19:
            return False

        num = int(value)
        if num < 0 or num > self.DISCORD_SNOWFLAKE_MAX:
            return False

        return True

class IsNonEmptyString(Check):
    def check(self, value: str) -> bool:
        return isinstance(value, str) and len(value.strip()) > 0

class NoSpaces(Check):
    def check(self, value: str) -> bool:
        return isinstance(value, str) and " " not in value

class MaxLength(Check):
    def __init__(self, max_length: int | float):
        self.max_length = max_length

    def check(self, value):
        if self.is_number_type(value):
            value = str(value)

        if not isinstance(value, str):
            return False

        return len(value) <= self.max_length

class Max(Check):
    def __init__(self, max_value: int | float):
        self.max_value = max_value

    def check(self, value):
        if not self.is_number_type(value):
            return False

        return value <= self.max_value

class Min(Check):
    def __init__(self, min_value: int | float):
        self.min_value = min_value

    def check(self, value):
        if not self.is_number_type(value):
            return False

        return value >= self.min_value

class RequireLength(Check):
    def __init__(self, length: int | float):
        self.length = length

    def check(self, value):
        if self.is_number_type(value):
            value = str(value)

        if not isinstance(value, str):
            return False

        return len(value) == self.length

class IsValidItemName(Check):
    def check(self, value):
        WINDOWS_RESERVED_NAMES = {
            "CON", "PRN", "AUX", "NUL",
            *(f"COM{i}" for i in range(1, 10)),
            *(f"LPT{i}" for i in range(1, 10)),
        }

        INVALID_CHARS_PATTERN = re.compile(r'[<>:"/\\|?*\x00-\x1F]')
        DRIVE_PATTERN = re.compile(r'^[a-zA-Z]:[/\\]')  # e.g. C:\ or Z:/

        if not value:
            return False

        stripped = value.strip()

        # 1. Block full paths / drive references (e.g. Z://, C:\foo)
        if DRIVE_PATTERN.match(stripped):
            return False

        # block any path separators at all
        if "/" in value or "\\" in value:
            return False

        # 2. Reserved device names (case-insensitive)
        base = stripped.split(".")[0].upper()
        if base in WINDOWS_RESERVED_NAMES:
            return False

        # 3. Invalid characters
        if INVALID_CHARS_PATTERN.search(value):
            return False

        # 4. Cannot end with space or dot (Windows rule)
        if stripped.rstrip(" .") != stripped:
            return False

        # 5. Avoid '.' and '..'
        if stripped in {".", ".."}:
            return False

        if len(value) > MAX_RESOURCE_NAME_LENGTH:
            return False

        # bare drive
        if re.match(r'^[a-zA-Z]:$', stripped):
            return False

        return True
