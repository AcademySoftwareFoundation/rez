"""Windows PowerShell 5"""

from rez.config import config
from rez.rex import RexExecutor, OutputStyle, EscapedString
from rez.shells import Shell
from rez.utils.system import popen
from rez.utils.platform_ import platform_
from rez.backport.shutilwhich import which
from functools import partial
import os
import re
import subprocess

try:
    basestring
except NameError:
    # Python 3+
    basestring = str


class PowerShell(Shell):
    syspaths = None
    _executable = None

    # Regex to aid with escaping of Windows-specific special chars:
    # http://ss64.com/nt/syntax-esc.html
    _escape_re = re.compile(r'(?<!\^)[&<>]|(?<!\^)\^(?![&<>\^])')
    _escaper = partial(_escape_re.sub, lambda m: '^' + m.group(0))

    @property
    def executable(cls):
        if cls._executable is None:
            cls._executable = Shell.find_executable('powershell')
        return cls._executable

    @classmethod
    def name(cls):
        return 'powershell'

    @classmethod
    def file_extension(cls):
        return 'ps1'

    @classmethod
    def startup_capabilities(cls, rcfile=False, norc=False, stdin=False,
                             command=False):
        cls._unsupported_option('rcfile', rcfile)
        cls._unsupported_option('norc', norc)
        cls._unsupported_option('stdin', stdin)
        rcfile = False
        norc = False
        stdin = False
        return (rcfile, norc, stdin, command)

    @classmethod
    def get_startup_sequence(cls, rcfile, norc, stdin, command):
        rcfile, norc, stdin, command = \
            cls.startup_capabilities(rcfile, norc, stdin, command)

        return dict(
            stdin=stdin,
            command=command,
            do_rcfile=False,
            envvar=None,
            files=[],
            bind_files=[],
            source_bind_files=(not norc)
        )

    @classmethod
    def get_syspaths(cls):
        if cls.syspaths is not None:
            return cls.syspaths

        if config.standard_system_paths:
            cls.syspaths = config.standard_system_paths
            return cls.syspaths

        # detect system paths using registry
        def gen_expected_regex(parts):
            whitespace = r"[\s]+"
            return whitespace.join(parts)

        paths = []

        cmd = [
            "REG",
            "QUERY",
            (
                "HKLM\\SYSTEM\\CurrentControlSet\\"
                "Control\\Session Manager\\Environment"
            ),
            "/v",
            "PATH"
        ]

        expected = gen_expected_regex([
            (
                "HKEY_LOCAL_MACHINE\\\\SYSTEM\\\\CurrentControlSet\\\\"
                "Control\\\\Session Manager\\\\Environment"
            ),
            "PATH",
            "REG_(EXPAND_)?SZ",
            "(.*)"
        ])

        p = popen(cmd,
                  stdout=subprocess.PIPE,
                  stderr=subprocess.PIPE,
                  universal_newlines=True,
                  shell=True)
        out_, _ = p.communicate()
        out_ = out_.strip()

        if p.returncode == 0:
            match = re.match(expected, out_)
            if match:
                paths.extend(match.group(2).split(os.pathsep))

        cmd = [
            "REG",
            "QUERY",
            "HKCU\\Environment",
            "/v",
            "PATH"
        ]

        expected = gen_expected_regex([
            "HKEY_CURRENT_USER\\\\Environment",
            "PATH",
            "REG_(EXPAND_)?SZ",
            "(.*)"
        ])

        p = popen(cmd,
                  stdout=subprocess.PIPE,
                  stderr=subprocess.PIPE,
                  universal_newlines=True,
                  shell=True)
        out_, _ = p.communicate()
        out_ = out_.strip()

        if p.returncode == 0:
            match = re.match(expected, out_)
            if match:
                paths.extend(match.group(2).split(os.pathsep))

        cls.syspaths = list(set([x for x in paths if x]))

        # add Rez binaries
        exe = which("rez-env")
        assert exe, "Could not find rez binary, this is a bug"
        rez_bin_dir = os.path.dirname(exe)
        cls.syspaths.insert(0, rez_bin_dir)

        return cls.syspaths

    def _bind_interactive_rez(self):
        if config.set_prompt and self.settings.prompt:
            self._addline('Function prompt {"%s"}' % self.settings.prompt)

    def spawn_shell(self, context_file, tmpdir, rcfile=None, norc=False,
                    stdin=False, command=None, env=None, quiet=False,
                    pre_command=None, **Popen_args):

        startup_sequence = self.get_startup_sequence(rcfile, norc, bool(stdin), command)
        shell_command = None

        def _record_shell(ex, files, bind_rez=True, print_msg=False):
            ex.source(context_file)
            if startup_sequence["envvar"]:
                ex.unsetenv(startup_sequence["envvar"])
            if bind_rez:
                ex.interpreter._bind_interactive_rez()
            if print_msg and not quiet:
                # Rez may not be available
                ex.command("Try { rez context } Catch { }")

        executor = RexExecutor(interpreter=self.new_shell(),
                               parent_environ={},
                               add_default_namespaces=False)

        if startup_sequence["command"] is not None:
            _record_shell(executor, files=startup_sequence["files"])
            shell_command = startup_sequence["command"]
        else:
            _record_shell(executor,
                          files=startup_sequence["files"],
                          print_msg=(not quiet))

        if shell_command:
            executor.command(shell_command)

        # Forward exit call to parent PowerShell process
        executor.command("exit $LastExitCode")

        code = executor.get_output()
        target_file = os.path.join(
            tmpdir, "rez-shell.%s" % self.file_extension()
        )

        with open(target_file, 'w') as f:
            f.write(code)

        cmd = []
        if pre_command:
            cmd = pre_command

            if not isinstance(cmd, (tuple, list)):
                cmd = pre_command.rstrip().split()

        cmd += [self.executable]
        cmd += ['. "{}"'.format(target_file)]

        if shell_command is None:
            cmd.insert(1, "-noexit")

        p = popen(cmd,
                  env=env,
                  universal_newlines=True,
                  **Popen_args)
        return p

    def get_output(self, style=OutputStyle.file):
        if style == OutputStyle.file:
            script = '\n'.join(self._lines) + '\n'
        else:
            lines = []
            for line in self._lines:
                if line.startswith('#'):
                    continue

                line = line.rstrip()
                lines.append(line)

            script = '&& '.join(lines)
        return script

    def escape_string(self, value):
        """Escape the <, >, ^, and & special characters reserved by Windows.

        Args:
            value (str/EscapedString): String or already escaped string.

        Returns:
            str: The value escaped for Windows.

        """
        if isinstance(value, EscapedString):
            return value.formatted(self._escaper)
        return self._escaper(value)

    def _saferefenv(self, key):
        pass

    def shebang(self):
        pass

    def setenv(self, key, value):
        value = self.escape_string(value)
        self._addline('$env:{0} = "{1}"'.format(key, value))

    def unsetenv(self, key):
        self._addline(r"Remove-Item Env:\%s" % key)

    def resetenv(self, key, value, friends=None):
        self._addline(self.setenv(key, value))

    def alias(self, key, value):
        value = EscapedString.disallow(value)
        cmd = "function {key}() {{ {value} $args }}"
        self._addline(cmd.format(key=key, value=value))

    def comment(self, value):
        for line in value.split('\n'):
            self._addline('# %s' % line)

    def info(self, value):
        for line in value.split('\n'):
            self._addline('Write-Host %s' % line)

    def error(self, value):
        for line in value.split('\n'):
            self._addline('Write-Error "%s"' % line)

    def source(self, value):
        self._addline(". \"%s\"" % value)

    def command(self, value):
        self._addline(value)

    def get_key_token(self, key):
        return "$env:%s" % key

    def join(self, command):
        return " ".join(command)


def register_plugin():
    if platform_.name == "windows":
        return PowerShell


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
