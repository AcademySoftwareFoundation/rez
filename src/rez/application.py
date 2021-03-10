
from rez.config import config


class Application(object):
    """An interface for registering custom Rez application/subcommand"""
    def __init__(self):
        self.type_settings = config.plugins.application
        self.settings = self.type_settings.get(self.name())

    @classmethod
    def name(cls):
        """Return the name of the Application and rez-subcommand."""
        raise NotImplementedError
