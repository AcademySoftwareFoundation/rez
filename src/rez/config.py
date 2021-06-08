from __future__ import absolute_import
from rez import __version__
from rez.utils.data_utils import AttrDictWrapper, RO_AttrDictWrapper, \
    convert_dicts, cached_property, cached_class_property, LazyAttributeMeta, \
    deep_update, ModifyList, DelayLoad
from rez.utils.formatting import expandvars, expanduser
from rez.utils.logging_ import get_debug_printer
from rez.utils.scope import scoped_format
from rez.exceptions import ConfigurationError
from rez import module_root_path
from rez.system import system
from rez.vendor.schema.schema import Schema, SchemaError, And, Or, Use
from rez.vendor import yaml
from rez.vendor.six import six
from rez.vendor.yaml.error import YAMLError
from rez.backport.lru_cache import lru_cache
from contextlib import contextmanager
from inspect import ismodule
import os
import re
import copy


basestring = six.string_types[0]


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
            data = expand_system_vars(data)
        except SchemaError as e:
            raise ConfigurationError("Misconfigured setting '%s': %s"
                                     % (self.key, str(e)))
        return data

    def _validate(self, data):
        # overridden settings take precedence. Note that `data` has already
        # taken override into account at this point
        if self.key in self.config.overrides:
            return data

        if not self.config.locked:

            # next, env-var
            value = os.getenv(self._env_var_name)
            if value is not None:
                return self._parse_env_var(value)

            # next, JSON-encoded env-var
            varname = self._env_var_name + "_JSON"
            value = os.getenv(varname)
            if value is not None:
                from rez.utils import json

                try:
                    return json.loads(value)
                except ValueError:
                    raise ConfigurationError(
                        "Expected $%s to be JSON-encoded string." % varname
                    )

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


class Char(Setting):
    schema = Schema(basestring, lambda x: len(x) == 1)

    def _parse_env_var(self, value):
        return value


class OptionalStr(Str):
    schema = Or(None, basestring)


class StrList(Setting):
    schema = Schema([basestring])
    sep = ','

    def _parse_env_var(self, value):
        value = value.replace(self.sep, ' ').split()
        return [x for x in value if x]


class PipInstallRemaps(Setting):
    """Ordered, pip install remappings."""
    PARDIR, SEP = map(re.escape, (os.pardir, os.sep))
    RE_TOKENS = {'sep': SEP, 's': SEP, 'pardir': PARDIR, 'p': PARDIR}
    TOKENS = {'sep': os.sep, 's': os.sep, 'pardir': os.pardir, 'p': os.pardir}
    KEYS = ["record_path", "pip_install", "rez_install"]

    schema = Schema([{key: And(str, len) for key in KEYS}])

    def validate(self, data):
        """Extended to substitute regex-escaped path tokens."""
        return [
            {
                key: expression.format(
                    **(self.RE_TOKENS if key == "record_path" else self.TOKENS)
                )
                for key, expression in remap.items()
            }
            for remap in super(PipInstallRemaps, self).validate(data)
        ]


class OptionalStrList(StrList):
    schema = Or(And(None, Use(lambda x: [])),
                [basestring])


class PathList(StrList):
    sep = os.pathsep

    def _parse_env_var(self, value):
        value = value.split(self.sep)
        return [x for x in value if x]


class Int(Setting):
    schema = Schema(int)

    def _parse_env_var(self, value):
        try:
            return int(value)
        except ValueError:
            raise ConfigurationError("Expected %s to be an integer"
                                     % self._env_var_name)


class Float(Setting):
    schema = Schema(float)

    def _parse_env_var(self, value):
        try:
            return float(value)
        except ValueError:
            raise ConfigurationError("Expected %s to be a float"
                                     % self._env_var_name)


class Bool(Setting):
    schema = Schema(bool)
    true_words = frozenset(["1", "true", "t", "yes", "y", "on"])
    false_words = frozenset(["0", "false", "f", "no", "n", "off"])
    all_words = true_words | false_words

    def _parse_env_var(self, value):
        value = value.lower()
        if value in self.true_words:
            return True
        elif value in self.false_words:
            return False
        else:
            raise ConfigurationError(
                "Expected $%s to be one of: %s"
                % (self._env_var_name, ", ".join(self.all_words)))


class OptionalBool(Bool):
    # need None first, or Bool.schema will coerce None to False
    schema = Or(None, Bool.schema)


class ForceOrBool(Bool):
    FORCE_STR = "force"

    # need force first, or Bool.schema will coerce "force" to True
    schema = Or(FORCE_STR, Bool.schema)
    all_words = Bool.all_words | frozenset([FORCE_STR])

    def _parse_env_var(self, value):
        if value == self.FORCE_STR:
            return value
        return super(ForceOrBool, self)._parse_env_var(value)


class Dict(Setting):
    schema = Schema(dict)

    def _parse_env_var(self, value):
        items = value.split(",")
        result = {}

        for item in items:
            if ':' not in item:
                raise ConfigurationError(
                    "Expected dict string in form 'k1:v1,k2:v2,...kN:vN': %s"
                    % value
                )

            k, v = item.split(':', 1)

            try:
                v = int(v)
            except ValueError:
                try:
                    v = float(v)
                except ValueError:
                    pass

            result[k] = v

        return result


class OptionalDict(Dict):
    schema = Or(And(None, Use(lambda x: {})),
                dict)


class OptionalDictOrDictList(Setting):
    schema = Or(And(None, Use(lambda x: [])),
                And(dict, Use(lambda x: [x])),
                [dict])


class SuiteVisibility_(Str):
    @cached_class_property
    def schema(cls):
        from rez.resolved_context import SuiteVisibility
        return Or(*(x.name for x in SuiteVisibility))


class VariantSelectMode_(Str):
    @cached_class_property
    def schema(cls):
        from rez.solver import VariantSelectMode
        return Or(*(x.name for x in VariantSelectMode))


class RezToolsVisibility_(Str):
    @cached_class_property
    def schema(cls):
        from rez.resolved_context import RezToolsVisibility
        return Or(*(x.name for x in RezToolsVisibility))


class ExecutableScriptMode_(Str):
    @cached_class_property
    def schema(cls):
        from rez.utils.execution import ExecutableScriptMode
        return Or(*(x.name for x in ExecutableScriptMode))


class OptionalStrOrFunction(Setting):
    schema = Or(None, basestring, callable)

    def _parse_env_var(self, value):
        # note: env-var override only supports string, eg 'mymodule.preprocess_func'
        return value


class PreprocessMode_(Str):
    @cached_class_property
    def schema(cls):
        from rez.developer_package import PreprocessMode
        return Or(*(x.name for x in PreprocessMode))


class BuildThreadCount_(Setting):
    # may be a positive int, or the values "physical" or "logical"

    @cached_class_property
    def schema(cls):
        from rez.utils.platform_ import platform_

        # Note that this bakes the physical / logical cores at the time the
        # config is read... which should be fine
        return Or(
            And(int, lambda x: x > 0),
            And("physical_cores", Use(lambda x: platform_.physical_cores)),
            And("logical_cores", Use(lambda x: platform_.logical_cores)),
        )

    def _parse_env_var(self, value):
        try:
            return int(value)
        except ValueError:
            # wasn't a string - hopefully it's "physical" or "logical"...
            # ...but this will be validated by the schema...
            return value


config_schema = Schema({
    "packages_path":                                PathList,
    "plugin_path":                                  PathList,
    "bind_module_path":                             PathList,
    "standard_system_paths":                        PathList,
    "package_definition_build_python_paths":        PathList,
    "platform_map":                                 OptionalDict,
    "default_relocatable_per_package":              OptionalDict,
    "default_relocatable_per_repository":           OptionalDict,
    "default_cachable_per_package":                 OptionalDict,
    "default_cachable_per_repository":              OptionalDict,
    "default_cachable":                             OptionalBool,
    "implicit_packages":                            StrList,
    "parent_variables":                             StrList,
    "resetting_variables":                          StrList,
    "release_hooks":                                StrList,
    "context_tracking_context_fields":              StrList,
    "prompt_release_message":                       Bool,
    "critical_styles":                              OptionalStrList,
    "error_styles":                                 OptionalStrList,
    "warning_styles":                               OptionalStrList,
    "info_styles":                                  OptionalStrList,
    "debug_styles":                                 OptionalStrList,
    "heading_styles":                               OptionalStrList,
    "local_styles":                                 OptionalStrList,
    "implicit_styles":                              OptionalStrList,
    "ephemeral_styles":                             OptionalStrList,
    "alias_styles":                                 OptionalStrList,
    "memcached_uri":                                OptionalStrList,
    "pip_extra_args":                               OptionalStrList,
    "pip_install_remaps":                           PipInstallRemaps,
    "local_packages_path":                          Str,
    "release_packages_path":                        Str,
    "dot_image_format":                             Str,
    "build_directory":                              Str,
    "documentation_url":                            Str,
    "suite_visibility":                             SuiteVisibility_,
    "rez_tools_visibility":                         RezToolsVisibility_,
    "create_executable_script_mode":                ExecutableScriptMode_,
    "suite_alias_prefix_char":                      Char,
    "cache_packages_path":                          OptionalStr,
    "package_definition_python_path":               OptionalStr,
    "tmpdir":                                       OptionalStr,
    "context_tmpdir":                               OptionalStr,
    "default_shell":                                OptionalStr,
    "terminal_emulator_command":                    OptionalStr,
    "editor":                                       OptionalStr,
    "image_viewer":                                 OptionalStr,
    "difftool":                                     OptionalStr,
    "browser":                                      OptionalStr,
    "critical_fore":                                OptionalStr,
    "critical_back":                                OptionalStr,
    "error_fore":                                   OptionalStr,
    "error_back":                                   OptionalStr,
    "warning_fore":                                 OptionalStr,
    "warning_back":                                 OptionalStr,
    "info_fore":                                    OptionalStr,
    "info_back":                                    OptionalStr,
    "debug_fore":                                   OptionalStr,
    "debug_back":                                   OptionalStr,
    "heading_fore":                                 OptionalStr,
    "heading_back":                                 OptionalStr,
    "local_fore":                                   OptionalStr,
    "local_back":                                   OptionalStr,
    "implicit_fore":                                OptionalStr,
    "implicit_back":                                OptionalStr,
    "ephemeral_fore":                               OptionalStr,
    "ephemeral_back":                               OptionalStr,
    "alias_fore":                                   OptionalStr,
    "alias_back":                                   OptionalStr,
    "package_preprocess_function":                  OptionalStrOrFunction,
    "package_preprocess_mode":                      PreprocessMode_,
    "context_tracking_host":                        OptionalStr,
    "variant_shortlinks_dirname":                   OptionalStr,
    "build_thread_count":                           BuildThreadCount_,
    "resource_caching_maxsize":                     Int,
    "max_package_changelog_chars":                  Int,
    "max_package_changelog_revisions":              Int,
    "memcached_package_file_min_compress_len":      Int,
    "memcached_context_file_min_compress_len":      Int,
    "memcached_listdir_min_compress_len":           Int,
    "memcached_resolve_min_compress_len":           Int,
    "shell_error_truncate_cap":                     Int,
    "package_cache_log_days":                       Int,
    "package_cache_max_variant_days":               Int,
    "package_cache_clean_limit":                    Float,
    "allow_unversioned_packages":                   Bool,
    "rxt_as_yaml":                                  Bool,
    "package_cache_during_build":                   Bool,
    "package_cache_local":                          Bool,
    "package_cache_same_device":                    Bool,
    "color_enabled":                                ForceOrBool,
    "resolve_caching":                              Bool,
    "cache_package_files":                          Bool,
    "cache_listdir":                                Bool,
    "prune_failed_graph":                           Bool,
    "all_parent_variables":                         Bool,
    "all_resetting_variables":                      Bool,
    "package_commands_sourced_first":               Bool,
    "use_variant_shortlinks":                       Bool,
    "warn_shell_startup":                           Bool,
    "warn_untimestamped":                           Bool,
    "warn_all":                                     Bool,
    "warn_none":                                    Bool,
    "debug_file_loads":                             Bool,
    "debug_plugins":                                Bool,
    "debug_package_release":                        Bool,
    "debug_bind_modules":                           Bool,
    "debug_resources":                              Bool,
    "debug_package_exclusions":                     Bool,
    "debug_memcache":                               Bool,
    "debug_resolve_memcache":                       Bool,
    "debug_all":                                    Bool,
    "debug_none":                                   Bool,
    "quiet":                                        Bool,
    "show_progress":                                Bool,
    "catch_rex_errors":                             Bool,
    "default_relocatable":                          Bool,
    "set_prompt":                                   Bool,
    "prefix_prompt":                                Bool,
    "warn_old_commands":                            Bool,
    "error_old_commands":                           Bool,
    "debug_old_commands":                           Bool,
    "warn_commands2":                               Bool,
    "error_commands2":                              Bool,
    "rez_1_environment_variables":                  Bool,
    "rez_1_cmake_variables":                        Bool,
    "disable_rez_1_compatibility":                  Bool,
    "make_package_temporarily_writable":            Bool,
    "read_package_cache":                           Bool,
    "write_package_cache":                          Bool,
    "env_var_separators":                           Dict,
    "variant_select_mode":                          VariantSelectMode_,
    "package_filter":                               OptionalDictOrDictList,
    "package_orderers":                             OptionalDictOrDictList,
    "new_session_popen_args":                       OptionalDict,
    "context_tracking_amqp":                        OptionalDict,
    "context_tracking_extra_fields":                OptionalDict,
    "optionvars":                                   OptionalDict,

    # GUI settings
    "use_pyside":                                   Bool,
    "use_pyqt":                                     Bool,
    "gui_threads":                                  Bool
})


# settings common to each plugin type
_plugin_config_dict = {
    "release_vcs": {
        "tag_name":                     basestring,
        "releasable_branches":          Or(None, [basestring]),
        "check_tag":                    bool
    }
}


# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------

class Config(six.with_metaclass(LazyAttributeMeta, object)):
    """Rez configuration settings.

    You should call the `create_config` function, rather than constructing a
    `Config` object directly.

    Config files are merged with other config files to create a `Config`
    instance. The 'rezconfig' file in rez acts as the master - other config
    files update the master configuration to create the final config. See the
    comments at the top of 'rezconfig' for more details.
    """
    schema = config_schema
    schema_error = ConfigurationError

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
        self._sourced_filepaths = None
        self.overrides = overrides or {}
        self.locked = locked

    def get(self, key, default=None):
        """Get the value of a setting."""
        return getattr(self, key, default)

    def copy(self, overrides=None, locked=False):
        """Create a separate copy of this config."""
        other = copy.copy(self)

        if overrides is not None:
            other.overrides = overrides

        other.locked = locked

        other._uncache()
        return other

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
            self._uncache(key)

    def is_overridden(self, key):
        return (key in self.overrides)

    def remove_override(self, key):
        """Remove a setting override, if one exists."""
        keys = key.split('.')
        if len(keys) > 1:
            raise NotImplementedError
        elif key in self.overrides:
            del self.overrides[key]
            self._uncache(key)

    def warn(self, key):
        """Returns True if the warning setting is enabled."""
        return (
            not self.quiet and not self.warn_none
            and (self.warn_all or getattr(self, "warn_%s" % key))
        )

    def debug(self, key):
        """Returns True if the debug setting is enabled."""
        return (
            not self.quiet and not self.debug_none
            and (self.debug_all or getattr(self, "debug_%s" % key))
        )

    def debug_printer(self, key):
        """Returns a printer object suitably enabled based on the given key."""
        enabled = self.debug(key)
        return get_debug_printer(enabled)

    @cached_property
    def sourced_filepaths(self):
        """Get the list of files actually sourced to create the config.

        Note:
            `self.filepaths` refers to the filepaths used to search for the
            configs, which does dot necessarily match the files used. For example,
            some files may not exist, while others are chosen as rezconfig.py in
            preference to rezconfig, rezconfig.yaml.

        Returns:
            List of str: The sourced files.
        """
        _ = self._data  # noqa; force a config load
        return self._sourced_filepaths

    @cached_property
    def plugins(self):
        """Plugin settings are loaded lazily, to avoid loading the plugins
        until necessary."""
        plugin_data = self._data.get("plugins", {})
        return _PluginConfigs(plugin_data)

    @property
    def data(self):
        """Returns the entire configuration as a dict.

        Note that this will force all plugins to be loaded.
        """
        d = {}
        for key in self._data:
            if key == "plugins":
                d[key] = self.plugins.data()
            else:
                try:
                    d[key] = getattr(self, key)
                except AttributeError:
                    pass  # unknown key, just leave it unchanged
        return d

    @property
    def nonlocal_packages_path(self):
        """Returns package search paths with local path removed."""
        paths = self.packages_path[:]
        if self.local_packages_path in paths:
            paths.remove(self.local_packages_path)
        return paths

    def get_completions(self, prefix):
        def _get_plugin_completions(prefix_):
            from rez.utils.data_utils import get_object_completions
            words = get_object_completions(
                instance=self.plugins,
                prefix=prefix_,
                instance_types=(dict, AttrDictWrapper))
            return ["plugins." + x for x in words]

        toks = prefix.split('.')
        if len(toks) > 1:
            if toks[0] == "plugins":
                prefix_ = '.'.join(toks[1:])
                return _get_plugin_completions(prefix_)
            return []
        else:
            keys = (
                [x for x in self._schema_keys if isinstance(x, basestring)]
                + ["plugins"]
            )
            keys = [x for x in keys if x.startswith(prefix)]
            if keys == ["plugins"]:
                keys += _get_plugin_completions('')
            return keys

    def _uncache(self, key=None):
        # deleting the attribute falls up back to the class attribute, which is
        # the cached_property descriptor
        if key and hasattr(self, key):
            delattr(self, key)

        # have to uncache entire data/plugins dict also, since overrides may
        # have been changed
        if hasattr(self, "_data"):
            delattr(self, "_data")

        if hasattr(self, "plugins"):
            delattr(self, "plugins")

    def _swap(self, other):
        """Swap this config with another.

        This is used by the unit tests to swap the config to one that is
        shielded from any user config updates. Do not use this method unless
        you have good reason.
        """
        self.__dict__, other.__dict__ = other.__dict__, self.__dict__

    def _validate_key(self, key, value, key_schema):
        if isinstance(value, DelayLoad):
            value = value.get_value()

        if type(key_schema) is type and issubclass(key_schema, Setting):
            key_schema = key_schema(self, key)
        elif not isinstance(key_schema, Schema):
            key_schema = Schema(key_schema)

        return key_schema.validate(value)

    @cached_property
    def _data_without_overrides(self):
        data, self._sourced_filepaths = _load_config_from_filepaths(self.filepaths)
        return data

    @cached_property
    def _data(self):
        data = copy.deepcopy(self._data_without_overrides)

        # need to do this regardless of overrides, in order to flatten
        # ModifyList instances
        deep_update(data, self.overrides)

        return data

    @classmethod
    def _create_main_config(cls, overrides=None):
        """See comment block at top of 'rezconfig' describing how the main
        config is assembled."""
        filepaths = []
        filepaths.append(get_module_root_config())
        filepath = os.getenv("REZ_CONFIG_FILE")
        if filepath:
            filepaths.extend(filepath.split(os.pathsep))

        if os.getenv("REZ_DISABLE_HOME_CONFIG", "").lower() not in ("1", "t", "true"):
            filepath = os.path.expanduser("~/.rezconfig")
            filepaths.append(filepath)

        return Config(filepaths, overrides)

    def __str__(self):
        keys = (x for x in self.schema._schema if isinstance(x, basestring))
        return "%r" % sorted(list(keys) + ["plugins"])

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, str(self))

    # -- dynamic defaults

    def _get_tmpdir(self):
        from rez.utils.platform_ import platform_
        return platform_.tmpdir

    def _get_context_tmpdir(self):
        from rez.utils.platform_ import platform_
        return platform_.tmpdir

    def _get_image_viewer(self):
        from rez.utils.platform_ import platform_
        return platform_.image_viewer

    def _get_editor(self):
        from rez.utils.platform_ import platform_
        return platform_.editor

    def _get_difftool(self):
        from rez.utils.platform_ import platform_
        return platform_.difftool

    def _get_terminal_emulator_command(self):
        from rez.utils.platform_ import platform_
        return platform_.terminal_emulator_command

    def _get_new_session_popen_args(self):
        from rez.utils.platform_ import platform_
        return platform_.new_session_popen_args


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
            # get plugin config data, and apply overrides
            plugin_type = attr
            config_data = plugin_manager.get_plugin_config_data(plugin_type)
            d = copy.deepcopy(config_data)
            deep_update(d, data.get(plugin_type, {}))

            # validate
            schema = plugin_manager.get_plugin_config_schema(plugin_type)
            try:
                d = schema.validate(d)
            except SchemaError as e:
                raise ConfigurationError(
                    "Error in Rez configuration under plugins.%s: %s"
                    % (plugin_type, str(e)))
        elif attr in data:
            d = data[attr]
        else:
            raise AttributeError("No such configuration setting: 'plugins.%s'"
                                 % attr)
        d_ = convert_dicts(d, RO_AttrDictWrapper)
        self.__dict__[attr] = d_
        return d_

    def __iter__(self):
        from rez.plugin_managers import plugin_manager
        return iter(plugin_manager.get_plugin_types())

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
            getattr(self, plugin_type)

        d = self.__dict__.copy()
        del d["_data"]
        d = convert_dicts(d, dict, (dict, AttrDictWrapper))
        return d

    def __str__(self):
        from rez.plugin_managers import plugin_manager
        return "%r" % sorted(plugin_manager.get_plugin_types())

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, str(self))


def expand_system_vars(data):
    """Expands any strings within `data` such as '{system.user}'."""
    def _expanded(value):
        if isinstance(value, basestring):
            value = expandvars(value)
            value = expanduser(value)
            return scoped_format(value, system=system)
        elif isinstance(value, (list, tuple, set)):
            return [_expanded(x) for x in value]
        elif isinstance(value, dict):
            return dict((k, _expanded(v)) for k, v in value.items())
        else:
            return value
    return _expanded(data)


def create_config(overrides=None):
    """Create a configuration based on the global config.
    """
    if not overrides:
        return config
    else:
        return config.copy(overrides=overrides)


def _create_locked_config(overrides=None):
    """Create a locked config.

    The config created by this function only reads settings from the main
    rezconfig file, and from plugin rezconfig files. All other files normally
    used by the main config (~/.rezconfig etc) are ignored, as are environment
    variable overrides.

    Returns:
        `Config` object.
    """
    return Config([get_module_root_config()], overrides=overrides, locked=True)


@contextmanager
def _replace_config(other):
    """Temporarily replace the global config.
    """
    config._swap(other)

    try:
        yield
    finally:
        config._swap(other)  # revert config


@lru_cache()
def _load_config_py(filepath):
    reserved = dict(
        # Standard Python module variables
        # Made available from within the module,
        # and later excluded from the `Config` class
        __name__=os.path.splitext(os.path.basename(filepath))[0],
        __file__=filepath,

        rez_version=__version__,
        ModifyList=ModifyList,
        DelayLoad=DelayLoad
    )

    g = reserved.copy()
    result = {}

    with open(filepath) as f:
        try:
            code = compile(f.read(), filepath, 'exec')
            exec(code, g)
        except Exception as e:
            raise ConfigurationError("Error loading configuration from %s: %s"
                                     % (filepath, str(e)))

    for k, v in g.items():
        if k != '__builtins__' \
                and not ismodule(v) \
                and k not in reserved:
            result[k] = v

    return result


@lru_cache()
def _load_config_yaml(filepath):
    with open(filepath) as f:
        content = f.read()
    try:
        doc = yaml.load(content, Loader=yaml.FullLoader) or {}
    except YAMLError as e:
        raise ConfigurationError("Error loading configuration from %s: %s"
                                 % (filepath, str(e)))

    if not isinstance(doc, dict):
        raise ConfigurationError("Error loading configuration from %s: Expected "
                                 "dict, got %s" % (filepath, type(doc).__name__))
    return doc


def _load_config_from_filepaths(filepaths):
    data = {}
    sourced_filepaths = []
    loaders = ((".py", _load_config_py),
               ("", _load_config_yaml))

    for filepath in filepaths:
        for extension, loader in loaders:
            if extension:
                no_ext = os.path.splitext(filepath)[0]
                filepath_with_ext = no_ext + extension
            else:
                filepath_with_ext = filepath

            if not os.path.isfile(filepath_with_ext):
                continue

            data_ = loader(filepath_with_ext)
            deep_update(data, data_)
            sourced_filepaths.append(filepath_with_ext)
            break

    return data, sourced_filepaths


def get_module_root_config():
    return os.path.join(module_root_path, "rezconfig.py")


# singleton
config = Config._create_main_config()


# Copyright 2013-2016 Allan Johns.
#
# This library is free software: you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.
