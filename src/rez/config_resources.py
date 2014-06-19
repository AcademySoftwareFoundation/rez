from rez.resources import Required, ArbitraryPath, FileResource, \
    register_resource, load_yaml
from rez.vendor.schema.schema import Schema, Or, Optional


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


_config_schema = {
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

    # plugin settings are validated lazily - they cannot be validated until
    # the plugins are loaded, which also happens lazily
    # "plugins":                      Or(None, dict)

    # TODO remove once all settings are finalised
    Optional(basestring): Setting
}


def _xkey(k, cls):
    return cls(k) if isinstance(k, basestring) else k

config_schema_required = Schema(dict((_xkey(k, Required), v.schema)
                                for k, v in _config_schema.iteritems()))

config_schema_optional = Schema(dict((_xkey(k, Optional), v.schema)
                                for k, v in _config_schema.iteritems()))


# -----------------------------------------------------------------------------
# Config Resources
# -----------------------------------------------------------------------------

class ConfigRoot(ArbitraryPath):
    """Represents a path containing a config file."""
    key = "folder.config_root"


class ConfigResource(FileResource):
    """A Rez configuration file.

    Config files are merged with other config files to create a `Config`
    instance. The 'rezconfig' file in rez acts as the master - other config
    files update the master configuration to create the final config. See the
    comments at the top of 'rezconfig' for more details.
    """
    key = "config.file"
    parent_resource = ConfigRoot
    schema = config_schema_optional
    path_pattern = "{filename}"
    variable_keys = ["filename"]
    variable_regex = dict(filename=".*")
    loader = 'yaml'


# -----------------------------------------------------------------------------
# Resource Registration
# -----------------------------------------------------------------------------

register_resource(0, ConfigRoot)

register_resource(0, ConfigResource)
