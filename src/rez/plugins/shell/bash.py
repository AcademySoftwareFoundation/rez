import sys
import select
import os
import os.path
from rez import plugin_factory
from rez.shells import UnixShell
from rez.plugins.shell.sh import SH



class Bash(SH):
    executable = UnixShell.find_executable('bash')
    rcfile_arg = '--rcfile'
    norc_arg = '--norc'

    @classmethod
    def name(cls):
        return 'bash'

    @classmethod
    def supports_rcfile(cls):
        return True

    @classmethod
    def startup_capabilities(cls, rcfile=False, norc=False, command=False, stdin=False):
        if norc:
            cls._overruled_option('rcfile', 'norc', rcfile)
            rcfile = False
        if command:
            cls._overruled_option('stdin', 'command', stdin)
            cls._overruled_option('rcfile', 'command', rcfile)
            stdin = False
            rcfile = False
        if stdin:
            cls._overruled_option('rcfile', 'stdin', rcfile)
            rcFile = False
        return (norc, rcfile, command, stdin)

    @classmethod
    def get_startup_sequence(cls, rcfile, norc, stdin, command):
        rcfile, norc, stdin, command = \
            cls.startup_capabilities(rcfile, norc, stdin, command)

        files = []
        envvar = None
        do_rcfile = False

        if command or stdin:
            envvar = 'BASH_ENV'
            path = os.getenv(envvar)
            if path and os.path.isfile(os.path.expanduser(path)):
                files.append(path)
        elif rcfile or norc:
            do_rcfile = True
            if rcfile and os.path.exists(os.path.expanduser(rcfile)):
                files.append(rcfile)
        else:
            for file in (
                    "~/.bash_profile",
                    "~/.bash_login",
                    "~/.profile",
                    "~/.bashrc"):
                if os.path.exists(os.path.expanduser(file)):
                    files.append(file)

        return dict(
            stdin=stdin,
            command=command,
            do_rcfile=do_rcfile,
            envvar=envvar,
            files=files,
            bind_files=(
                "~/.bash_profile",
                "~/.bashrc"),
            source_bind_files=True
        )


class BashFactory(plugin_factory.RezPluginFactory):
    def target_type(self):
        return Bash
