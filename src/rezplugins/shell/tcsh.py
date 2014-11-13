"""
TCSH shell
"""
from rez.shells import UnixShell
from rezplugins.shell.csh import CSH
from rez import module_root_path
import os.path


class TCSH(CSH):
    executable = UnixShell.find_executable('tcsh')

    @classmethod
    def name(cls):
        return 'tcsh'

    def _bind_interactive_rez(self):
        super(TCSH, self)._bind_interactive_rez()
        completion = os.path.join(module_root_path, "completion", "complete.csh")
        self.source(completion)


def register_plugin():
    return TCSH
