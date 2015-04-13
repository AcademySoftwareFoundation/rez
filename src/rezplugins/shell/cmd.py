"""
Windows Command Prompt (DOS) shell.
"""
from rez.config import config
from rez.rex import RexExecutor, literal
from rez.shells import Shell
from rez.system import system
from rez.utils.platform_ import platform_
from rez.util import shlex_join
import os
import re
import subprocess


class CMD(Shell):
    # For reference, the ss64 web page provides useful documentation on builtin
    # commands for the Windows Command Prompt (cmd).  It can be found here :
    # http://ss64.com/nt/cmd.html
    executable = Shell.find_executable('cmd')
    syspaths = None

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
        if not cls.syspaths:
            paths = []

            cmd = ["REG", "QUERY", "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment", "/v", "PATH"]
            expected = "\r\nHKEY_LOCAL_MACHINE\\\\SYSTEM\\\\CurrentControlSet\\\\Control\\\\Session Manager\\\\Environment\r\n    PATH    REG_(EXPAND_)?SZ    (.*)\r\n\r\n"

            p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, shell=True)
            out_, _ = p.communicate()

            if p.returncode == 0:
                match = re.match(expected, out_)
                if match:
                    paths.extend(match.group(2).split(os.pathsep))

            cmd = ["REG", "QUERY", "HKCU\\Environment", "/v", "PATH"]
            expected = "\r\nHKEY_CURRENT_USER\\\\Environment\r\n    PATH    REG_(EXPAND_)?SZ    (.*)\r\n\r\n"
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, shell=True)
            out_, _ = p.communicate()

            if p.returncode == 0:
                match = re.match(expected, out_)
                if match:
                    paths.extend(match.group(2).split(os.pathsep))

            cls.syspaths = set([x for x in paths if x])
        return cls.syspaths

    def _bind_interactive_rez(self):
        if self.settings.prompt:
            stored_prompt = os.getenv("REZ_STORED_PROMPT")
            curr_prompt = stored_prompt or os.getenv("PROMPT", "foobar")
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
#                ex.info('')
#                ex.info('You are now in a rez-configured environment.')
#                ex.info('')
                if system.is_production_rez_install:
                    ex.command("cmd /Q /K rezolve context")

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
            executor.command(shell_command)
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
        cmd = cmd + [self.executable, "/Q", "/K", target_file]
        p = subprocess.Popen(cmd, env=env, **Popen_args)
        return p

    def escape_string(self, value):
        return value

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
        self._addline("doskey %s=%s" % (key, value))

    def comment(self, value):
        for line in value.split('\n'):
            self._addline(': %s' % line)

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
