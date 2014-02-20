"""
Pluggable API for creating subshells using different programs, such as bash.
"""
from rez.rex import ActionInterpreter
from rez.settings import settings
from rez.util import which, shlex_join
import subprocess
import os.path



def get_shell_types():
    """
    Returns the available shell types: bash, tcsh etc.
    """
    from rez.plugin_managers import shell_plugin_manager
    return shell_plugin_manager.get_plugins()


def create_shell(shell=None, **kwargs):
    """
    Returns a Shell of the given type, or the current shell type if shell is None.
    """
    from rez.plugin_managers import shell_plugin_manager
    return shell_plugin_manager.create_instance(shell=shell, **kwargs)


"""
def interpret(commands, shell=None, **kwargs):
    from rez.plugin_managers import shell_plugin_manager

    sh = shell_plugin_manager.create_instance(shell=shell, **kwargs)
    if isinstance(commands, CommandRecorder):
        commands = commands.commands
    return sh._execute(commands)
"""

def spawn_shell(context_file, shell=None, rcfile=None, norc=False, stdin=False,
                command=None, quiet=False, get_stdout=False, get_stderr=False,
                **kwargs):
    """
    Spawn a child shell process.
    """
    from rez.plugin_managers import shell_plugin_manager

    sh = shell_plugin_manager.create_instance(shell=shell, **kwargs)
    return sh.spawn_shell(context_file,
                   rcfile=rcfile,
                   stdin=stdin,
                   command=command,
                   quiet=quiet,
                   get_stdout=get_stdout,
                   get_stderr=get_stderr)


class Shell(ActionInterpreter):
    @classmethod
    def name(cls):
        raise NotImplementedError

    @classmethod
    def file_extension(cls):
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

    def spawn_shell(self, context_file, rcfile=None, norc=False, stdin=False,
                    command=None, quiet=False, get_stdout=False, get_stderr=False):
        """
        Spawn a possibly interactive subshell.
        @param context_file File that must be sourced in the new shell, this
            configures the Rez environment.
        @param rcfile Custom startup script.
        @param norc Don't run startup scripts. Overrides rcfile.
        @param stdin If True, read commands from stdin in a non-interactive shell.
        @param command If not None, execute this command in a non-interactive shell.
        @param quiet If True, don't show the configuration summary, and suppress
            any stdout from startup scripts.
        @param get_stdout Capture stdout.
        @param get_stderr Capture stderr.
        @returns (returncode, stdout, stderr), where stdout/err are None if the
            corresponding get_stdxxx param was False.
        """
        raise NotImplementedError


class UnixShell(Shell):
    executable = None
    rcfile_arg = None
    norc_arg = None
    stdin_arg = '-s'

    #
    # startup rules
    #

    @classmethod
    def find_executable(cls, *names):
        exe = which(*names)
        if not exe:
            raise RuntimeError("Couldn't find executable for shell type '%s'" % cls.name())
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

    def bind_rez_cli(self, recorder):
        """ Make rez cli visible in the current shell """
        raise NotImplementedError

    @classmethod
    def _ignore_bool_option(cls, option, val):
        if val and settings.warn_shell_startup:
            print >> sys.stderr, "WARNING: %s ignored by %s shell" % (option, cls.name())

    def spawn_shell(self, context_file, rcfile=None, norc=False, stdin=False,
                    command=None, quiet=False, get_stdout=False, get_stderr=False):
        recorder = CommandRecorder()
        recorder.setenv('REZ_CONTEXT_FILE', context_file)
        recorder.setenv('REZ_ENV_PROMPT', '${REZ_ENV_PROMPT}%s' % '>')

        # TODO hook up prompt symbol once more
        # TODO fix this properly
        #recorder.appendenv('REZ_ENV_PROMPT', '>')
        # some shells don't like references to undefined vars
        #if os.getenv('REZ_ENV_PROMPT') is None:
        #    recorder.setenv('REZ_ENV_PROMPT', '>')
        #else:
        #    recorder.setenv('REZ_ENV_PROMPT', '${REZ_ENV_PROMPT}%s' % '>')
        #if os.getenv('REZ_REQUEST') is None:
        #    recorder.setenv('REZ_REQUEST', '')

        d = self.get_startup_sequence(rcfile, norc, stdin, command)
        envvar = d["envvar"]
        files = d["files"]
        bind_files = d["bind_files"]
        do_rcfile = d["do_rcfile"]
        shell_command = None

        def _record_shell(r, files, bind_rez=True, print_msg=False):
            # TODO make context sourcing position configurable?
            if bind_rez:
                r.source(context_file)
            for file in files:
                r.source(file)
            if envvar:
                r.unsetenv(envvar)
            if bind_rez:
                self.bind_rez_cli(r)
            if print_msg and not quiet:
                r.info('')
                r.info('You are now in a rez-configured environment.')
                r.command('rezolve context-info')

        def _write_shell(r, filename):
            script = self._execute(r.commands, output_style='file')
            target_file = tmpfile(filename)
            with open(target_file, 'w') as f:
                f.write(script)
            return target_file

        if d["command"]:
            _record_shell(recorder, files=files)
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
                rec = CommandRecorder()
                _record_shell(rec, files=files, print_msg=(not quiet))
                filename = "rcfile.%s" % self.file_extension()
                filepath = _write_shell(rec, filename)
                shell_command += " %s" % filepath
            elif envvar:
                # hijack env-var to insert our own script
                rec = CommandRecorder()
                _record_shell(rec, files=files, print_msg=(not quiet))
                filename = "%s.%s" % (envvar, self.file_extension())
                filepath = _write_shell(rec, filename)
                recorder.setenv(envvar, filepath)
            else:
                # hijack $HOME to insert our own script
                files = [x for x in files if x not in bind_files] + list(bind_files)
                if files:
                    for file in files:
                        rec = CommandRecorder()
                        rec.setenv('HOME', os.environ.get('HOME',''))
                        if file in bind_files:
                            bind_rez = True
                            files_ = [file] if d["source_bind_files"] else []
                        else:
                            bind_rez = False
                            files_ = [file]

                        _record_shell(rec, files=files_, bind_rez=bind_rez,
                                      print_msg=bind_rez)
                        _write_shell(rec, os.path.basename(file))

                    recorder.setenv("HOME", get_tmpdir())
                else:
                    if settings.warn_shell_startup:
                        print >> sys.stderr, "WARNING: Could not configure environment " + \
                            "from within the target shell; this has been done in the " + \
                            "parent process instead."
                    recorder.source(context_file)

        recorder.command(shell_command)
        recorder.command("exit $?")
        script = self._execute(recorder.commands, output_style='file')

        target_file = tmpfile("rez-shell.%s" % self.file_extension())
        with open(target_file, 'w') as f:
            f.write(script)

        p = subprocess.Popen([self.executable, self.norc_arg, target_file],
                             stdout=subprocess.PIPE if get_stdout else None,
                             stderr=subprocess.PIPE if get_stderr else None)

        out_, err_ = p.communicate()
        return (p.returncode,
                out_ if get_stdout else None,
                err_ if get_stderr else None)

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
        self._addline('source "%s"' % value)

    def shebang(self):
        self._addline("#!%s" % self.executable)
