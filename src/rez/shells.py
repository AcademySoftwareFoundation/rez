"""
Pluggable API for creating subshells using different programs, such as bash.
"""
from rez.rex import RexExecutor, ActionInterpreter, OutputStyle
from rez.util import which, shlex_join, print_warning
from rez.config import config
from rez.system import system
import subprocess
import os.path


def get_shell_types():
    """Returns the available shell types: bash, tcsh etc."""
    from rez.plugin_managers import plugin_manager
    return plugin_manager.get_plugins('shell')


def create_shell(shell=None, **kwargs):
    """Returns a Shell of the given type, or the current shell type if shell
    is None."""
    if not shell:
        from rez.system import system
        shell = system.shell

    from rez.plugin_managers import plugin_manager
    return plugin_manager.create_instance('shell', shell, **kwargs)


class Shell(ActionInterpreter):
    """Class representing a shell, such as bash or tcsh.
    """
    @classmethod
    def name(cls):
        raise NotImplementedError

    @classmethod
    def file_extension(cls):
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

    def _addline(self, line):
        self._lines.append(line)

    def get_output(self, manager):
        if manager.output_style == OutputStyle.file:
            script = '\n'.join(self._lines) + '\n'
        elif manager.output_style == OutputStyle.eval:
            lines = []
            for line in self._lines:
                if not line.startswith('#'):  # strip comments
                    line = line.rstrip().rstrip(';')
                    lines.append(line)
            script = ';'.join(lines)
        else:
            raise ValueError("Unknown output style: %r" % manager.output_style)

        return script

    def new_shell(self):
        """Returns A new, reset shell of the same type."""
        return type(self)()

    def spawn_shell(self, context_file, tmpdir, rcfile=None, norc=False,
                    stdin=False, command=None, env=None, quiet=False,
                    pre_command=None, **Popen_args):
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
            env: Environ dict to execute the shell within; uses the current
                environment if None.
            quiet: If True, don't show the configuration summary, and suppress
                any stdout from startup scripts.
            pre_command: Command to inject before the shell command itself. This
                is for internal use.
            popen_args: args to pass to the shell process object constructor.

        Returns:
            A subprocess.Popen object representing the shell process.
        """
        raise NotImplementedError


class UnixShell(Shell):
    """
    A base class for common *nix shells, such as bash and tcsh.
    """
    executable = None
    rcfile_arg = None
    norc_arg = None
    histfile = None
    histvar = None
    command_arg = '-c'
    stdin_arg = '-s'
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
    def find_executable(cls, name):
        exe = which(name)
        if not exe:
            raise RuntimeError("Couldn't find executable '%s' for shell type '%s'"
                               % (name, cls.name()))
        return exe

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

    def spawn_shell(self, context_file, tmpdir, rcfile=None, norc=False,
                    stdin=False, command=None, env=None, quiet=False,
                    pre_command=None, **Popen_args):

        d = self.get_startup_sequence(rcfile, norc, bool(stdin), command)
        envvar = d["envvar"]
        files = d["files"]
        bind_files = d["bind_files"]
        do_rcfile = d["do_rcfile"]
        shell_command = None

        def _record_shell(ex, files, bind_rez=True, print_msg=False):
            # TODO make context sourcing position configurable?
            if bind_rez:
                ex.source(context_file)
            for file_ in files:
                if os.path.exists(os.path.expanduser(file_)):
                    ex.source(file_)
            if envvar:
                ex.unsetenv(envvar)
            if bind_rez:
                ex.interpreter._bind_interactive_rez()
            if print_msg and not quiet:
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

        if config.prompt:
            newprompt = '${REZ_ENV_PROMPT}%s' % config.prompt
            executor.interpreter._saferefenv('REZ_ENV_PROMPT')
            executor.env.REZ_ENV_PROMPT = newprompt

        if d["command"]:
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
                    for file in files:
                        if file in bind_files:
                            bind_rez = True
                            files_ = [file] if d["source_bind_files"] else []
                        else:
                            bind_rez = False
                            files_ = [file]

                        ex = _create_ex()
                        ex.setenv('HOME', os.environ.get('HOME', ''))
                        _record_shell(ex, files=files_, bind_rez=bind_rez,
                                      print_msg=bind_rez)
                        _write_shell(ex, os.path.basename(file))

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

        executor.command(shell_command)
        # TODO this could be more cross-shell...
        executor.command("exit $?")

        code = executor.get_output()
        target_file = os.path.join(tmpdir, "rez-shell.%s"
                                   % self.file_extension())
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
        cmd = cmd + [self.executable, self.norc_arg, target_file]
        p = subprocess.Popen(cmd, env=env, **Popen_args)
        return p

    def resetenv(self, key, value, friends=None):
        self._addline(self.setenv(key, value))

    def info(self, value):
        for line in value.split('\n'):
            self._addline('echo "%s"' % line)

    def error(self, value):
        for line in value.split('\n'):
            self._addline('echo "%s" 1>&2' % line)

    def command(self, value):
        value = shlex_join(value)
        self._addline(value)

    def comment(self, value):
        for line in value.split('\n'):
            self._addline('# %s' % line)

    def source(self, value):
        self._addline('source "%s"' % os.path.expanduser(value))

    def shebang(self):
        self._addline("#!%s" % self.executable)
