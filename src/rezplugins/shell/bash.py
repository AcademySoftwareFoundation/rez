"""
Bash shell
"""
import os
import os.path
from rez.utils.platform_ import platform_
from rezplugins.shell.sh import SH
from rez import module_root_path
from rez.rex import EscapedString


class Bash(SH):
    rcfile_arg = '--rcfile'
    norc_arg = '--norc'

    @classmethod
    def name(cls):
        return 'bash'

    @classmethod
    def startup_capabilities(cls, rcfile=False, norc=False, stdin=False,
                             command=False):
        if norc:
            cls._overruled_option('rcfile', 'norc', rcfile)
            rcfile = False
        if command is not None:
            cls._overruled_option('stdin', 'command', stdin)
            cls._overruled_option('rcfile', 'command', rcfile)
            stdin = False
            rcfile = False
        if stdin:
            cls._overruled_option('rcfile', 'stdin', rcfile)
            rcfile = False
        return (rcfile, norc, stdin, command)

    @classmethod
    def get_startup_sequence(cls, rcfile, norc, stdin, command):
        rcfile, norc, stdin, command = \
            cls.startup_capabilities(rcfile, norc, stdin, command)

        files = []
        envvar = None
        do_rcfile = False

        if (command is not None) or stdin:
            envvar = 'BASH_ENV'
            path = os.getenv(envvar)
            if path and os.path.isfile(os.path.expanduser(path)):
                files.append(path)
        elif rcfile or norc:
            do_rcfile = True
            if rcfile and os.path.exists(os.path.expanduser(rcfile)):
                files.append(rcfile)
        else:
            for file_ in (
                    "~/.bash_profile",
                    "~/.bash_login",
                    "~/.profile",
                    "~/.bashrc"):
                if os.path.exists(os.path.expanduser(file_)):
                    files.append(file_)

        bind_files = [
            "~/.bash_profile",
            "~/.bashrc"
        ]

        return dict(
            stdin=stdin,
            command=command,
            do_rcfile=do_rcfile,
            envvar=envvar,
            files=files,
            bind_files=bind_files,
            source_bind_files=True
        )

    def alias(self, key, value):
        value = EscapedString.disallow(value)
        cmd = 'function {key}() {{ {value} "$@"; }};export -f {key};'
        self._addline(cmd.format(key=key, value=value))

    def _bind_interactive_rez(self):
        super(Bash, self)._bind_interactive_rez()
        completion = os.path.join(module_root_path, "completion", "complete.sh")
        self.source(completion)


def register_plugin():
    if platform_.name != "windows":
        return Bash


# Copyright 2013-2016 Allan Johns.
#
# This library is free software: you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.
