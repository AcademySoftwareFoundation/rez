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

    def bind_rez_cli(self, recorder):
        recorder.prependenv('PATH', get_script_path())
        recorder.setprompt("$REZ_ENV_PROMPT $prompt")
        return recorder

    def setenv(self, key, value):
        return 'setenv %s "%s"' % (key, value)

    def unsetenv(self, key):
        return "unsetenv %s" % (key,)

    def prependenv(self, key, value):
        return 'setenv %(key)s="%(value)s%(sep)s$%(key)s"' % dict(
            key=key,
            value=value,
            sep=self._env_sep(key))

    def appendenv(self, key, value):
        return 'setenv %(key)s="$%(key)s%(sep)s%(value)s"' % dict(
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
