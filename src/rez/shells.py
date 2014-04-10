"""
Pluggable API for creating subshells using different programs, such as bash.
"""
from rez.rex import RexExecutor, ActionInterpreter
from rez.settings import settings
from rez.util import which, shlex_join
import subprocess
import os.path
import sys



def get_shell_types():
    """Returns the available shell types: bash, tcsh etc."""
    from rez.plugin_managers import shell_plugin_manager
    return shell_plugin_manager().get_plugins()


def create_shell(shell=None, **kwargs):
    """Returns a Shell of the given type, or the current shell type if shell
    is None."""
    if not shell:
        from rez.system import system
        shell = system.shell

    from rez.plugin_managers import shell_plugin_manager
    return shell_plugin_manager().create_instance(shell, **kwargs)



class Shell(ActionInterpreter):
    """
    Class representing a shell, such as bash or tcsh.
    """
    @classmethod
    def name(cls):
        raise NotImplementedError

    @classmethod
    def file_extension(cls):
        raise NotImplementedError

    @classmethod
    def startup_capabilities(cls, rcfile=False, norc=False, command=False, stdin=False):
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
        line_sep = '\n' if manager.output_style == 'file' else ';'
        script = line_sep.join(self._lines)
        script += line_sep
        return script

    def new_shell(self):
        """
        @returns A new, reset shell of the same type.
        """
        return type(self)()

    def spawn_shell(self, context_file, tmpdir, rcfile=None, norc=False,
                    stdin=False, command=None, quiet=False, **Popen_args):
        """
        Spawn a possibly interactive subshell.
        @param context_file File that must be sourced in the new shell, this
            configures the Rez environment.
        @param tmpdir Tempfiles, if needed, should be created within this path.
        @param rcfile Custom startup script.
        @param norc Don't run startup scripts. Overrides rcfile.
        @param stdin If True, read commands from stdin in a non-interactive shell.
            If a different non-False value, such as subprocess.PIPE, the same
            occurs, but stid is also passed to the resulting subprocess.Popen object.
        @param command If not None, execute this command in a non-interactive shell.
        @param quiet If True, don't show the configuration summary, and suppress
            any stdout from startup scripts.
        @param popen_args args to pass to the shell process object constructor.
        @returns A subprocess.Popen object representing the shell process.
        """
        raise NotImplementedError


class UnixShell(Shell):
    """
    A base class for common *nix shells, such as bash and tcsh.
    """
    executable = None
    rcfile_arg = None
    norc_arg = None
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
        if val and settings.warn_shell_startup:
            print >> sys.stderr, "WARNING: %s ignored, not supported by %s shell" \
                                 % (option, cls.name())

    @classmethod
    def _overruled_option(cls, option, overruling_option, val):
        if val and settings.warn_shell_startup:
            print >> sys.stderr, ("WARNING: %s ignored by %s shell - " + \
                "overruled by %s option") % (option, cls.name(), overruling_option)

    def spawn_shell(self, context_file, tmpdir, rcfile=None, norc=False,
                    stdin=False, command=None, quiet=False, **Popen_args):

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
            for file in files:
                if os.path.exists(os.path.expanduser(file)):
                    ex.source(file)
            if envvar:
                ex.unsetenv(envvar)
            if bind_rez:
                ex.interpreter._bind_interactive_rez()
            if print_msg and not quiet:
                ex.info('')
                ex.info('You are now in a rez-configured environment.')
                ex.info('')
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
                               bind_rez=False,
                               bind_syspaths=False,
                               add_default_namespaces=False)

        executor = _create_ex()

        if settings.prompt:
            newprompt = '${REZ_ENV_PROMPT}%s' % settings.prompt
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
                        ex.setenv('HOME', os.environ.get('HOME',''))
                        _record_shell(ex, files=files_, bind_rez=bind_rez,
                                      print_msg=bind_rez)
                        _write_shell(ex, os.path.basename(file))

                    executor.setenv("HOME", tmpdir)
                else:
                    if settings.warn_shell_startup:
                        print >> sys.stderr, ("WARNING: Could not configure "
                        "environment from within the target shell (%s); this "
                        "has been done in the parent process instead.") % self.name()
                    executor.source(context_file)

        executor.command(shell_command)
        # TODO this could be more cross-shell...
        executor.command("exit $?")

        code = executor.get_output()
        target_file = os.path.join(tmpdir, "rez-shell.%s" % self.file_extension())
        with open(target_file, 'w') as f:
            f.write(code)

        if d["stdin"] and stdin and (stdin is not True):
            Popen_args["stdin"] = stdin

        p = subprocess.Popen([self.executable, self.norc_arg, target_file], **Popen_args)
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
