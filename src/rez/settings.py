"""
API for querying Rez settings. See 'rezconfig' file for more details.
Example:
from rez.settings import settings
print settings.packages_path
"""
import os
import os.path
import sys
import string
import getpass
from rez.contrib import yaml
from rez.util import which
from rez import module_root_path
from rez.system import system
from rez.exceptions import ConfigurationError
from rez.contrib.schema.schema import Schema, SchemaError, Or



class PartialFormatter(string.Formatter):
    def get_field(self, key, args, kwargs):
        try:
            return super(PartialFormatter, self).get_field(key, args, kwargs)
        except (KeyError, AttributeError):
            return "{%s}" % key, key


class Settings(object):
    bool_schema         = Schema(bool, error="Expected boolean")
    str_schema          = Schema(str, error="Expected string")
    opt_str_schema      = Schema(Or(str,None), error="Expected string or null")
    int_schema          = Schema(int, error="Expected integer")
    str_list_schema     = Schema([str], error="Expected list of strings")
    path_list_schema    = Schema([str], error="Expected list of strings")

    key_schemas = {
        # bools
        "prefix_prompt":                    bool_schema,
        "warn_shell_startup":               bool_schema,
        "warn_untimestamped":               bool_schema,
        "warn_old_commands":                bool_schema,
        "debug_plugins":                    bool_schema,
        "debug_package_release":            bool_schema,
        "all_parent_variables":             bool_schema,
        "all_resetting_variables":          bool_schema,
        # integers
        "release_email_smtp_port":          int_schema,
        # strings
        "local_packages_path":              str_schema,
        "release_packages_path":            str_schema,
        "external_packages_path":           str_schema,
        "package_repository_path":          str_schema,
        "package_repository_cache_path":    str_schema,
        "tmpdir":                           str_schema,
        "version_sep":                      str_schema,
        "prompt":                           str_schema,
        "build_system":                     str_schema,
        "vcs_tag_name":                     str_schema,
        "release_email_smtp_host":          str_schema,
        "release_email_from":               str_schema,
        # optional strings
        "editor":                           opt_str_schema,
        "image_viewer":                     opt_str_schema,
        "browser":                          opt_str_schema,
        # string lists
        "implicit_packages":                str_list_schema,
        "cmake_args":                       str_list_schema,
        "release_hooks":                    str_list_schema,
        "release_email_to":                 str_list_schema,
        "parent_variables":                 str_list_schema,
        "resetting_variables":              str_list_schema,
        # path lists
        "packages_path":                    path_list_schema,
        "package_repository_url_path":      path_list_schema,
        "shell_plugin_path":                path_list_schema,
        "source_retriever_plugin_path":     path_list_schema,
        "release_vcs_plugin_path":          path_list_schema,
        "release_hook_plugin_path":         path_list_schema,
        "build_system_plugin_path":         path_list_schema
    }

    def __init__(self, overrides=None):
        """Create a Settings object.

        Settings are loaded lazily, and follow the rules found at the top of the
        rezconfig file. If 'overrides' is provided, any settings contained in
        this dict override settings from any other source.

        Args:
            overrides: A dict containing settings that override all others.
        """
        self.root_config = None
        self.config = None
        self.variables = None
        self.settings = overrides or {}

    def get(self, key):
        """ Get a setting by name """
        return getattr(self, key)

    def set(self, key, value):
        """ Force a setting to the given value """
        self.settings[key] = value

    def get_all(self):
        """ Get a dict of all settings """
        self._load_config()
        for k in self.config.iterkeys():
            getattr(self, k)
        return self.settings

    def env_var_changed(self, varname):
        """ Uncaches matching setting, if any """
        if varname.startswith('REZ_') and varname.isupper():
            setting = varname.lower()[len('REZ_'):]
            if setting in self.settings:
                del self.settings[setting]

    @property
    def nonlocal_packages_path(self):
        """ Get the package search paths, with local packages path removed """
        paths = self.packages_path[:]
        if self.local_packages_path in paths:
            paths.remove(self.local_packages_path)
        return paths

    def _load_config(self):
        if self.config is None:
            root_config = os.path.join(module_root_path, "rezconfig")
            with open(root_config) as f:
                content = f.read()
                self.root_config = yaml.load(content)
                self.config = dict((k,v) for k,v in self.root_config.iteritems() \
                    if not k.startswith('_'))

            for filepath in ( \
                os.getenv("REZ_SETTINGS_FILE"),
                os.path.expanduser("~/.rezconfig")):
                if filepath and os.path.exists(filepath):
                    with open(filepath) as f:
                        content = f.read()
                        config = yaml.load(content)

                        for k,v in config.items():
                            if k not in self.config:
                                print >> sys.stderr, \
                                    "Warning: ignoring unknown setting in %s: '%s'" \
                                    % (filepath, k)
                                del config[k]

                        self.config.update(config)

        for k,v in self.config.iteritems():
            self._validate(k, v)

    @classmethod
    def _validate(cls, key, value):
        schema = cls.key_schemas.get(key)
        if schema:
            try:
                schema.validate(value)
            except SchemaError as e:
                raise ConfigurationError("%s: %s" % (key, str(e)))

    def _load_variables(self):
        if self.variables is None:
            self.variables = dict(
                platform=system.platform,
                arch=system.arch,
                os=system.os,
                user=getpass.getuser())

    def _expand_variables(self, v):
        if isinstance(v, basestring):
            self._load_variables()
            f = PartialFormatter()
            return f.format(os.path.expanduser(v), **self.variables)
        else:
            return v

    def __getattr__(self, attr):
        if attr in self.settings:
            return self.settings[attr]

        self._load_config()
        if attr not in self.config:
            raise ConfigurationError("No such Rez setting - '%s'" % attr)

        config_value = self.config.get(attr)
        env_var = "REZ_%s" % attr.upper()
        value = os.getenv(env_var)

        if value is None:
            value = config_value
            if value is None:
                func = "_get_" + attr
                if hasattr(self, func):
                    value = getattr(self, func)()
        elif isinstance(config_value, list):
            value = value.strip()
            schema = self.key_schemas.get(attr)
            if schema is self.path_list_schema:
                vals = value.split(os.pathsep)
            else:
                vals = value.replace(',',' ').strip().split()
            value = [x for x in vals if x]
        elif isinstance(config_value, int):
            try:
                value = int(value)
            except ValueError:
                pass
        elif isinstance(config_value, bool):
            if value.lower() in ("1", "true", "yes", "y", "on"):
                value = True
            elif value.lower() in ("0", "false", "no", "n", "off"):
                value = False

        if isinstance(value, basestring):
            value = self._expand_variables(value)
        elif isinstance(value, list):
            value = [self._expand_variables(x) for x in value]

        self._validate(attr, value)
        self.settings[attr] = value
        return value

    def _get_image_viewer(self):
        if system.platform == "linux":
            viewer = which("xdg-open", "eog", "kview")
        elif system.platform == "darwin":
            viewer = "open"
        else:
            # os.system("file.jpg") will open in default viewer on windows
            viewer = ''

        # if None, rez will use webbrowser
        return viewer

    def _get_editor(self):
        if system.platform == "linux":
            ed = os.getenv("EDITOR")
            if ed is None:
                ed = which("xdg-open", "vim", "vi")
        elif system.platform == "darwin":
            ed = "open"
        else:
            # os.system("file.txt") will open in default editor on windows
            ed = ''

        if ed is None:
            raise RuntimeError("Could not detect default text editor - specify one in rezconfig")
        return ed

# singleton
settings = Settings()
