# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


import os
import re

from rez.config import config
from rez.rex import RexExecutor, OutputStyle, EscapedString
from rez.shells import Shell
from rez.system import system
from rez.utils.platform_ import platform_
from rez.utils.execution import Popen
from rez.util import shlex_join
from .windows import get_syspaths_from_registry, to_windows_path


class PowerShellBase(Shell):
    """
    Abstract base class for PowerShell-like shells.
    """
    expand_env_vars = True
    syspaths = None

    # Make sure that the $Env:VAR formats come before the $VAR formats since
    # PowerShell Environment variables are ambiguous with Unix paths.
    # Note: This is used in other parts of Rez
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

        paths = get_syspaths_from_registry()

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

        # Translate the status of the most recent command into an exit code.
        #
        # Note that in PowerShell, `$LASTEXITCODE` is only set after calling a
        # native command (i.e. an executable), or another script that uses the
        # `exit` keyword. Otherwise, only the boolean `$?` variable is set (to
        # True if the last command succeeded and False if it failed).
        # See https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_automatic_variables  # noqa
        #
        # Additionally, if PowerShell is running in strict mode, references to
        # uninitialized variables will error instead of simply returning 0 or
        # `$null`, so we use `Test-Path` here to verify that `$LASTEXITCODE` has
        # been set before using it.
        # See https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/set-strictmode?view=powershell-7.5#description  # noqa
        #
        executor.command(
            "if ((Test-Path variable:LASTEXITCODE) -and $LASTEXITCODE) {\n"
            "  exit $LASTEXITCODE\n"
            "}\n"
            "if (! $?) {\n"
            "  exit 1\n"
            "}"
        )

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

        # Powershell execution policy overrides
        # Prevent injections/mistakes by ensuring policy value only contains letters.
        execution_policy = self.settings.execution_policy
        if execution_policy and execution_policy.isalpha():
            cmd += ["-ExecutionPolicy", execution_policy]

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

    def escape_string(self, value, is_path=False):
        value = EscapedString.promote(value)
        value = value.expanduser()
        result = ''

        for is_literal, txt in value.strings:
            if is_literal:
                txt = self._escape_quotes(self._escape_vars(txt))
            else:
                if is_path:
                    txt = self.normalize_paths(txt)

                txt = self._escape_quotes(txt)
            result += txt
        return result

    def normalize_path(self, path):
        if platform_.name == "windows":
            return to_windows_path(path)
        else:
            return path

    def _saferefenv(self, key):
        pass

    def shebang(self):
        pass

    def setenv(self, key, value):
        value = self.escape_string(value, is_path=self._is_pathed_key(key))
        self._addline('Set-Item -Path "Env:{0}" -Value "{1}"'.format(key, value))

    def prependenv(self, key, value):
        value = self.escape_string(value, is_path=self._is_pathed_key(key))

        # Be careful about ambiguous case in pwsh on Linux where pathsep is :
        # so that the ${ENV:VAR} form has to be used to not collide.
        self._addline(
            'Set-Item -Path "Env:{0}" -Value ("{1}{2}" + (Get-ChildItem -ErrorAction SilentlyContinue "Env:{0}").Value)'
            .format(key, value, self.pathsep)
        )

    def appendenv(self, key, value):
        value = self.escape_string(value, is_path=self._is_pathed_key(key))

        # Be careful about ambiguous case in pwsh on Linux where pathsep is :
        # so that the ${ENV:VAR} form has to be used to not collide.
        # The nested Get-ChildItem call is set to SilentlyContinue to prevent
        # an exception of the Environment Variable is not set already
        self._addline(
            'Set-Item -Path "Env:{0}" -Value ((Get-ChildItem -ErrorAction SilentlyContinue "Env:{0}").Value + "{1}{2}")'
            .format(key, os.path.pathsep, value))

    def unsetenv(self, key):
        self._addline(
            'Remove-Item -ErrorAction SilentlyContinue "Env:{0}"'.format(key)
        )

    def resetenv(self, key, value, friends=None):
        self._addline(self.setenv(key, value))

    def alias(self, key, value):
        value = EscapedString.disallow(value)
        # TODO: Find a way to properly escape paths in alias() calls that also
        # contain args
        #
        cmd = "function %s() { %s @args }" % (key, value)
        self._addline(cmd)

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
    def line_terminator(cls):
        return "\n"

    @classmethod
    def join(cls, command):
        if isinstance(command, str):
            return command

        replacements = [
            # escape ` as ``
            ('`', "``"),

            # escape " as `"
            ('"', '`"')
        ]

        joined = shlex_join(command, replacements=replacements)

        # add call operator in case executable gets quotes applied
        # https://docs.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_operators?view=powershell-7.1#call-operator-
        #
        return "& " + joined
