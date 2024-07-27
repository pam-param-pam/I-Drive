import time

from website.models import Folder
from website.utilities.CommandLine.ArgsChecker import requireExactly
from website.utilities.CommandLine.ArgumentException import IncorrectArgumentError
from website.utilities.CommandLine.Command import Command
from website.utilities.other import build_folder_content


class HelpCommand(Command):
    def __init__(self, commands, name):
        super().__init__(name)
        self.commands = commands

    shortDesc = "Displays information about available commands"
    longDesc = "The `help` command displays information about available commands.\n If given an argument, it will display the long description of the specified command.\n Otherwise, it will display a list of available commands and their short descriptions."

    def execute(self, args, commandLineState):
        if len(args) > 0:
            for command in self.commands:
                if args[0] in command.getName():
                    yield command.getLongDesc()
                    return
            IncorrectArgumentError("Command not found")
        else:
            yield "Available commands:"
            for command in self.commands:
                yield f"{command.getName()}: {command.getShortDesc()}"


class LsCommand(Command):
    def __init__(self, commands, name):
        super().__init__(name)
        self.commands = commands

    shortDesc = "Displays all files in given directory"
    longDesc = "TODO"

    def execute(self, args, commandLineState):
        requireExactly(0, args)
        folder_obj = Folder.objects.get(id=commandLineState["folder_id"])

        folder_content = build_folder_content(folder_obj)
        for item in folder_content["children"]:
            yield "> " + item["name"]
            time.sleep(0.05)


class CdCommand(Command):
    def __init__(self, commands, name):
        super().__init__(name)
        self.commands = commands

    shortDesc = "Moves in a directories, takes an argument"
    longDesc = "TODO"

    def execute(self, args, commandLineState):
        requireExactly(1, args)
        folder_obj = Folder.objects.filter(name=args[0], parent__id=commandLineState["folder_id"]).first()
        print(folder_obj)
        commandLineState["folder_id"] = folder_obj.id
        yield "Done"
