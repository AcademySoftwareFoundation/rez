"""
CSH shell
"""
import pipes
import os.path
import subprocess
from rez.config import config
from rez.utils.execution import Popen
from rez.utils.platform_ import platform_
from rez.shells import UnixShell
from rez.rex import EscapedString


class CSH(UnixShell):
    norc_arg = '-f'
    last_command_status = '$status'
    histfile = "~/.history"
    histvar = "histfile"

    @classmethod
    def name(cls):
        return 'csh'

    @classmethod
    def file_extension(cls):
        return 'csh'

    @classmethod
    def get_syspaths(cls):
        if cls.syspaths is not None:
            return cls.syspaths

        if config.standard_system_paths:
            cls.syspaths = config.standard_system_paths
            return cls.syspaths

        # detect system paths using registry
        cmd = "cmd=`which %s`; unset PATH; $cmd %s 'echo __PATHS_ $PATH'" \
              % (cls.name(), cls.command_arg)
        p = Popen(cmd, stdout=subprocess.PIPE,
                  stderr=subprocess.PIPE, shell=True, text=True)
        out_, err_ = p.communicate()
        if p.returncode:
            paths = []
        else:
            lines = out_.split('\n')
            line = [x for x in lines if "__PATHS_" in x.split()][0]
            paths = line.strip().split()[-1].split(os.pathsep)

        for path in os.defpath.split(os.path.pathsep):
            if path not in paths:
                paths.append(path)

        cls.syspaths = [x for x in paths if x]
        return cls.syspaths

    @classmethod
    def startup_capabilities(cls, rcfile=False, norc=False, stdin=False,
                             command=False):
        cls._unsupported_option('rcfile', rcfile)
        rcfile = False
        if command is not None:
            cls._overruled_option('stdin', 'command', stdin)
            stdin = False
        return (rcfile, norc, stdin, command)

    @classmethod
    def get_startup_sequence(cls, rcfile, norc, stdin, command):
        rcfile, norc, stdin, command = \
            cls.startup_capabilities(rcfile, norc, stdin, command)

        files = []
        if not norc:
            for file in (
                    "~/.tcshrc",
                    "~/.cshrc",
                    "~/.login",
                    "~/.cshdirs"):
                if os.path.exists(os.path.expanduser(file)):
                    files.append(file)

        return dict(
            stdin=stdin,
            command=command,
            do_rcfile=False,
            envvar=None,
            files=files,
            bind_files=(
                "~/.tcshrc",
                "~/.cshrc"),
            source_bind_files=(not norc)
        )

    def escape_string(self, value):
        value = EscapedString.promote(value)
        value = value.expanduser()
        result = ''

        for is_literal, txt in value.strings:
            if is_literal:
                txt = pipes.quote(txt)
                if not txt.startswith("'"):
                    txt = "'%s'" % txt
            else:
                txt = txt.replace('"', '"\\""')
                txt = txt.replace('!', '\\!')
                txt = '"%s"' % txt
            result += txt
        return result

    def _bind_interactive_rez(self):
        if config.set_prompt and self.settings.prompt:
            # TODO: Do more like in sh.py, much less error prone
            stored_prompt = os.getenv("REZ_STORED_PROMPT_CSH")
            curr_prompt = stored_prompt or os.getenv("prompt", "[%m %c]%# ")
            if not stored_prompt:
                self.setenv("REZ_STORED_PROMPT_CSH", '"%s"' % curr_prompt)

            new_prompt = "$REZ_ENV_PROMPT"
            new_prompt = (new_prompt + " %s") if config.prefix_prompt \
                else ("%s " + new_prompt)

            new_prompt = new_prompt % curr_prompt
            new_prompt = self.escape_string(new_prompt)
            self._addline('set prompt=%s' % new_prompt)

    def _saferefenv(self, key):
        self._addline("if (!($?%s)) setenv %s" % (key, key))

    def setenv(self, key, value):
        value = self.escape_string(value)
        self._addline('setenv %s %s' % (key, value))

    def unsetenv(self, key):
        self._addline("unsetenv %s" % key)

    def alias(self, key, value):
        value = EscapedString.disallow(value)
        self._addline("alias %s '%s';" % (key, value))

    def source(self, value):
        value = self.escape_string(value)
        self._addline('source %s' % value)


def register_plugin():
    if platform_.name != "windows":
        return CSH


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
