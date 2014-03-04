import sys
import select
import os
import os.path
import subprocess
from rez.settings import settings
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
    def get_syspaths(cls):
        if not cls.syspaths:
            cmd = "cmd=`which %s`; unset PATH; $cmd %s %s 'echo __PATHS_ $PATH'" \
                  % (cls.name(), cls.norc_arg, cls.command_arg)
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, shell=True)
            out_,err_ = p.communicate()
            if p.returncode:
                raise RuntimeError("Could not get executable paths: %s" % err_)
            else:
                lines = out_.split('\n')
                line = [x for x in lines if "__PATHS_" in x.split()][0]
                paths = line.strip().split()[-1].split(os.pathsep)
                cls.syspaths = [x for x in paths if x]
        return cls.syspaths

    @classmethod
    def startup_capabilities(cls, rcfile=False, norc=False, command=False, stdin=False):
        cls._unsupported_option('rcfile', rcfile)
        rcfile = False
        if command:
            cls._overruled_option('stdin', 'command', stdin)
            stdin = False
        return (norc, rcfile, command, stdin)

    @classmethod
    def get_startup_sequence(cls, rcfile, norc, stdin, command):
        rcfile, norc, stdin, command = \
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
            source_bind_files=False
        )

    def _bind_interactive_rez(self):
        if settings.prompt:
            stored_prompt = os.getenv("$REZ_STORED_PROMPT")
            curr_prompt = stored_prompt or os.getenv("$PS1", "\\h:\\w]$ ")
            if not stored_prompt:
                self.setenv("REZ_STORED_PROMPT", curr_prompt)

            new_prompt = "\[\e[1m\]$REZ_ENV_PROMPT\[\e[0m\]"
            new_prompt = (new_prompt+" %s") if settings.prefix_prompt \
                else ("%s "+new_prompt)
            new_prompt = new_prompt % curr_prompt
            self._addline('export PS1="%s"' % new_prompt)

        completion = os.path.join(module_root_path, "_sys", "complete.sh")
        self.source(completion)

    def setenv(self, key, value):
        self._addline('export %s="%s"' % (key, value))

    def unsetenv(self, key):
        self._addline("unset %s" % key)

    def alias(self, key, value):
        self._addline("{key}() {{ {value}; }};export -f {key};".format( \
            key=key, value=value))

    def _saferefenv(self, key):
        pass


class SHFactory(plugin_factory.RezPluginFactory):
    def target_type(self):
        return SH
