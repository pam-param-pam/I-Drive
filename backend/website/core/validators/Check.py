from django.core.exceptions import ValidationError

class Check:
    def check(self, value):
        raise NotImplementedError

    def is_number_type(self, value):
        return isinstance(value, (int, float)) and not isinstance(value, bool)

    def __call__(self, value):
        if not self.check(value):
            raise ValidationError(f"Failed on {self} with {value!r}")
        return True

    def __and__(self, other):
        return AndCheck(self, other)

    def __or__(self, other):
        return OrCheck(self, other)

    def __invert__(self):
        return NotCheck(self)

    def __repr__(self):
        return self.__class__.__name__

class AndCheck(Check):
    def __init__(self, a: Check, b: Check):
        self.a = a
        self.b = b

    def check(self, value):
        return self.a.check(value) and self.b.check(value)

    def __repr__(self):
        return f"({self.a} AND {self.b})"


class OrCheck(Check):
    def __init__(self, a: Check, b: Check):
        self.a = a
        self.b = b

    def check(self, value):
        return self.a.check(value) or self.b.check(value)

    def __repr__(self):
        return f"({self.a} OR {self.b})"


class NotCheck(Check):
    def __init__(self, a: Check):
        self.a = a

    def check(self, value):
        return not self.a.check(value)

    def __repr__(self):
        return f"(NOT {self.a})"
