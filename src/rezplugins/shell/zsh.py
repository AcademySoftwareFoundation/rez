# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Zsh shell
"""
import os
import os.path
from rez.config import config
from rez.rex import EscapedString
from rez.utils.platform_ import platform_
from rezplugins.shell.sh import SH
from rez import module_root_path
from shlex import quote


class Zsh(SH):
    rcfile_arg = None
    norc_arg = '--no-rcs'
    histfile = "~/.zsh_history"

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

        if rcfile or norc:
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
            "~/.zshrc"
        ]

        return dict(
            stdin=stdin,
            command=command,
            do_rcfile=False,
            envvar=None,
            files=files,
            bind_files=bind_files,
            source_bind_files=not norc
        )

    def _bind_interactive_rez(self):
        if config.set_prompt and self.settings.prompt:
            self._addline(r'if [ -z "$REZ_STORED_PROMPT_SH" ]; then export REZ_STORED_PROMPT_SH="$PS1"; fi')
            if config.prefix_prompt:
                cmd = 'export PS1="%s $REZ_STORED_PROMPT_SH"'
            else:
                cmd = 'export PS1="$REZ_STORED_PROMPT_SH %s"'
            self._addline(cmd % r"%{%B%}$REZ_ENV_PROMPT%{%b%}")
        completion = os.path.join(module_root_path, "completion", "complete.zsh")
        self.source(completion)

    def escape_string(self, value, is_path=False):
        value = EscapedString.promote(value)
        value = value.expanduser()
        result = ''

        for is_literal, txt in value.strings:
            if is_literal:
                txt = quote(txt)
                if not txt.startswith("'"):
                    txt = "'%s'" % txt
            else:
                if is_path:
                    txt = self.normalize_paths(txt)

                txt = txt.replace('\\', '\\\\')
                txt = txt.replace('"', '\\"')
                txt = txt.replace("%", "%%")
                txt = '"%s"' % txt
            result += txt
        return result


def register_plugin():
    if platform_.name != "windows":
        return Zsh
