from rez.util import deep_update, propertycache, RO_AttrDictWrapper, \
    convert_dicts, AttrDictWrapper, DataWrapper, ObjectStringFormatter
from rez.exceptions import ConfigurationError
from rez import module_root_path
from rez.system import system
from rez.vendor.schema.schema import Schema, SchemaError, Optional, And, Or
from rez.vendor import yaml
from rez.backport.lru_cache import lru_cache
import os
import os.path
import copy


# -----------------------------------------------------------------------------
# Schema Implementations
# -----------------------------------------------------------------------------

class Setting(object):
    """Setting subclasses implement lazy setting validators.

    Note that lazy setting validation only happens on master configuration
    settings - plugin settings are validated on load only.
    """
    schema = Schema(object)

    def __init__(self, config, key):
        self.config = config
        self.key = key

    @property
    def _env_var_name(self):
        return "REZ_%s" % self.key.upper()

    def _parse_env_var(self, value):
        raise NotImplementedError

    def validate(self, data):
        try:
            data = self._validate(data)
            data = self.schema.validate(data)
        except SchemaError as e:
            raise ConfigurationError("Misconfigured setting '%s': %s"
                                     % (self.key, str(e)))
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


class Str(Setting):
    schema = Schema(basestring)

    def _parse_env_var(self, value):
        return value


class OptionalStr(Setting):
    schema = Or(None, basestring)


class StrList(Setting):
    schema = Schema([basestring])
    sep = ','

    def _parse_env_var(self, value):
        value = value.replace(self.sep, ' ').split()
        return [x for x in value if x]


class PathList(StrList):
    sep = os.pathsep


class Int(Setting):
    schema = Schema(int)

    def _parse_env_var(self, value):
        try:
            return int(value)
        except ValueError:
            raise ConfigurationError("expected %s to be an integer"
                                     % self._env_var_name)


class Bool(Setting):
    schema = Schema(bool)
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
                % (self._env_var_name, ", ".join(words)))


_config_dict = {
    "packages_path":                PathList,
    "plugin_path":                  PathList,
    "bind_module_path":             PathList,
    "implicit_packages":            StrList,
    "parent_variables":             StrList,
    "resetting_variables":          StrList,
    "release_hooks":                StrList,
    "local_packages_path":          Str,
    "release_packages_path":        Str,
    "vcs_tag_name":                 Str,
    "dot_image_format":             Str,
    "prompt":                       Str,
    "build_directory":              Str,
    "tmpdir":                       OptionalStr,
    "default_shell":                OptionalStr,
    "editor":                       OptionalStr,
    "image_viewer":                 OptionalStr,
    "browser":                      OptionalStr,
    "resource_caching_maxsize":     Int,
    "rez_1_compatibility":          Bool,
    "add_bootstrap_path":           Bool,  # TODO deprecate
    "resource_caching":             Bool,
    "resolve_caching":              Bool,
    "all_parent_variables":         Bool,
    "all_resetting_variables":      Bool,
    "warn_shell_startup":           Bool,
    "warn_untimestamped":           Bool,
    "warn_old_commands":            Bool,
    "warn_nonstring_version":       Bool,
    "warn_all":                     Bool,
    "debug_plugins":                Bool,
    "debug_package_release":        Bool,
    "debug_bind_modules":           Bool,
    "debug_resources":              Bool,
    "debug_all":                    Bool,
    "quiet":                        Bool,
    "prefix_prompt":                Bool,

    # preferred namespace to place custom settings
    Optional("custom"):             object,

    # plugin settings are validated lazily
    Optional("plugins"):            dict,

    # TODO remove once all settings are finalised
    Optional(basestring):           object
}


class Expand(object):
    """Schema that applies variable expansion."""
    namespace = dict(system=system)
    formatter = ObjectStringFormatter(AttrDictWrapper(namespace),
                                      expand='unchanged')

    def __init__(self):
        pass

    def validate(self, data):
        def _expand(value):
            if isinstance(value, basestring):
                return self.formatter.format(value)
            elif isinstance(value, list):
                return [_expand(x) for x in value]
            elif isinstance(value, dict):
                return dict((k, _expand(v)) for k, v in value.iteritems())
            else:
                return value
        return _expand(data)


def _to_schema(config_dict, required, allow_custom_keys=True,
               inject_expansion=True):
    """Convert a dict of Schemas into a Schema.

    Args:
        required (bool): Whether to make schema keys optional or required.
        allow_custom_keys (bool): If True, creates a schema that allows
            custom items in dicts.
        inject_expansion (bool): If True, updates schema values by adding
            variable expansion. This is used to update plugins schemas, so
            plugin authors don't have to explicitly support expansion.

    Returns:
        A `Schema` object.
    """
    def _to(value):
        if isinstance(value, dict):
            d = {}
            for k, v in value.iteritems():
                if isinstance(k, basestring):
                    k_ = Schema(k) if required else Optional(k)
                else:
                    k_ = k
                d[k_] = _to(v)
            if allow_custom_keys:
                d[Optional(basestring)] = (Expand()
                                           if inject_expansion else object)
            schema = Schema(d)
        else:
            if type(value) is type and issubclass(value, Setting):
                schema = value.schema
            else:
                schema = value
            if inject_expansion:
                schema = And(schema, Expand())
        return schema

    return _to(config_dict)


config_schema_required = _to_schema(_config_dict, required=True)


# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------

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

    def get(self, key, default=None):
        """Get a config setting."""
        return self.metadata.get(key, default)

    def override(self, key, value):
        """Set a setting to the given value.

        Note that `key` can be in dotted form, eg
        'plugins.release_hook.emailer.sender'.
        """
        keys = key.split('.')
        if len(keys) > 1:
            if keys[0] != "plugins":
                raise AttributeError("no such setting: %r" % key)
            self.plugins.override(keys[1:], value)
        else:
            self.overrides[key] = value
            propertycache.uncache(self, key)

    def warn(self, key):
        """Returns True if the warning setting is enabled."""
        return (not self.quiet and
                (self.warn_all or getattr(self, "warn_%s" % key)))

    def debug(self, key):
        """Returns True if the debug setting is enabled."""
        return (not self.quiet and
                (self.debug_all or getattr(self, "debug_%s" % key)))

    @propertycache
    def plugins(self):
        """Plugin settings are loaded lazily, to avoid loading the plugins
        until necessary."""
        plugin_data = self.metadata.get("plugins", {})
        return _PluginConfigs(plugin_data)

    @property
    def data(self):
        """Returns the entire configuration as a dict.

        Note that this will force all plugins to be loaded.
        """
        d = {}
        for key in self.metadata.iterkeys():
            try:  # TODO remove try-catch once all settings are finalised
                d[key] = getattr(self, key)
            except AttributeError:
                pass
        d["plugins"] = self.plugins.data()
        return d

    @property
    def nonlocal_packages_path(self):
        """Returns package search paths with local path removed."""
        paths = self.packages_path[:]
        if self.local_packages_path in paths:
            paths.remove(self.local_packages_path)
        return paths

    # use as decorator
    def lru_cache(self, key, maxsize_key=None):
        def decorated(f):
            if self.get(key):
                maxsize = self.get(maxsize_key) \
                    if maxsize_key else 100
                return lru_cache(maxsize)(f)
            else:
                return f
        return decorated

    def _swap(self, other):
        """Swap this config with another.

        This is used by the unit tests to swap the config to one that is
        shielded from any user config updates. Do not use this method unless
        you have good reason.
        """
        self.__dict__, other.__dict__ = other.__dict__, self.__dict__

    def _validate_key(self, key, value):
        v = _config_dict.get(key)
        if type(v) is type and issubclass(v, Setting):
            return v(self, key).validate(value)
        return value

    def _load_data(self):
        data = {}
        for filepath in self.filepaths:
            data_ = _load_config_yaml(filepath)
            deep_update(data, data_)

        deep_update(data, self.overrides)
        return data

    @classmethod
    def _create_main_config(cls, overrides=None):
        """See comment block at top of 'rezconfig' describing how the main
        config is assembled."""
        filepaths = []
        filepaths.append(os.path.join(module_root_path, "rezconfig"))
        filepath = os.getenv("REZ_CONFIG_FILE")
        if filepath and os.path.isfile(filepath):
            filepaths.append(filepath)
        filepath = os.path.expanduser("~/.rezconfig")
        if os.path.isfile(filepath):
            filepaths.append(filepath)
        return Config(filepaths, overrides)

    # -- dynamic defaults

    def _get_tmpdir(self):
        from rez.platform_ import platform_
        return platform_.tmpdir

    def _get_image_viewer(self):
        from rez.platform_ import platform_
        return platform_.image_viewer

    def _get_editor(self):
        from rez.platform_ import platform_
        return platform_.editor


class _PluginConfigs(object):
    """Lazy config loading for plugins."""
    def __init__(self, plugin_data):
        self.__dict__['_data'] = plugin_data

    def __setattr__(self, attr, value):
        raise AttributeError("'%s' object attribute '%s' is read-only"
                             % (self.__class__.__name__, attr))

    def __getattr__(self, attr):
        if attr in self.__dict__:
            return self.__dict__[attr]

        data = self.__dict__['_data']
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

    def override(self, key, value):
        def _nosuch():
            raise AttributeError("no such setting: %r" % '.'.join(key))
        if len(key) < 2:
            _nosuch()
        from rez.plugin_managers import plugin_manager
        if key[0] not in plugin_manager.get_plugin_types():
            _nosuch()

        plugin_type = key[0]
        key = key[1:]
        data = {}
        new_overrides = {plugin_type: data}
        while len(key) > 1:
            data_ = {}
            data[key[0]] = data_
            data = data_
            key = key[1:]
        data[key[0]] = value
        deep_update(self.__dict__['_data'], new_overrides)

        if plugin_type in self.__dict__:
            del self.__dict__[plugin_type]  # uncache

    def data(self):
        # force plugin configs to load
        from rez.plugin_managers import plugin_manager
        for plugin_type in plugin_manager.get_plugin_types():
            _ = getattr(self, plugin_type)

        d = self.__dict__.copy()
        del d["_data"]
        d = convert_dicts(d, dict, (dict, AttrDictWrapper))
        return d


def create_config(overrides=None):
    """Create a configuration that reads config files from standard locations.
    """
    if not overrides:
        return config
    else:
        return Config._create_main_config(overrides=overrides)


def _create_locked_config(overrides=None):
    """Create a locked config.

    The config created by this function only reads settings from the main
    rezconfig file, and from plugin rezconfig files. All other files normally
    used by the main config (~/.rezconfig etc) are ignored, as are environment
    variable overrides.

    Returns:
        `Config` object.
    """
    filepath = os.path.join(module_root_path, "rezconfig")
    return Config([filepath], overrides=overrides, locked=True)


@lru_cache()
def _load_config_yaml(filepath):
    with open(filepath) as f:
        content = f.read()
    try:
        return yaml.load(content) or {}
    except Exception as e:
        raise ConfigurationError("Error loading configuration from %s: %s"
                                 % (filepath, str(e)))


# singleton
config = Config._create_main_config()
