import os.path
from rez import plugin_factory
from rez.shells import UnixShell
from rez.util import get_script_path



class CSH(UnixShell):
    executable = UnixShell.find_executable('csh')
    file_extension = 'csh'
    norc_arg = '-f'

    @classmethod
    def name(cls):
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
                    "~/.history",
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

    def bind_rez_cli(self, recorder):
        recorder.prependenv('PATH', get_script_path())
        curr_prompt = os.getenv("$prompt", "[%m %c]%# ")
        recorder.setprompt("$REZ_ENV_PROMPT %s" % curr_prompt)
        return recorder

    def setenv(self, key, value):
        return 'setenv %s "%s"' % (key, value)

    def unsetenv(self, key):
        return "unsetenv %s" % (key,)

    def prependenv(self, key, value):
        return 'setenv %(key)s "%(value)s%(sep)s${%(key)s}"' % dict(
            key=key,
            value=value,
            sep=self._env_sep(key))

    def appendenv(self, key, value):
        return 'setenv %(key)s "${%(key)s}%(sep)s%(value)s"' % dict(
            key=key,
            value=value,
            sep=self._env_sep(key))

    def alias(self, key, value):
        return "alias %s '%s';" % (key, value)

    def setprompt(self, value):
        return 'set prompt="%s"' % value


class CSHFactory(plugin_factory.RezPluginFactory):
    def target_type(self):
        return CSH
