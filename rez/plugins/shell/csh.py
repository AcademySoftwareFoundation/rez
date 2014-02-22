import os.path
from rez import plugin_factory
from rez.settings import settings
from rez.shells import UnixShell
from rez.util import get_script_path



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
    def get_startup_sequence(cls, rcfile, norc, stdin, command):
        cls._ignore_bool_option('rcfile', rcfile)
        files = []

        if command:
            cls._ignore_bool_option('stdin', stdin)
            stdin = False
        if stdin and not select.select([sys.stdin,],[],[],0.0)[0]:  # tests stdin
            stdin = False

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
