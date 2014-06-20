from rez.config_resources import _config_dict, _to_schema
from rez.resources import load_resource, DataWrapper
from rez.util import deep_update, propertycache, RO_AttrDictWrapper, \
    convert_dicts, AttrDictWrapper
from rez.exceptions import ConfigurationError
from rez.vendor.schema.schema import SchemaError
from rez import config_resources
from rez import module_root_path
import os
import os.path
import copy


class Setting(object):
    """Setting subclasses implement lazy setting validators.

    Note that lazy setting validation only happens on master configuration
    settings - plugin settings are validated on load only.
    """
    def __init__(self, config, key):
        self.config = config
        self.key = key

    @property
    def _env_var_name(self):
        return "REZ_%s" % self.key.upper()

    def _parse_env_var(self, value):
        raise NotImplementedError

    def validate(self, data):
        data = self._validate(data)
        try:
            data = self.schema.validate(data)
        except SchemaError as e:
            raise ConfigurationError("Error in Rez configuration: %s" % str(e))
        return data

    def _validate(self, data):
        # setting in overrides takes precedence
        if self.key in self.config.overrides:
            return self.config.overrides[self.key]
        # next, env-var
        if not self.config.locked:
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
    def _parse_env_var(self, value):
        return value


class OptionalStr(Str):
    pass


class StrList(Setting, config_resources.StrList):
    sep = ','

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


config_schema_required = _to_schema(_config_dict, required=True)


class Config(DataWrapper):
    """Rez configuration settings.

    You should call the `create_config` function, rather than constructing a
    `Config` object directly.

    Config files are merged with other config files to create a `Config`
    instance. The 'rezconfig' file in rez acts as the master - other config
    files update the master configuration to create the final config. See the
    comments at the top of 'rezconfig' for more details.
    """
    schema = config_schema_required

    def __init__(self, filepaths, overrides=None, locked=False):
        """Create a config.

        Args:
            filepaths (list of str): List of config files to load.
            overrides (dict): A dict containing settings that override all
                others. Nested settings are overridden with nested dicts.
            locked: If True, settings overrides in environment variables are
                ignored.
        """
        self.filepaths = filepaths
        self.overrides = overrides or {}
        self.locked = locked

    def warn(self, param):
        """Returns True if the warning setting is enabled."""
        return (not self.quiet and
                (self.warn_all or getattr(self, "warn_%s" % param)))

    def debug(self, param):
        """Returns True if the debug setting is enabled."""
        return (not self.quiet and
                (self.debug_all or getattr(self, "debug_%s" % param)))

    @propertycache
    def plugins(self):
        """Plugin settings are loaded lazily, to avoid loading the plugins
        until necessary."""
        plugin_data = self.metadata.get("plugins", {})
        return _PluginConfigs(plugin_data)

    @propertycache
    def data(self):
        """Returns the entire configuration as a dict.

        Note that this will force all plugins to be loaded.
        """
        d = convert_dicts(self.metadata, dict, (dict, AttrDictWrapper))
        d["plugins"] = self.plugins.to_dict()
        return d

    def _validate_key(self, key, value):
        v = _config_dict.get(key)
        if type(v) is type and issubclass(v, config_resources.Setting):
            cls_ = _setting_classes[v]
            return cls_(self, key).validate(value)
        return value

    def _load_data(self):
        data = {}
        for filepath in self.filepaths:
            data_ = load_resource(0,
                                  filepath=filepath,
                                  resource_keys="config.main",
                                  root_resource_key="folder.config_root")
            deep_update(data, data_)

        deep_update(data, self.overrides)
        return data

    @classmethod
    def _get_main_config(cls):
        """See comment block at top of 'rezconfig' describing how the main
        config is assembled."""
        filepaths = []
        filepaths.append(os.path.join(module_root_path, "rezconfig"))
        filepath = os.getenv("REZ_CONFIG_FILE")
        if filepath and os.path.isfile(filepath):
            filepaths.append(filepath)
        user_filepath = os.path.expanduser("~/.rezconfig")
        if os.path.isfile(user_filepath):
            filepaths.append(filepath)
        return Config(filepaths)

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


class _PluginConfigs(object):
    """Lazy config loading for plugins."""
    def __init__(self, plugin_data):
        self.__dict__['data'] = plugin_data

    def __setattr__(self, attr, value):
        raise AttributeError("'%s' object attribute '%s' is read-only"
                             % (self.__class__.__name__, attr))

    def __getattr__(self, attr):
        if attr == "data":
            raise AttributeError("no such attribute 'data'")
        if attr in self.__dict__:
            return self.__dict__[attr]

        data = self.__dict__['data']
        from rez.plugin_managers import plugin_manager
        if attr in plugin_manager.get_plugin_types():
            config_data = plugin_manager.get_plugin_config_data(attr)
            d = copy.deepcopy(config_data)
            if attr in data:
                # data may contain `AttrDictWrapper`s, which break schema
                # validation, hence the dict conversion here
                plugin_data = convert_dicts(data[attr], dict,
                                            (dict, AttrDictWrapper))
                deep_update(d, plugin_data)
            # validate
            schema = plugin_manager.get_plugin_config_schema(attr)
            try:
                d = schema.validate(d)
            except SchemaError as e:
                raise ConfigurationError(
                    "Error in Rez configuration under plugins.%s: %s"
                    % (attr, str(e)))
        elif attr in data:
            d = data[attr]
        else:
            raise AttributeError("No such configuration setting: 'plugins.%s'"
                                 % attr)
        d_ = convert_dicts(d, RO_AttrDictWrapper)
        self.__dict__[attr] = d_
        return d_

    def to_dict(self):
        # force plugin configs to load
        from rez.plugin_managers import plugin_manager
        for plugin_type in plugin_manager.get_plugin_types():
            _ = getattr(self, plugin_type)

        d = self.__dict__.copy()
        del d["data"]
        d = convert_dicts(d, dict, (dict, AttrDictWrapper))
        return d


def _create_locked_config(overrides=None):
    """Create a locked config.

    The config created by this function only reads settings from the main
    rezconfig file, and from plugin rezconfig files. All other files normally
    used by the main config (~/.rezconfig etc) are ignored, as are environment
    variables overrides.

    Returns:
        `Config` object.
    """
    filepath = os.path.join(module_root_path, "rezconfig")
    return Config([filepath], overrides=overrides, locked=True)


def _swap_config(new_config):
    """Replaces the config singleton with another config.

    Only use this function if you have a very good reason! The unit tests use
    this function to replace the main config with a locked config created via
    `_create_locked_config`, to shield the tests from user settings.

    Returns:
        Previous main `Config` instance.
    """
    global config
    old_config = config
    config = new_config
    return old_config


# singleton
config = Config._get_main_config()
