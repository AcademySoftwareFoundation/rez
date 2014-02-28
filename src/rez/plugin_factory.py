# This needs to be in its own source file due to the way Yapsy works.
from yapsy.IPlugin import IPlugin


class RezPluginFactory(IPlugin):
    """
    Pure abstract class for creating a plugin instance.
    """
    #__metaclass__ = abc.ABCMeta

    def target_type(self):
        """ Override this function to return the type this factory creates. """
        raise NotImplementedError

    def name(self):
        """ @returns The name of the plugin type this factory creates. """
        return self.target_type().name()
