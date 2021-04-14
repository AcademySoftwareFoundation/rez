"""
Windows Command Prompt (DOS) shell.
"""
from rez.config import config
from rez.rex import RexExecutor, expandable, OutputStyle, EscapedString
from rez.shells import Shell
from rez.system import system
from rez.utils.execution import Popen
from rez.utils.platform_ import platform_
from rez.vendor.six import six
from functools import partial
import os
import re
import subprocess


basestring = six.string_types[0]


class CMD(Shell):
    # For reference, the ss64 web page provides useful documentation on builtin
    # commands for the Windows Command Prompt (cmd).  It can be found here :
    # http://ss64.com/nt/cmd.html
    syspaths = None
    _doskey = None
    expand_env_vars = True

    _env_var_regex = re.compile("%([A-Za-z0-9_]+)%")    # %ENVVAR%

    # Regex to aid with escaping of Windows-specific special chars:
    # http://ss64.com/nt/syntax-esc.html
    _escape_re = re.compile(r'(?<!\^)[&<>]|(?<!\^)\^(?![&<>\^])|(\|)')
    _escaper = partial(_escape_re.sub, lambda m: '^' + m.group(0))

    def __init__(self):
        super(CMD, self).__init__()
        self._doskey_aliases = {}

    @classmethod
    def name(cls):
        return 'cmd'

    @classmethod
    def file_extension(cls):
        return 'bat'

    @classmethod
    def startup_capabilities(cls, rcfile=False, norc=False, stdin=False,
                             command=False):
        cls._unsupported_option('rcfile', rcfile)
        rcfile = False
        cls._unsupported_option('norc', norc)
        norc = False
        cls._unsupported_option('stdin', stdin)
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
            "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment",
            "/v",
            "PATH"
        ]

        expected = gen_expected_regex([
            "HKEY_LOCAL_MACHINE\\\\SYSTEM\\\\CurrentControlSet\\\\Control\\\\Session Manager\\\\Environment",
            "PATH",
            "REG_(EXPAND_)?SZ",
            "(.*)"
        ])

        p = Popen(cmd, stdout=subprocess.PIPE,
                  stderr=subprocess.PIPE, shell=True, text=True)
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

        p = Popen(cmd, stdout=subprocess.PIPE,
                  stderr=subprocess.PIPE, shell=True, text=True)
        out_, _ = p.communicate()
        out_ = out_.strip()

        if p.returncode == 0:
            match = re.match(expected, out_)
            if match:
                paths.extend(match.group(2).split(os.pathsep))

        cls.syspaths = [x for x in paths if x]
        return cls.syspaths

    def _bind_interactive_rez(self):
        if config.set_prompt and self.settings.prompt:
            stored_prompt = os.getenv("REZ_STORED_PROMPT_CMD")
            curr_prompt = stored_prompt or os.getenv("PROMPT", "")
            if not stored_prompt:
                self.setenv("REZ_STORED_PROMPT_CMD", curr_prompt)

            new_prompt = "%%REZ_ENV_PROMPT%%"
            new_prompt = (new_prompt + " %s") if config.prefix_prompt \
                else ("%s " + new_prompt)
            new_prompt = new_prompt % curr_prompt
            self._addline('set PROMPT=%s' % new_prompt)

    def spawn_shell(self, context_file, tmpdir, rcfile=None, norc=False,
                    stdin=False, command=None, env=None, quiet=False,
                    pre_command=None, add_rez=True, **Popen_args):

        command = self._expand_alias(command)
        startup_sequence = self.get_startup_sequence(rcfile, norc, bool(stdin), command)
        shell_command = None

        def _record_shell(ex, files, bind_rez=True, print_msg=False):
            ex.source(context_file)
            if startup_sequence["envvar"]:
                ex.unsetenv(startup_sequence["envvar"])
            if add_rez and bind_rez:
                ex.interpreter._bind_interactive_rez()
            if print_msg and add_rez and not quiet:
                ex.info('')
                ex.info('You are now in a rez-configured environment.')
                ex.info('')
                if system.is_production_rez_install:
                    # previously this was called with the /K flag, however
                    # that would leave spawn_shell hung on a blocked call
                    # waiting for the user to type "exit" into the shell that
                    # was spawned to run the rez context printout
                    ex.command("cmd /Q /C rez context")

        def _create_ex():
            return RexExecutor(interpreter=self.new_shell(),
                               parent_environ={},
                               add_default_namespaces=False)

        executor = _create_ex()

        if self.settings.prompt:
            executor.interpreter._saferefenv('REZ_ENV_PROMPT')
            executor.env.REZ_ENV_PROMPT = \
                expandable("%REZ_ENV_PROMPT%").literal(self.settings.prompt)

        # Make .py launch within cmd without extension.
        if self.settings.additional_pathext:
            # Ensure that the PATHEXT does not append duplicates.
            fmt = (
                'echo %PATHEXT%|C:\\Windows\\System32\\findstr.exe /i /c:"{0}">nul '
                '|| set PATHEXT=%PATHEXT%;{0}'
            )

            for pathext in self.settings.additional_pathext:
                executor.command(fmt.format(pathext))
            # This resets the errorcode, which is tainted by the code above
            executor.command("(call )")

        if startup_sequence["command"] is not None:
            _record_shell(executor, files=startup_sequence["files"])
            shell_command = startup_sequence["command"]
        else:
            _record_shell(executor, files=startup_sequence["files"], print_msg=(not quiet))

        if shell_command:
            # Launch the provided command in the configured shell and wait
            # until it exits.
            executor.command(shell_command)

        # Test for None specifically because resolved_context.execute_rex_code
        # passes '' and we do NOT want to keep a shell open during a rex code
        # exec operation.
        elif shell_command is None:
            # Launch the configured shell itself and wait for user interaction
            # to exit.
            executor.command('cmd /Q /K')

        # Exit the configured shell.
        executor.command('exit %errorlevel%')

        code = executor.get_output()
        target_file = os.path.join(tmpdir, "rez-shell.%s"
                                   % self.file_extension())

        with open(target_file, 'w') as f:
            f.write(code)

        if startup_sequence["stdin"] and stdin and (stdin is not True):
            Popen_args["stdin"] = stdin

        cmd = []
        if pre_command:
            if isinstance(pre_command, basestring):
                cmd = pre_command.strip().split()
            else:
                cmd = pre_command

        # Test for None specifically because resolved_context.execute_rex_code
        # passes '' and we do NOT want to keep a shell open during a rex code
        # exec operation.
        if shell_command is None:
            cmd_flags = ['/Q', '/K']
        else:
            cmd_flags = ['/Q', '/C']

        cmd += [self.executable]
        cmd += cmd_flags
        cmd += ['call {}'.format(target_file)]
        is_detached = (cmd[0] == 'START')

        p = Popen(cmd, env=env, shell=is_detached, **Popen_args)
        return p

    def get_output(self, style=OutputStyle.file):
        if style == OutputStyle.file:
            script = '\n'.join(self._lines) + '\n'
        else:  # eval style
            lines = []
            for line in self._lines:
                if not line.startswith('REM'):  # strip comments
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
        value = EscapedString.promote(value)
        value = value.expanduser()
        result = ''

        for is_literal, txt in value.strings:
            if is_literal:
                txt = self._escaper(txt)
                # Note that cmd uses ^% while batch files use %% to escape %
                txt = self._env_var_regex.sub(r"%%\1%%", txt)
            else:
                txt = self._escaper(txt)
            result += txt
        return result

    def _saferefenv(self, key):
        pass

    def shebang(self):
        pass

    def setenv(self, key, value):
        value = self.escape_string(value)
        self._addline('set %s=%s' % (key, value))

    def unsetenv(self, key):
        self._addline("set %s=" % key)

    def resetenv(self, key, value, friends=None):
        self._addline(self.setenv(key, value))

    def alias(self, key, value):
        # find doskey, falling back to system paths if not in $PATH. Fall back
        # to unqualified 'doskey' if all else fails
        if self._doskey is None:
            try:
                self.__class__._doskey = \
                    self.find_executable("doskey", check_syspaths=True)
            except:
                self._doskey = "doskey"

        self._doskey_aliases[key] = value

        self._addline("%s %s=%s $*" % (self._doskey, key, value))

    def comment(self, value):
        for line in value.split('\n'):
            self._addline('REM %s' % line)

    def info(self, value):
        for line in value.split('\n'):
            line = self.escape_string(line)
            line = self.convert_tokens(line)
            if line:
                self._addline('echo %s' % line)
            else:
                self._addline('echo.')

    def error(self, value):
        for line in value.split('\n'):
            line = self.escape_string(line)
            line = self.convert_tokens(line)
            self._addline('echo "%s" 1>&2' % line)

    def source(self, value):
        self._addline("call %s" % value)

    def command(self, value):
        self._addline(value)

    @classmethod
    def get_all_key_tokens(cls, key):
        return ["%{}%".format(key)]

    @classmethod
    def join(cls, command):
        # TODO: This may disappear in future [1]
        # [1] https://bugs.python.org/issue10838
        return subprocess.list2cmdline(command)

    @classmethod
    def line_terminator(cls):
        return "\r\n"

    def _expand_alias(self, command):
        """Expand `command` if alias is being presented

        This is important for Windows CMD shell because the doskey.exe isn't
        executed yet when the alias is being passed in `command`. This means we
        cannot rely on doskey.exe to execute alias in first run. So here we
        lookup alias that were just parsed from package, replace it with full
        command if matched.
        """
        if command:
            word = command.split()[0]
            resolved_alias = self._doskey_aliases.get(word)

            if resolved_alias:
                command = command.replace(word, resolved_alias, 1)

        return command


def register_plugin():
    if platform_.name == "windows":
        return CMD


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
