from abc import ABC, abstractmethod


class Command(ABC):

    def __init__(self, name):
        self.name = name

    @property
    @abstractmethod
    def longDesc(self):
        raise NotImplementedError

    @property
    @abstractmethod
    def shortDesc(self):
        raise NotImplementedError

    @abstractmethod
    def execute(self, args, commandLineState):
        raise NotImplementedError

    def getName(self):
        return self.name

    def getLongDesc(self):
        return self.longDesc

    def getShortDesc(self):
        return self.shortDesc

    def __eq__(self, other):
        return other == self.getName()

    def __repr__(self):
        return self.getName()
