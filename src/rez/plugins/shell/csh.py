import os.path
import subprocess
from rez import plugin_factory
from rez.settings import settings
from rez.shells import UnixShell
from rez.util import get_script_path
from rez import module_root_path



class CSH(UnixShell):
    executable = UnixShell.find_executable('csh')
    norc_arg = '-f'

    @classmethod
    def name(cls):
        return 'csh'

    @classmethod
    def file_extension(cls):
        return 'csh'

    @classmethod
    def get_syspaths(cls):
        if not cls.syspaths:
            cmd = "cmd=`which %s`; unset PATH; $cmd %s 'echo __PATHS_ $PATH'" \
                  % (cls.name(), cls.command_arg)
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

        files = []
        if not norc:
            for file in (
                    "~/.tcshrc",
                    "~/.cshrc",
                    "~/.login",
                    "~/.cshdirs"):
                if os.path.exists(os.path.expanduser(file)):
                    files.append(file)

        return dict(
            stdin=stdin,
            command=command,
            do_rcfile=False,
            envvar=None,
            files=files,
            bind_files=(
                "~/.tcshrc",
                "~/.cshrc"),
            source_bind_files=(not norc)
        )

    def _bind_interactive_rez(self):
        if settings.prompt:
            stored_prompt = os.getenv("$REZ_STORED_PROMPT")
            curr_prompt = stored_prompt or os.getenv("$prompt", "[%m %c]%# ")
            if not stored_prompt:
                self.setenv("REZ_STORED_PROMPT", curr_prompt)

            new_prompt = "$REZ_ENV_PROMPT"
            new_prompt = (new_prompt+" %s") if settings.prefix_prompt \
                else ("%s "+new_prompt)
            new_prompt = new_prompt % curr_prompt
            self._addline('set prompt="%s"' % new_prompt)

        completion = os.path.join(module_root_path, "_sys", "complete.csh")
        self.source(completion)

    def _saferefenv(self, key):
        self._addline("if (!($?%s)) setenv %s" % (key,key))

    def setenv(self, key, value):
        self._addline('setenv %s "%s"' % (key, value))

    def unsetenv(self, key):
        self._addline("unsetenv %s" % key)

    def alias(self, key, value):
        self._addline("alias %s '%s';" % (key, value))


class CSHFactory(plugin_factory.RezPluginFactory):
    def target_type(self):
        return CSH
