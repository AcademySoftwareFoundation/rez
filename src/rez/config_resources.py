from rez.resources import Required, ArbitraryPath, FileResource, \
    register_resource, load_yaml
from rez.vendor.schema.schema import Schema, Or, And, Use, Optional
from rez.util import AttrDictWrapper, ObjectStringFormatter
from rez.exceptions import ConfigurationError
from rez.system import system


# -----------------------------------------------------------------------------
# Schema Implementations
# -----------------------------------------------------------------------------

class Setting(object):
    schema = Schema(object)


class Str(Setting):
    schema = Schema(basestring)


class OptionalStr(Setting):
    schema = Or(None, basestring)


class StrList(Setting):
    schema = Schema([basestring])


class PathList(StrList):
    pass


class Int(Setting):
    schema = Schema(int)


class Bool(Setting):
    schema = Schema(bool)


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
    "debug_system":                 Bool,
    "debug_package_release":        Bool,
    "debug_bind_modules":           Bool,
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
                    k_ = Required(k) if required else Optional(k)
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


config_schema_optional = _to_schema(_config_dict, False)


# -----------------------------------------------------------------------------
# Config Resources
# -----------------------------------------------------------------------------

class ConfigRoot(ArbitraryPath):
    """Represents a path containing a config file."""
    key = "folder.config_root"

    @classmethod
    def _contents_exception_type(cls):
        return ConfigurationError


class ConfigResource(FileResource):
    """A Rez configuration file resource."""
    key = "config.main"
    parent_resource = ConfigRoot
    schema = config_schema_optional
    path_pattern = "{filename}"
    variable_keys = ["filename"]
    variable_regex = dict(filename=".*")
    loader = 'yaml'


class PluginConfigResource(FileResource):
    """A configuration file resource found in rez plugins."""
    key = "config.plugin"
    parent_resource = ConfigRoot
    schema = None
    path_pattern = "rezconfig"
    loader = 'yaml'


# -----------------------------------------------------------------------------
# Resource Registration
# -----------------------------------------------------------------------------

register_resource(0, ConfigRoot)
register_resource(0, ConfigResource)
register_resource(0, PluginConfigResource)
