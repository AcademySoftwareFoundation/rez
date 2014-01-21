"""
Pluggable API for creating subshells using different programs, such as bash.
"""
from rez.rex import CommandInterpreter, CommandRecorder
from rez.settings import settings
from rez.util import which, tmpfile, get_tmpdir
import subprocess
import os.path



def get_shell_types():
    """ Returns the available shell types: bash, tcsh etc. """
    from rez.plugin_managers import shell_plugin_manager
    return shell_plugin_manager.get_plugins()


def interpret(commands, shell=None, **kwargs):
    from rez.plugin_managers import shell_plugin_manager
    sh = shell_plugin_manager.create_instance(shell=shell, **kwargs)
    if isinstance(commands, CommandRecorder):
        commands = commands.commands
    return sh._execute(commands)


def spawn_shell(context_file, shell=None, rcfile=None, stdin=False,
                command=None, quiet=False, **kwargs):
    """
    Spawn a child shell process.
    """
    from rez.plugin_managers import shell_plugin_manager
    sh = shell_plugin_manager.create_instance(shell=shell, **kwargs)
    sh.spawn_shell(context_file,
                   rcfile=rcfile,
                   stdin=stdin,
                   command=command,
                   quiet=quiet)


class Shell(CommandInterpreter):
    @classmethod
    def name(cls):
        raise NotImplementedError

    def spawn_shell(self, context_file, rcfile=None, stdin=False, command=None, quiet=False):
        """
        Spawn a possibly interactive subshell.
        @param context_file File that must be sourced in the new shell, this configures the
            Rez environment.
        @param rcfile Custom startup script.
        @param stdin If True, read commands from stdin in a non-interactive shell.
        @param command If not None, execute this command in a non-interactive shell.
        @param quiet Whether to show the configuration summary when the shell starts.
        """
        raise NotImplementedError


class UnixShell(Shell):
    executable = None
    file_extension = None
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

    """
    @classmethod
    def find_user_startup_files(cls):
        files = []
        for entry in cls.user_startup_files:
            if isinstance(entry, basestring):
                file = entry
                path = os.path.expanduser('~/'+file)
                if os.path.exists(path):
                    files.append(file)
            else:
                for file in entry:
                    path = os.path.expanduser('~/'+file)
                    if os.path.exists(path):
                        files.append(file)
                        break
        return files

    @classmethod
    def first_user_startup_file(cls):
        if self.user_startup_files:
            entry = self.user_startup_files[0]
            return entry if isinstance(entry, basestring) else entry[0]

    def _write_shell_resource(self, filename, context_file,
                              rcfile=None, quiet=False, bind_rez=False):
        recorder = CommandRecorder()
        recorder.setenv('HOME', os.environ.get('HOME',''))

        path = os.path.expanduser('~/'+filename)
        if os.path.exists(path):
            recorder.source('~/%s' % filename)

        if bind_rez:
            if rcfile:
                recorder.source(rcfile)

            recorder.source(context_file)
            self.bind_rez(recorder)

            if not quiet:
                recorder.info('')
                recorder.info('You are now in a rez-configured environment.')
                recorder.command('rezolve context-info')

        script = self._execute(recorder.commands, output_style='file')
        target_file = tmpfile(filename)
        with open(target_file, 'w') as f:
            f.write(script)
        return target_file
    """

    # TODO norc
    @classmethod
    def get_startup_sequence(cls, rcfile, stdin, command):
        """
        Return a dict containing:
        - 'stdin': replacement stdin setting.
        - 'command': replacement command setting.
        - 'envvar': Env-var that points at a file to source at startup. Can be None.
        - 'files': Existing files that will be sourced (non-user-expanded), in source
            order. This may also incorporate rcfile, and file pointed at via envvar.
            Can be empty.
        - 'default_file': The 'default' startup file (such as '.bashrc'), whether
            or not it exists. Can be None.
        """
        raise NotImplementedError

    def bind_rez_cli(self, recorder):
        """ Make rez cli visible in the current shell """
        raise NotImplementedError

    @classmethod
    def _ignore_bool_option(cls, option, val):
        if val and settings.warn_shell_startup:
            print >> sys.stderr, "WARNING: %s ignored by %s shell" % (option, cls.name())

    def spawn_shell(self, context_file, rcfile=None, stdin=False, command=None, quiet=False):
        recorder = CommandRecorder()
        recorder.setenv('REZ_CONTEXT_FILE', context_file)
        # TODO hook up prompt symbol once more
        recorder.setenv('REZ_ENV_PROMPT', '${REZ_ENV_PROMPT}%s' % '>')

        d = self.get_startup_sequence(rcfile, stdin, command)
        envvar = d["envvar"]
        files = d["files"]
        default_file = d["default_file"]
        command = None

        def _record_shell(r, quiet=True):
            r.source(context_file)
            for file in files:
                r.source(file)
            if envvar:
                r.unsetenv(envvar)
            self.bind_rez_cli(r)
            if not quiet:
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
            _record_shell(recorder)
            command = d["command"]
        else:
            if d["stdin"]:
                command = "%s %s" % (self.executable, self.stdin_arg)
                quiet = True
            else:
                command = self.executable

            if envvar:
                # hijack envvar to insert our own startup sequence
                rec = CommandRecorder()
                _record_shell(rec, quiet=quiet)
                filename = "%s.%s" % (envvar, self.file_extension)
                filepath = _write_shell(rec, filename)
                recorder.setenv(envvar, filepath)
            elif default_file:
                # hijack $HOME to insert our own startup sequence
                rec = CommandRecorder()
                rec.setenv('HOME', os.environ.get('HOME',''))
                _record_shell(rec, quiet=quiet)
                _write_shell(rec, default_file)
                recorder.setenv("HOME", get_tmpdir())
            else:
                if settings.warn_shell_startup:
                    print >> sys.stderr, "WARNING: Could not configure environment " + \
                        "from within the target shell; this has been done in the " + \
                        "parent process instead."
                recorder.source(context_file)

        recorder.command(command)
        script = self._execute(recorder.commands, output_style='file')
        target_file = tmpfile("rez-shell.%s" % self.file_extension)
        with open(target_file, 'w') as f:
            f.write(script)

        print '>>>>>>>>>>> '+target_file
        p = subprocess.Popen([self.executable, target_file])
        p.wait()

    def info(self, value):
        # TODO: handle newlines
        return 'echo "%s"' % value

    def error(self, value):
        # TODO: handle newlines
        return 'echo "%s" 1>&2' % value

    def command(self, value):
        def quote(s):
            if '$' not in s:
                return pipes.quote(s)
            return s
        if isinstance(value, (list, tuple)):
            value = ' '.join(quote(x) for x in value)
        return str(value)

    def comment(self, value):
        # TODO: handle newlines
        return "# %s" % value

    def source(self, value):
        return 'source "%s"' % os.path.expanduser(value)
