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
from rez.util import which
from rez import module_root_path
from rez.system import system



class Settings(object):
    def __init__(self):
        self.config = None
        self.variables = None
        self.settings = {}

    def _load_config(self):
        if self.config is None:
            self.config = {}
            for filepath in ( \
                os.path.join(module_root_path, "rezconfig"),
                os.getenv("REZ_SETTINGS_FILE"),
                os.path.expanduser("~/.rezconfig")):
                if filepath and os.path.exists(filepath):
                    with open(filepath) as f:
                        content = f.read()
                        config = yaml.load(content)
                        self.config.update(config)

    def _load_variables(self):
        if self.variables is None:
            self.variables = dict(
                root_dir=module_root_path,
                platform=system.platform,
                arch=system.arch,
                os=system.os,
                shell=system.shell)

    def _expand_variables(self, s):
        self._load_variables()
        if '{' in s:
            for k,v in self.variables.iteritems():
                s = s.replace("{%s}"%k, v)
        return s

    def __getattr__(self, attr):
        if attr in self.settings:
            return self.settings[attr]

        self._load_config()
        if attr not in self.config:
            raise AttributeError("No such Rez setting - '%s'" % attr)

        value = os.getenv("REZ_%s" % attr.upper())
        if value is None:
            value = self.config.get(attr)
            if value is None:
                func = "_get_" + attr
                if hasattr(self, func):
                    value = getattr(self, func)()

        if isinstance(value, basestring):
            value = self._expand_variables(value)

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
