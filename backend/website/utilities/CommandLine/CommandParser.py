import json

from colorama import Fore, Style

from website.utilities.CommandLine.Commands import HelpCommand, LsCommand, CdCommand


class CommandParser:
    def __init__(self, commandLineState):
        self.commands = []
        self.commandLineState = commandLineState
        self.register_command_class(HelpCommand(self.commands, "help"))
        self.register_command_class(LsCommand(self.commands, "ls"))
        self.register_command_class(CdCommand(self.commands, "cd"))

    def get_commands(self):
        return self.commands

    def register_command_class(self, command):
        self.commands.append(command)

    def process_command(self, command_message):
        """command_message: {"cmd_name": string, "args": list[string], "working_dir_id": string}"""
        json_command = json.loads(command_message)
        cmd_name = json_command["cmd_name"]
        args = json_command["args"]
        working_dir_id = json_command["working_dir_id"]

        try:
            cmd_name = cmd_name.lower()

            for command in self.commands:
                if cmd_name == command.getName():
                    for chunk in command.execute(args, working_dir_id):
                        yield chunk
                    return

            else:
                yield "Command not found\nUse 'help' for help"
        except IndexError:
            yield "Command not found\nUse 'help' for help"

