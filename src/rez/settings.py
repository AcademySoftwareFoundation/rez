"""
API for querying Rez settings. See 'rezconfig' file for more details.
Example:
from rez.settings import settings
print settings.packages_path
"""
from __future__ import with_statement
import os
import os.path
import yaml
import sys
import string
import getpass
from rez.util import which
from rez import module_root_path
from rez.system import system



class PartialFormatter(string.Formatter):
    def get_field(self, key, args, kwargs):
        try:
            return super(PartialFormatter, self).get_field(key, args, kwargs)
        except (KeyError, AttributeError):
            return "{%s}" % key, key


class Settings(object):
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
                                    "Warning: ignoring unknown settings key in %s: '%s'" \
                                    % (filepath, k)
                                del config[k]
                            else:
                                typestr = self.root_config["_type"].get(k)
                                if type(v).__name__ != typestr:
                                    raise KeyError("Invalid key in %s: '%s' should be %s, not %s" \
                                        % (filepath, k, typestr, type(v).__name__))

                        self.config.update(config)

    def _load_variables(self):
        if self.variables is None:
            self.variables = dict(
                platform=system.platform,
                arch=system.arch,
                os=system.os,
                user=getpass.getuser())

    def _expand_variables(self, s):
        self._load_variables()
        f = PartialFormatter()
        return f.format(os.path.expanduser(s), **self.variables)

    def __getattr__(self, attr):
        if attr in self.settings:
            return self.settings[attr]

        self._load_config()
        if attr not in self.config:
            raise AttributeError("No such Rez setting - '%s'" % attr)

        config_value = self.config.get(attr)
        env_var = "REZ_%s" % attr.upper()
        env_value = os.getenv(env_var)

        if env_value is None:
            value = config_value
            if value is None:
                func = "_get_" + attr
                if hasattr(self, func):
                    value = getattr(self, func)()
        elif isinstance(config_value, list):
            sep = self.root_config.get("_sep",{}).get(attr) or os.pathsep
            vals = env_value.strip().strip(sep).split(sep)
            value = [x for x in vals if x]
        elif isinstance(config_value, bool):
            if env_value.lower() in ("1", "true", "yes", "y"):
                value = True
            elif env_value.lower() in ("0", "false", "no", "n"):
                value = False
            else:
                raise ValueError("Expect boolean value: $%s" % env_var)
        else:
            value = env_value

        if isinstance(value, basestring):
            value = self._expand_variables(value)
        elif isinstance(value, list):
            value = [self._expand_variables(x) for x in value]

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
