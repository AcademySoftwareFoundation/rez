# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Bash shell
"""
from __future__ import annotations

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
    def name(cls) -> str:
        return 'bash'

    @classmethod
    def startup_capabilities(cls, rcfile: str | None | bool = False, norc: bool = False, stdin: bool = False,
                             command: bool = False) -> tuple[bool, bool, bool, bool]:
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
    def get_startup_sequence(cls, rcfile: str | None, norc: bool, stdin: bool, command):
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

    def alias(self, key, value) -> None:
        value = EscapedString.disallow(value)
        cmd = 'function {key}() {{ {value} "$@"; }};export -f {key};'
        self._addline(cmd.format(key=key, value=value))

    def _bind_interactive_rez(self) -> None:
        super(Bash, self)._bind_interactive_rez()
        completion = os.path.join(module_root_path, "completion", "complete.sh")
        self.source(completion)


def register_plugin():
    if platform_.name != "windows":
        return Bash
