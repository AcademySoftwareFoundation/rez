"""
This class needs to be in its own source file due to the way Yapsy works. Do not
place any other IPlugin-derived subclasses within this source file.
"""
from yapsy.IPlugin import IPlugin


class RezPluginFactory(IPlugin):
    """Pure abstract class for creating a plugin instance.
    """
    def target_type(self):
        """Override this function to return the type this factory creates"""
        raise NotImplementedError

    def name(self):
        """Returns The name of the plugin type this factory creates."""
        return self.target_type().name()
