"""
SH shell
"""
import sys
import select
import os
import os.path
import subprocess
from rez.config import config
from rez import module_root_path
from rez.shells import UnixShell


class SH(UnixShell):
    executable = UnixShell.find_executable('sh')
    norc_arg = '--noprofile'
    histfile = "~/.bash_history"
    histvar = "HISTFILE"

    @classmethod
    def name(cls):
        return 'sh'

    @classmethod
    def file_extension(cls):
        return 'sh'

    @classmethod
    def get_syspaths(cls):
        if not cls.syspaths:
            cmd = "cmd=`which %s`; unset PATH; $cmd %s %s 'echo __PATHS_ $PATH'" \
                  % (cls.name(), cls.norc_arg, cls.command_arg)
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, shell=True)
            out_, err_ = p.communicate()
            if p.returncode:
                paths = []
            else:
                lines = out_.split('\n')
                line = [x for x in lines if "__PATHS_" in x.split()][0]
                paths = line.strip().split()[-1].split(os.pathsep)

            for path in os.defpath.split(os.path.pathsep):
                if path not in paths:
                    paths.append(path)
            cls.syspaths = [x for x in paths if x]
        return cls.syspaths

    @classmethod
    def startup_capabilities(cls, rcfile=False, norc=False, stdin=False,
                             command=False):
        cls._unsupported_option('rcfile', rcfile)
        rcfile = False
        if command:
            cls._overruled_option('stdin', 'command', stdin)
            stdin = False
        return (rcfile, norc, stdin, command)

    @classmethod
    def get_startup_sequence(cls, rcfile, norc, stdin, command):
        _, norc, stdin, command = \
            cls.startup_capabilities(rcfile, norc, stdin, command)

        envvar = None
        files = []

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
            source_bind_files=False)

    def _bind_interactive_rez(self):
        if config.prompt:
            stored_prompt = os.getenv("$REZ_STORED_PROMPT")
            curr_prompt = stored_prompt or os.getenv("$PS1", "\\h:\\w]$ ")
            if not stored_prompt:
                self.setenv("REZ_STORED_PROMPT", curr_prompt)

            new_prompt = "\[\e[1m\]$REZ_ENV_PROMPT\[\e[0m\]"
            new_prompt = (new_prompt + " %s") if config.prefix_prompt \
                else ("%s " + new_prompt)
            new_prompt = new_prompt % curr_prompt
            self._addline('export PS1="%s"' % new_prompt)

        completion = os.path.join(module_root_path, "_sys", "complete.sh")
        self.source(completion)

    def setenv(self, key, value):
        self._addline('export %s="%s"' % (key, value))

    def unsetenv(self, key):
        self._addline("unset %s" % key)

    def alias(self, key, value):
        cmd = "function {key}() {{ {value}; }};export -f {key};"
        self._addline(cmd.format(key=key, value=value))

    def _saferefenv(self, key):
        pass


def register_plugin():
    return SH
