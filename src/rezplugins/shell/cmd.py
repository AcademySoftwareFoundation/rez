"""
Windows Command Prompt (DOS) shell.
"""
from rez.config import config
from rez.rex import RexExecutor, literal, OutputStyle, EscapedString
from rez.shells import Shell
from rez.utils.system import popen
from rez.utils.platform_ import platform_
from rez.util import shlex_join
from rez.backport.shutilwhich import which
from functools import partial
import os
import re


class CMD(Shell):
    # For reference, the ss64 web page provides useful documentation on builtin
    # commands for the Windows Command Prompt (cmd).  It can be found here :
    # http://ss64.com/nt/cmd.html
    syspaths = None
    _executable = None
    _doskey = None

    # Regex to aid with escaping of Windows-specific special chars:
    # http://ss64.com/nt/syntax-esc.html
    _escape_re = re.compile(r'(?<!\^)[&<>]|(?<!\^)\^(?![&<>\^])')
    _escaper = partial(_escape_re.sub, lambda m: '^' + m.group(0))

    @property
    def executable(cls):
        if cls._executable is None:
            cls._executable = Shell.find_executable('cmd')
        return cls._executable

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

        paths = os.getenv("PATH").split(os.pathsep)

        cls.syspaths = list(set([x for x in paths if x]))

        # add Rez binaries
        exe = which("rez")
        assert exe, "Could not find rez binary, this is a bug"
        rez_bin_dir = os.path.dirname(exe)
        cls.syspaths.insert(0, rez_bin_dir)

        return cls.syspaths

    def _bind_interactive_rez(self):
        if config.set_prompt and self.settings.prompt:
            stored_prompt = os.getenv("REZ_STORED_PROMPT")
            curr_prompt = stored_prompt or os.getenv("PROMPT", "")
            if not stored_prompt:
                self.setenv("REZ_STORED_PROMPT", curr_prompt)

            new_prompt = "%%REZ_ENV_PROMPT%%"
            new_prompt = (new_prompt + " %s") if config.prefix_prompt \
                else ("%s " + new_prompt)
            new_prompt = new_prompt % curr_prompt
            self._addline('set PROMPT=%s' % new_prompt)

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
            newprompt = '%%REZ_ENV_PROMPT%%%s' % self.settings.prompt
            executor.interpreter._saferefenv('REZ_ENV_PROMPT')
            executor.env.REZ_ENV_PROMPT = literal(newprompt)

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

        if shell_command:
            cmd_flags = ['/Q', '/C']
        else:
            cmd_flags = ['/Q', '/K']

        cmd = cmd + [self.executable] + cmd_flags + ['call {}'.format(target_file)]
        is_detached = (cmd[0] == 'START')

        p = popen(cmd, env=env, shell=is_detached, **Popen_args)
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
        if isinstance(value, EscapedString):
            return value.formatted(self._escaper)
        return self._escaper(value)

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

        self._addline("%s %s=%s $*" % (self._doskey, key, value))

    def comment(self, value):
        for line in value.split('\n'):
            self._addline('REM %s' % line)

    def info(self, value):
        for line in value.split('\n'):
            self._addline('echo %s' % line)

    def error(self, value):
        for line in value.split('\n'):
            self._addline('echo "%s" 1>&2' % line)

    def source(self, value):
        self._addline("call %s" % value)

    def command(self, value):
        self._addline(value)

    def get_key_token(self, key):
        return "%%%s%%" % key

    def join(self, command):
        return shlex_join(command).replace("'", '"')


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
