from rez import plugin_factory
from rez.shells import UnixShell
from rez.plugins.shell.csh import CSH



class TCSH(CSH):
    executable = UnixShell.find_executable('tcsh')

    @classmethod
    def name(cls):
        return 'tcsh'


class TCSHFactory(plugin_factory.RezPluginFactory):
    def target_type(self):
        return TCSH
