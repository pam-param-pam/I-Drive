from colorama import Fore, Style

from website.utilities.CommandLine.Commands import HelpCommand, LsCommand, CdCommand


class ArgumentParser:
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

    def parse_arguments(self, input_str):

        try:

            input_list = input_str.split()

            prefix = input_list[0].lower()

            for command in self.commands:
                if prefix == command.getName():
                    args = input_list[1:]
                    for chunk in command.execute(args, self.commandLineState):
                        yield chunk
                    return

            else:
                yield "Command not found\nUse 'help' for help"
        except IndexError:
            yield "Command not found\nUse 'help' for help"

