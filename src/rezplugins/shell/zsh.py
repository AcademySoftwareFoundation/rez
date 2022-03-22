# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Zsh shell
"""
import os
import os.path
from rez.utils.platform_ import platform_
from rezplugins.shell.sh import SH
from rez import module_root_path


class Zsh(SH):
    rcfile_arg = '--rcs'
    norc_arg = '--no-rcs'

    @classmethod
    def name(cls):
        return 'zsh'

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

        if rcfile or norc:
            do_rcfile = True
            if rcfile and os.path.exists(os.path.expanduser(rcfile)):
                files.append(rcfile)
        else:
            for file_ in (
                    "~/.zprofile",
                    "~/.zlogin",
                    "~/.zshrc",
                    "~/.zshenv"):
                if os.path.exists(os.path.expanduser(file_)):
                    files.append(file_)

        bind_files = [
            "~/.zprofile",
            "~/.zshrc"
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

    def _bind_interactive_rez(self):
        super(Zsh, self)._bind_interactive_rez()
        completion = os.path.join(module_root_path, "completion", "complete.zsh")
        self.source(completion)


def register_plugin():
    if platform_.name != "windows":
        return Zsh
