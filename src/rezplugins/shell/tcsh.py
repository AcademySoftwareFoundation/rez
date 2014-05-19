from rez.shells import UnixShell
from rezplugins.shell.csh import CSH


class TCSH(CSH):
    executable = UnixShell.find_executable('tcsh')

    @classmethod
    def name(cls):
        return 'tcsh'


def register_plugin():
    return TCSH
