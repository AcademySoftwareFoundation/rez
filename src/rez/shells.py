"""
Pluggable API for creating subshells using different programs, such as bash.
"""
from rez.rex import RexExecutor, ActionInterpreter, OutputStyle
from rez.util import shlex_join, is_non_string_iterable
from rez.backport.shutilwhich import which
from rez.utils.logging_ import print_warning
from rez.utils.execution import Popen
from rez.system import system
from rez.exceptions import RezSystemError
from rez.rex import EscapedString
from rez.config import config
from rez.vendor.six import six
import os
import os.path
import pipes


basestring = six.string_types[0]


def get_shell_types():
    """Returns the available shell types: bash, tcsh etc.

    Returns:
    List of str: Shells.
    """
    from rez.plugin_managers import plugin_manager
    return list(plugin_manager.get_plugins('shell'))


def get_shell_class(shell=None):
    """Get the plugin class associated with the given or current shell.

    Returns:
        class: Plugin class for shell.
    """
    if not shell:
        shell = config.default_shell
        if not shell:
            from rez.system import system
            shell = system.shell

    from rez.plugin_managers import plugin_manager
    return plugin_manager.get_plugin_class("shell", shell)


def create_shell(shell=None, **kwargs):
    """Returns a Shell of the given or current type.

    Returns:
        `Shell`: Instance of given shell.
    """
    if not shell:
        shell = config.default_shell
        if not shell:
            from rez.system import system
            shell = system.shell

    from rez.plugin_managers import plugin_manager
    return plugin_manager.create_instance('shell', shell, **kwargs)


class Shell(ActionInterpreter):
    """Class representing a shell, such as bash or tcsh.
    """
    schema_dict = {
        "prompt": basestring}

    @classmethod
    def name(cls):
        """Plugin name.
        """
        raise NotImplementedError

    @classmethod
    def executable_name(cls):
        """Name of executable to create shell instance.
        """
        return cls.name()

    @classmethod
    def executable_filepath(cls):
        """Get full filepath to executable, or raise if not found.
        """
        return cls.find_executable(cls.executable_name())

    @property
    def executable(self):
        return self.__class__.executable_filepath()

    @classmethod
    def is_available(cls):
        """Determine if the shell is available to instantiate.

        Returns:
            bool: True if the shell can be created.
        """
        try:
            return cls.executable_filepath() is not None
        except RuntimeError:
            return False

    @classmethod
    def file_extension(cls):
        """Get the file extension associated with the shell.

        Returns:
            str: Shell file extension.
        """
        raise NotImplementedError

    @classmethod
    def startup_capabilities(cls, rcfile=False, norc=False, stdin=False,
                             command=False):
        """
        Given a set of options related to shell startup, return the actual
        options that will be applied.
        @returns 4-tuple representing applied value of each option.
        """
        raise NotImplementedError

    @classmethod
    def get_syspaths(cls):
        raise NotImplementedError

    def __init__(self):
        self._lines = []
        self.settings = config.plugins.shell[self.name()]

    def _addline(self, line):
        self._lines.append(line)

    def get_output(self, style=OutputStyle.file):
        if style == OutputStyle.file:
            script = '\n'.join(self._lines) + '\n'
        else:  # eval style
            lines = []
            for line in self._lines:
                if not line.startswith('#'):  # strip comments
                    line = line.rstrip().rstrip(';')
                    lines.append(line)
            script = ';'.join(lines)

        return script

    def new_shell(self):
        """Returns A new, reset shell of the same type."""
        return self.__class__()

    @classmethod
    def _unsupported_option(cls, option, val):
        if val and config.warn("shell_startup"):
            print_warning("%s ignored, not supported by %s shell"
                          % (option, cls.name()))

    @classmethod
    def _overruled_option(cls, option, overruling_option, val):
        if val and config.warn("shell_startup"):
            print_warning("%s ignored by %s shell - overruled by %s option"
                          % (option, cls.name(), overruling_option))

    @classmethod
    def find_executable(cls, name, check_syspaths=False):
        """Find an executable.

        Args:
            name (str): Program name.
            check_syspaths (bool): If True, check the standard system paths as
                well, if program was not found on current $PATH.

        Returns:
            str: Full filepath of executable.
        """
        exe = which(name)

        if not exe and check_syspaths:
            paths = cls.get_syspaths()
            env = os.environ.copy()
            env["PATH"] = os.pathsep.join(paths)
            exe = which(name, env=env)

        if not exe:
            raise RuntimeError("Couldn't find executable '%s'." % name)
        return exe

    def spawn_shell(self, context_file, tmpdir, rcfile=None, norc=False,
                    stdin=False, command=None, env=None, quiet=False,
                    pre_command=None, add_rez=True,
                    package_commands_sourced_first=None, **Popen_args):
        """Spawn a possibly interactive subshell.
        Args:
            context:_file File that must be sourced in the new shell, this
                configures the Rez environment.
            tmpdir: Tempfiles, if needed, should be created within this path.
            rcfile: Custom startup script.
            norc: Don't run startup scripts. Overrides rcfile.
            stdin: If True, read commands from stdin in a non-interactive shell.
                If a different non-False value, such as subprocess.PIPE, the same
                occurs, but stdin is also passed to the resulting subprocess.Popen
                object.
            command: If not None, execute this command in a non-interactive shell.
                If an empty string, don't run a command, but don't open an
                interactive shell either.
            env: Environ dict to execute the shell within; uses the current
                environment if None.
            quiet: If True, don't show the configuration summary, and suppress
                any stdout from startup scripts.
            pre_command: Command to inject before the shell command itself. This
                is for internal use.
            add_rez: If True, assume this shell is being used with rez, and do
                things such as set the prompt etc.
            package_commands_sourced_first: If True, source the context file before
                sourcing startup scripts (such as .bashrc). If False, source
                the context file AFTER. If None, use the configured setting.
            popen_args: args to pass to the shell process object constructor.

        Returns:
            A subprocess.Popen object representing the shell process.
        """
        raise NotImplementedError

    @classmethod
    def convert_tokens(cls, value):
        """
        Converts any token like ${VAR} and $VAR to shell specific form.
        Uses the ENV_VAR_REGEX to correctly parse tokens.

        Args:
            value: str to convert

        Returns:
            str with shell specific variables
        """
        return cls.ENV_VAR_REGEX.sub(
            lambda m: "".join(cls.get_key_token(g) for g in m.groups() if g),
            value
        )

    @classmethod
    def get_key_token(cls, key):
        """
        Encodes the environment variable into the shell specific form.
        Shells might implement multiple forms, but the most common/safest
        should be returned here.

        Args:
            key: Variable name to encode

        Returns:
            str of encoded token form
        """
        return cls.get_all_key_tokens(key)[0]

    @classmethod
    def get_all_key_tokens(cls, key):
        """
        Encodes the environment variable into the shell specific forms.
        Shells might implement multiple forms, but the most common/safest
        should be always returned at index 0.

        Args:
            key: Variable name to encode

        Returns:
            list of str with encoded token forms
        """
        raise NotImplementedError

    @classmethod
    def line_terminator(cls):
        """
        Returns:
            str: default line terminator
        """
        raise NotImplementedError

    @classmethod
    def join(cls, command):
        """
        Args:
            command:
                A sequence of program arguments to be joined into a single
                string that can be executed in the current shell.
        Returns:
            A string object representing the command.
        """
        raise NotImplementedError


class UnixShell(Shell):
    """
    A base class for common *nix shells, such as bash and tcsh.
    """
    rcfile_arg = None
    norc_arg = None
    histfile = None
    histvar = None
    command_arg = '-c'
    stdin_arg = '-s'
    last_command_status = '$?'
    syspaths = None

    #
    # startup rules
    #

    @classmethod
    def supports_norc(cls):
        return True

    @classmethod
    def supports_command(cls):
        return True

    @classmethod
    def supports_stdin(cls):
        return True

    @classmethod
    def get_startup_sequence(cls, rcfile, norc, stdin, command):
        """
        Return a dict containing:
        - 'stdin': resulting stdin setting.
        - 'command': resulting command setting.
        - 'do_rcfile': True if a file should be sourced directly.
        - 'envvar': Env-var that points at a file to source at startup. Can be None.
        - 'files': Existing files that will be sourced (non-user-expanded), in source
            order. This may also incorporate rcfile, and file pointed at via envvar.
            Can be empty.
        - 'bind_files': Files to inject Rez binding into, even if that file doesn't
            already exist.
        - 'source_bind_files': Whether to source bind files, if they exist.
        """
        raise NotImplementedError

    def spawn_shell(self, context_file, tmpdir, rcfile=None, norc=False,
                    stdin=False, command=None, env=None, quiet=False,
                    pre_command=None, add_rez=True,
                    package_commands_sourced_first=None, **Popen_args):

        d = self.get_startup_sequence(rcfile, norc, bool(stdin), command)
        envvar = d["envvar"]
        files = d["files"]
        bind_files = d["bind_files"]
        do_rcfile = d["do_rcfile"]
        shell_command = None

        if package_commands_sourced_first is None:
            package_commands_sourced_first = config.package_commands_sourced_first

        def _record_shell(ex, files, bind_rez=True, print_msg=False):
            if bind_rez and package_commands_sourced_first:
                ex.source(context_file)

            for file_ in files:
                if os.path.exists(os.path.expanduser(file_)):
                    ex.source(file_)

            if bind_rez and not package_commands_sourced_first:
                ex.source(context_file)

            if envvar:
                ex.unsetenv(envvar)
            if add_rez and bind_rez:
                ex.interpreter._bind_interactive_rez()
            if print_msg and add_rez and not quiet:
                ex.info('')
                ex.info('You are now in a rez-configured environment.')
                ex.info('')
                if system.is_production_rez_install:
                    ex.command('rezolve context')

        def _write_shell(ex, filename):
            code = ex.get_output()
            target_file = os.path.join(tmpdir, filename)
            with open(target_file, 'w') as f:
                f.write(code)
            return target_file

        def _create_ex():
            return RexExecutor(interpreter=self.new_shell(),
                               parent_environ={},
                               add_default_namespaces=False)

        executor = _create_ex()

        if self.settings.prompt:
            newprompt = '${REZ_ENV_PROMPT}%s' % self.settings.prompt
            executor.interpreter._saferefenv('REZ_ENV_PROMPT')
            executor.env.REZ_ENV_PROMPT = newprompt

        if d["command"] is not None:
            _record_shell(executor, files=files)
            shell_command = d["command"]
        else:
            if d["stdin"]:
                assert(self.stdin_arg)
                shell_command = "%s %s" % (self.executable, self.stdin_arg)
                quiet = True
            elif do_rcfile:
                assert(self.rcfile_arg)
                shell_command = "%s %s" % (self.executable, self.rcfile_arg)
            else:
                shell_command = self.executable

            if do_rcfile:
                # hijack rcfile to insert our own script
                ex = _create_ex()
                _record_shell(ex, files=files, print_msg=(not quiet))
                filename = "rcfile.%s" % self.file_extension()
                filepath = _write_shell(ex, filename)
                shell_command += " %s" % filepath
            elif envvar:
                # hijack env-var to insert our own script
                ex = _create_ex()
                _record_shell(ex, files=files, print_msg=(not quiet))
                filename = "%s.%s" % (envvar, self.file_extension())
                filepath = _write_shell(ex, filename)
                executor.setenv(envvar, filepath)
            else:
                # hijack $HOME to insert our own script
                files = [x for x in files if x not in bind_files] + list(bind_files)

                if files:
                    for file_ in files:
                        if file_ in bind_files:
                            bind_rez = True
                            files_ = [file_] if d["source_bind_files"] else []
                        else:
                            bind_rez = False
                            files_ = [file_]

                        ex = _create_ex()
                        ex.setenv('HOME', os.environ.get('HOME', ''))
                        _record_shell(ex, files=files_, bind_rez=bind_rez,
                                      print_msg=bind_rez)
                        _write_shell(ex, os.path.basename(file_))

                    executor.setenv("HOME", tmpdir)

                    # keep history
                    if self.histfile and self.histvar:
                        histfile = os.path.expanduser(self.histfile)
                        if os.path.exists(histfile):
                            executor.setenv(self.histvar, histfile)
                else:
                    if config.warn("shell_startup"):
                        print_warning(
                            "WARNING: Could not configure environment from "
                            "within the target shell (%s); this has been done "
                            "in the parent process instead." % self.name())
                    executor.source(context_file)

        if shell_command:  # an empty string means 'run no command and exit'
            executor.command(shell_command)
        executor.command("exit %s" % self.last_command_status)

        code = executor.get_output()
        target_file = os.path.join(tmpdir, "rez-shell.%s" % self.file_extension())
        with open(target_file, 'w') as f:
            f.write(code)

        if d["stdin"] and stdin and (stdin is not True):
            Popen_args["stdin"] = stdin

        cmd = []
        if pre_command:
            if isinstance(pre_command, basestring):
                cmd = pre_command.strip().split()
            else:
                cmd = pre_command
        cmd.extend([self.executable, target_file])

        try:
            p = Popen(cmd, env=env, **Popen_args)
        except Exception as e:
            cmd_str = ' '.join(map(pipes.quote, cmd))
            raise RezSystemError("Error running command:\n%s\n%s"
                                 % (cmd_str, str(e)))
        return p

    def resetenv(self, key, value, friends=None):
        self._addline(self.setenv(key, value))

    def info(self, value):
        for line in value.split('\n'):
            line = self.escape_string(line)
            self._addline('echo %s' % line)

    def error(self, value):
        for line in value.split('\n'):
            line = self.escape_string(line)
            self._addline('echo %s 1>&2' % line)

    # escaping is allowed in args, but not in program string
    def command(self, value):
        if is_non_string_iterable(value):
            it = iter(value)
            cmd = EscapedString.disallow(next(it))
            args_str = ' '.join(self.escape_string(x) for x in it)
            value = "%s %s" % (cmd, args_str)
        else:
            value = EscapedString.disallow(value)
        self._addline(value)

    def comment(self, value):
        value = EscapedString.demote(value)
        for line in value.split('\n'):
            self._addline('# %s' % line)

    def shebang(self):
        self._addline("#!%s" % self.executable)

    @classmethod
    def get_all_key_tokens(cls, key):
        return ["${%s}" % key, "$%s" % key]

    @classmethod
    def join(cls, command):
        return shlex_join(command)

    @classmethod
    def line_terminator(cls):
        return "\n"

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
