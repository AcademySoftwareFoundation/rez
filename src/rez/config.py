from rez.config_resources import config_schema_required, _config_schema
from rez.resources import load_resource, DataWrapper
from rez.util import deep_update, propertycache, AttrDictWrapper, \
    ObjectStringFormatter
from rez.exceptions import ConfigurationError
from rez import config_resources
from rez.system import system
import os


class Setting(object):
    """Setting subclasses implement lazy setting validators."""
    namespace = dict(system=system)
    formatter = ObjectStringFormatter(AttrDictWrapper(namespace),
                                      expand='unchanged')

    def __init__(self, config, key):
        self.config = config
        self.key = key

    @property
    def _env_var_name(self):
        return "REZ_%s" % self.key.upper()

    def _expand(self, value):
        return value

    def _parse_env_var(self, value):
        raise NotImplementedError

    def validate(self, data):
        data = self._validate(data)
        data = self.schema.validate(data)
        data = self._expand(data)
        return data

    def _validate(self, data):
        # setting in overrides takes precedence
        if self.key in self.config.overrides:
            return self.config.overrides[self.key]
        # next, env-var
        value = os.getenv(self._env_var_name)
        if value is not None:
            return self._parse_env_var(value)
        # next, data unchanged
        if data is not None:
            return data
        # some settings have a programmatic default
        attr = "_get_%s" % self.key
        if hasattr(self.config, attr):
            return getattr(self.config, attr)()
        # setting is None
        return None


class Str(Setting, config_resources.Str):
    def _expand(self, value):
        return self.formatter.format(value)

    def _parse_env_var(self, value):
        return value


class OptionalStr(Str):
    pass


class StrList(Setting, config_resources.StrList):
    sep = ','

    def _expand(self, value):
        return [self.formatter.format(x) for x in value]

    def _parse_env_var(self, value):
        value = value.replace(self.sep, ' ').split()
        return [x for x in value if x]


class PathList(StrList):
    sep = os.pathsep


class Int(Setting, config_resources.Int):
    def _parse_env_var(self, value):
        try:
            return int(value)
        except ValueError:
            raise ConfigurationError("expected %s to be an integer"
                                     % self._env_var_name())


class Bool(Setting, config_resources.Bool):
    true_words = frozenset(["1", "true", "yes", "y", "on"])
    false_words = frozenset(["0", "false", "no", "n", "off"])

    def _parse_env_var(self, value):
        value = value.lower()
        if value in self.true_words:
            return True
        elif value in self.false_words:
            return False
        else:
            words = self.true_words | self.false_words
            raise ConfigurationError(
                "expected $%s to be one of: %s"
                % (self._env_var_name(), ", ".join(words)))


_setting_classes = {
    config_resources.Str:           Str,
    config_resources.OptionalStr:   OptionalStr,
    config_resources.StrList:       StrList,
    config_resources.PathList:      PathList,
    config_resources.Int:           Int,
    config_resources.Bool:          Bool}


class Config(DataWrapper):
    """Rez configuration settings.

    Config files are merged with other config files to create a `Config`
    instance. The 'rezconfig' file in rez acts as the master - other config
    files update the master configuration to create the final config. See the
    comments at the top of 'rezconfig' for more details.
    """
    schema = config_schema_required

    def __init__(self, filepaths, overrides=None):
        """Create a config.

        Args:
            filepaths (list of str): List of config files to load.
            overrides (dict): A dict containing settings that override all
                others. Nested settings are overridden with nested dicts.
        """
        self.filepaths = filepaths
        self.overrides = overrides or {}

    def warn(self, param):
        """Returns True if the warning setting is enabled."""
        return (not self.quiet and
                (self.warn_all or getattr(self, "warn_%s" % param))

    def debug(self, param):
        """Returns True if the debug setting is enabled."""
        return (not self.quiet and
                (self.debug_all or getattr(self, "debug_%s" % param))

    def _validate_key(self, key, value):
        v = _config_schema.get(key)
        if v and issubclass(v, config_resources.Setting):
            cls_ = _setting_classes[v]
            return cls_(self, key).validate(value)
        return value

    def _load_data(self):
        data = {}
        for filepath in self.filepaths:
            data_ = load_resource(0,
                                  filepath=filepath,
                                  resource_keys="config.file",
                                  root_resource_key="folder.config_root")
            deep_update(data, data_)

        deep_update(data, self.overrides)
        return data

    @classmethod
    def _get_master_config(cls):
        pass

    # -- dynamic defaults

    # TODO move into platform_
    def _get_tmpdir(self):
        from rez.system import system
        if system.platform == "windows":
            path = os.getenv("TEMP")
            if path and os.path.isdir(path):
                return path

        return "/tmp"

    # TODO move into platform_
    def _get_image_viewer(self):
        from rez.system import system
        from rez.util import which
        if system.platform == "linux":
            viewer = which("xdg-open", "eog", "kview")
        elif system.platform == "darwin":
            viewer = "open"
        else:
            # os.system("file.jpg") will open in default viewer on windows
            viewer = ''

        # if None, rez will use webbrowser
        return viewer

    # TODO move into platform_
    def _get_editor(self):
        from rez.system import system
        from rez.util import which
        if system.platform == "linux":
            ed = os.getenv("EDITOR")
            if ed is None:
                ed = which("xdg-open", "vim", "vi")
        elif system.platform == "darwin":
            ed = "open"
        else:
            # os.system("file.txt") will open in default editor on windows
            ed = ''

        return ed
