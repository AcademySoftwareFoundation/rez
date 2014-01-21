import sys
import select
import os
import os.path
from rez import plugin_factory
from rez.shells import UnixShell
from rez.plugins.shell.sh import SH



class Bash(SH):
    executable = UnixShell.find_executable('bash')

    @classmethod
    def name(cls):
        return 'bash'

    @classmethod
    def get_startup_sequence(cls, rcfile, stdin, command):
        files = []
        envvar = None

        if command:
            cls._ignore_bool_option('stdin', stdin)
            stdin = False
        if stdin and not select.select([sys.stdin,],[],[],0.0)[0]:  # tests stdin
            stdin = False

        if command or stdin:
            cls._ignore_bool_option('rcfile', rcfile)
            envvar = 'BASH_ENV'
            path = os.getenv(envvar)
            if path and os.path.isfile(path):
                files.append(path)
        elif rcfile:
            if os.path.exists(os.path.expanduser(rcfile)):
                files.append(file)
        else:
            for file in ("~/.bashrc",):
                if os.path.exists(os.path.expanduser(file)):
                    files.append(file)

        return dict(
            stdin=stdin,
            command=command,
            envvar=envvar,
            files=files,
            default_file='.bashrc'
        )


class BashFactory(plugin_factory.RezPluginFactory):
    def target_type(self):
        return Bash
