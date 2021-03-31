import os
import re
from subprocess import PIPE, list2cmdline

from rez.config import config
from rez.rex import RexExecutor, OutputStyle, EscapedString
from rez.shells import Shell
from rez.system import system
from rez.utils.platform_ import platform_
from rez.utils.execution import Popen


class PowerShellBase(Shell):
    """
    Abstract base class for PowerShell-like shells.
    """
    expand_env_vars = True
    syspaths = None

    # Make sure that the $Env:VAR formats come before the $VAR formats since
    # PowerShell Environment variables are ambiguous with Unix paths.
    ENV_VAR_REGEX = re.compile(
        "|".join([
            "\\$[Ee][Nn][Vv]:([a-zA-Z_]+[a-zA-Z0-9_]*?)",       # $Env:ENVVAR
            "\\${[Ee][Nn][Vv]:([a-zA-Z_]+[a-zA-Z0-9_]*?)}",     # ${Env:ENVVAR}
            Shell.ENV_VAR_REGEX.pattern,                        # Generic form
        ])
    )

    @staticmethod
    def _escape_quotes(s):
        return s.replace('"', '`"').replace("'", "`'")

    @staticmethod
    def _escape_vars(s):
        return s.replace('$', '`$')

    @classmethod
    def startup_capabilities(cls,
                             rcfile=False,
                             norc=False,
                             stdin=False,
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

        return dict(stdin=stdin,
                    command=command,
                    do_rcfile=False,
                    envvar=None,
                    files=[],
                    bind_files=[],
                    source_bind_files=(not norc))

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

        # TODO: Research if there is an easier way to pull system PATH from
        # registry in powershell
        paths = []

        cmd = [
            "REG", "QUERY",
            ("HKLM\\SYSTEM\\CurrentControlSet\\"
             "Control\\Session Manager\\Environment"), "/v", "PATH"
        ]

        expected = gen_expected_regex([
            ("HKEY_LOCAL_MACHINE\\\\SYSTEM\\\\CurrentControlSet\\\\"
             "Control\\\\Session Manager\\\\Environment"), "PATH",
            "REG_(EXPAND_)?SZ", "(.*)"
        ])

        p = Popen(cmd, stdout=PIPE, stderr=PIPE,
                  shell=True, text=True)
        out_, _ = p.communicate()
        out_ = out_.strip()

        if p.returncode == 0:
            match = re.match(expected, out_)
            if match:
                paths.extend(match.group(2).split(os.pathsep))

        cmd = ["REG", "QUERY", "HKCU\\Environment", "/v", "PATH"]

        expected = gen_expected_regex([
            "HKEY_CURRENT_USER\\\\Environment", "PATH", "REG_(EXPAND_)?SZ",
            "(.*)"
        ])

        p = Popen(cmd, stdout=PIPE, stderr=PIPE,
                  shell=True, text=True)
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
            self._addline('Function prompt {"%s"}' % self.settings.prompt)

    def _additional_commands(self, executor):
        # Make .py launch within shell without extension.
        # For PowerShell this will also execute in the same window, so that
        # stdout can be captured.
        if platform_.name == "windows" and self.settings.additional_pathext:
            # Ensures that the PATHEXT does not append duplicates.
            executor.command(
                '$Env:PATHEXT = ((($Env:PATHEXT + ";{}") -split ";") | Select-Object -Unique) -join ";"'.format(
                    ";".join(self.settings.additional_pathext)
                )
            )

    def spawn_shell(self,
                    context_file,
                    tmpdir,
                    rcfile=None,
                    norc=False,
                    stdin=False,
                    command=None,
                    env=None,
                    quiet=False,
                    pre_command=None,
                    add_rez=True,
                    **Popen_args):

        startup_sequence = self.get_startup_sequence(rcfile, norc, bool(stdin),
                                                     command)
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
                    ex.command("rezolve context")

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

        self._additional_commands(executor)

        if shell_command:
            executor.command(shell_command)

        # Forward exit call to parent PowerShell process
        executor.command("exit $LastExitCode")

        code = executor.get_output()
        target_file = os.path.join(tmpdir,
                                   "rez-shell.%s" % self.file_extension())

        with open(target_file, 'w') as f:
            f.write(code)

        cmd = []
        if pre_command:
            cmd = pre_command

            if not isinstance(cmd, (tuple, list)):
                cmd = pre_command.rstrip().split()

        cmd += [self.executable]

        # Suppresses copyright message of PowerShell and pwsh
        cmd += ["-NoLogo"]

        # Generic form of sourcing that works in powershell and pwsh
        cmd += ["-File", target_file]

        if shell_command is None:
            cmd.insert(1, "-NoExit")

        p = Popen(cmd, env=env, **Popen_args)
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
        value = EscapedString.promote(value)
        value = value.expanduser()
        result = ''

        for is_literal, txt in value.strings:
            if is_literal:
                txt = self._escape_quotes(self._escape_vars(txt))
            else:
                txt = self._escape_quotes(txt)
            result += txt
        return result

    def _saferefenv(self, key):
        pass

    def shebang(self):
        pass

    def setenv(self, key, value):
        value = self.escape_string(value)
        self._addline('$Env:{0} = "{1}"'.format(key, value))

    def appendenv(self, key, value):
        value = self.escape_string(value)
        # Be careful about ambiguous case in pwsh on Linux where pathsep is :
        # so that the ${ENV:VAR} form has to be used to not collide.
        self._addline(
            '$Env:{0} = "${{Env:{0}}}{1}{2}"'.format(key, os.path.pathsep, value)
        )

    def unsetenv(self, key):
        self._addline(r"Remove-Item Env:\%s" % key)

    def resetenv(self, key, value, friends=None):
        self._addline(self.setenv(key, value))

    def alias(self, key, value):
        value = EscapedString.disallow(value)
        # TODO: Find a way to properly escape paths in alias() calls that also
        # contain args
        cmd = "function {key}() {{ {value} $args }}"
        self._addline(cmd.format(key=key, value=value))

    def comment(self, value):
        for line in value.split('\n'):
            self._addline('# %s' % line)

    def info(self, value):
        for line in value.split('\n'):
            line = self.escape_string(line)
            line = self.convert_tokens(line)
            self._addline('Write-Host %s' % line)

    def error(self, value):
        for line in value.split('\n'):
            line = self.escape_string(line)
            line = self.convert_tokens(line)
            self._addline('Write-Error "%s"' % line)

    def source(self, value):
        self._addline(". \"%s\"" % value)

    def command(self, value):
        self._addline(value)

    @classmethod
    def get_all_key_tokens(cls, key):
        return ["${Env:%s}" % key, "$Env:%s" % key]

    @classmethod
    def join(cls, command):
        # TODO: This may disappear in future [1]
        # [1] https://bugs.python.org/issue10838
        return list2cmdline(command)

    @classmethod
    def line_terminator(cls):
        return "\n"
