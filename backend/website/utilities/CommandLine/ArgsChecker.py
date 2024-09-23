from .ArgumentException import IncorrectArgumentError


def requireExactly(param, args):
    if len(args) != param:
        raise IncorrectArgumentError(f"Incorrect number of arguments. Expected exactly {param} but got {len(args)}")


def requireAtLeast(param, args):
    if len(args) < param:
        raise IncorrectArgumentError(f"Incorrect number of arguments. Expected at least {param} but got {len(args)}")


def requireNoMoreThan(param, args):
    if len(args) > param:
        raise IncorrectArgumentError(f"Incorrect number of arguments. Expected no more than {param} but got {len(args)}")
