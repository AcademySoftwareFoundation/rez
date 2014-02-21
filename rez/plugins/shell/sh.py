import sys
import select
import os
import os.path
import subprocess
from rez import module_root_path, plugin_factory
from rez.shells import UnixShell
from rez.util import get_script_path



class SH(UnixShell):
    executable = UnixShell.find_executable('sh')
    norc_arg = '--noprofile'

    @classmethod
    def name(cls):
        return 'sh'

    @classmethod
    def file_extension(cls):
        return 'sh'

    @classmethod
    def get_startup_sequence(cls, rcfile, norc, stdin, command):
        cls._ignore_bool_option('rcfile', rcfile)
        envvar = None
        files = []

        if command:
            cls._ignore_bool_option('stdin', stdin)
            stdin = False
        if stdin and not select.select([sys.stdin,],[],[],0.0)[0]:  # tests stdin
            stdin = False
        if not (command or stdin):
            if not norc:
                for file in ("~/.profile",):
                    if os.path.exists(os.path.expanduser(file)):
                        files.append(file)
            envvar = 'ENV'
            path = os.getenv(envvar)
            if path and os.path.isfile(os.path.expanduser(path)):
                files.append(path)

        return dict(
            stdin=stdin,
            command=command,
            do_rcfile=False,
            envvar=envvar,
            files=files,
            bind_files=[],
            source_bind_files=False
        )

    """
    def bind_rez_cli(self, executor):
        curr_prompt = os.getenv("$PS1", "\\h:\\w]$ ")
        executor.setprompt("\[\e[1m\]$REZ_ENV_PROMPT\[\e[0m\] %s" % curr_prompt)
        completion = os.path.join(module_root_path, "_sys", "bash_completion")
        executor.source(completion)
    """

    def bind_interactive_rez(self):
        curr_prompt = os.getenv("$PS1", "\\h:\\w]$ ")
        new_prompt = "\[\e[1m\]$REZ_ENV_PROMPT\[\e[0m\] %s" % curr_prompt
        self._addline('export PS1="%s"' % new_prompt)
        completion = os.path.join(module_root_path, "_sys", "bash_completion")
        self.source(completion)

    def setenv(self, key, value):
        self._addline('export %s="%s"' % (key, value))

    def unsetenv(self, key):
        self._addline("unset %s" % key)

    def alias(self, key, value):
        self._addline("{key}() {{ {value}; }};export -f {key};".format( \
            key=key, value=value))

    def setprompt(self, value):
        self._addline('export PS1="%s"' % value)


class SHFactory(plugin_factory.RezPluginFactory):
    def target_type(self):
        return SH
