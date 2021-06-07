"""
Manages loading of all types of Rez plugins.
"""
from rez.config import config, expand_system_vars, _load_config_from_filepaths
from rez.utils.formatting import columnise
from rez.utils.schema import dict_to_schema
from rez.utils.data_utils import LazySingleton, cached_property, deep_update
from rez.utils.logging_ import print_debug, print_warning
from rez.vendor.six import six
from rez.exceptions import RezPluginError
import pkgutil
import os.path
import sys


basestring = six.string_types[0]


# modified from pkgutil standard library:
# this function is called from the __init__.py files of each plugin type inside
# the 'rezplugins' package.
def extend_path(path, name):
    """Extend a package's path.

    Intended use is to place the following code in a package's __init__.py:

        from pkgutil import extend_path
        __path__ = extend_path(__path__, __name__)

    This will add to the package's __path__ all subdirectories of
    directories on 'config.plugin_path' named after the package.  This is
    useful if one wants to distribute different parts of a single logical
    package as multiple directories.

    If the input path is not a list (as is the case for frozen
    packages) it is returned unchanged.  The input path is not
    modified; an extended copy is returned.  Items are only appended
    to the copy at the end.

    It is assumed that 'plugin_path' is a sequence.  Items of 'plugin_path'
    that are not (unicode or 8-bit) strings referring to existing
    directories are ignored.  Unicode items of sys.path that cause
    errors when used as filenames may cause this function to raise an
    exception (in line with os.path.isdir() behavior).
    """
    if not isinstance(path, list):
        # This could happen e.g. when this is called from inside a
        # frozen package.  Return the path unchanged in that case.
        return path

    pname = os.path.join(*name.split('.'))  # Reconstitute as relative path
    # Just in case os.extsep != '.'
    init_py = "__init__" + os.extsep + "py"
    path = path[:]

    def append_if_valid(dir_):
        if os.path.isdir(dir_):
            subdir = os.path.normcase(os.path.join(dir_, pname))
            initfile = os.path.join(subdir, init_py)
            if subdir not in path and os.path.isfile(initfile):
                path.append(subdir)

        elif config.debug("plugins"):
            print_debug("skipped nonexistant rez plugin path: %s" % dir_)

    # Extend old-style plugins
    for dir_ in config.plugin_path:
        append_if_valid(dir_)
    # Extend new-style plugins
    for dir_ in plugin_manager.rezplugins_module_paths:
        append_if_valid(dir_)

    return path


def uncache_rezplugins_module_paths(instance=None):
    instance = instance or plugin_manager
    cached_property.uncache(instance, "rezplugins_module_paths")


class RezPluginType(object):
    """An abstract base class representing a single type of plugin.

    'type_name' must correspond with one of the source directories found under
    the 'plugins' directory.
    """
    type_name = None

    def __init__(self):
        if self.type_name is None:
            raise TypeError("Subclasses of RezPluginType must provide a "
                            "'type_name' attribute")
        self.pretty_type_name = self.type_name.replace('_', ' ')
        self.plugin_classes = {}
        self.failed_plugins = {}
        self.plugin_modules = {}
        self.config_data = {}
        self.load_plugins()

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, self.plugin_classes.keys())

    def register_plugin(self, plugin_name, plugin_class, plugin_module):
        # TODO: check plugin_class to ensure it is a sub-class of expected base-class?
        # TODO: perhaps have a Plugin base class. This introduces multiple
        # inheritance in Shell class though :/
        self.plugin_classes[plugin_name] = plugin_class
        self.plugin_modules[plugin_name] = plugin_module

    def load_plugins(self):
        import pkgutil
        from rez.backport.importlib import import_module
        type_module_name = 'rezplugins.' + self.type_name
        package = import_module(type_module_name)

        # on import, the `__path__` variable of the imported package is extended
        # to include existing directories on the plugin search path (via
        # extend_path, above). this means that `walk_packages` will walk over all
        # modules on the search path at the same level (.e.g in a
        # 'rezplugins/type_name' sub-directory).
        paths = [package.__path__] if isinstance(package.__path__, basestring) \
            else package.__path__

        # reverse plugin path order, so that custom plugins have a chance to
        # be found before the builtin plugins (from /rezplugins).
        paths = reversed(paths)

        for path in paths:
            if config.debug("plugins"):
                print_debug("searching plugin path %s...", path)

            for importer, modname, ispkg in pkgutil.iter_modules(
                    [path], package.__name__ + '.'):

                if importer is None:
                    continue

                plugin_name = modname.split('.')[-1]
                if plugin_name.startswith('_') or plugin_name == 'rezconfig':
                    continue

                if plugin_name in self.plugin_modules:
                    # same named plugins will have identical module name,
                    # which will just reuse previous imported module from
                    # `sys.modules` below. skipping the rest of the process
                    # for good.
                    if config.debug("plugins"):
                        print_warning("skipped same named %s plugin at %s: %s"
                                      % (self.type_name, path, modname))
                    continue

                if config.debug("plugins"):
                    print_debug("loading %s plugin at %s: %s..."
                                % (self.type_name, path, modname))
                try:
                    # nerdvegas/rez#218
                    # load_module will force reload the module if it's
                    # already loaded, so check for that
                    plugin_module = sys.modules.get(modname)
                    if plugin_module is None:
                        loader = importer.find_module(modname)
                        plugin_module = loader.load_module(modname)

                    elif os.path.dirname(plugin_module.__file__) != path:
                        if config.debug("plugins"):
                            # this should not happen but if it does, tell why.
                            print_warning(
                                "plugin module %s is not loaded from current "
                                "load path but reused from previous imported "
                                "path: %s" % (modname, plugin_module.__file__))

                    if (hasattr(plugin_module, "register_plugin")
                            and callable(plugin_module.register_plugin)):

                        plugin_class = plugin_module.register_plugin()
                        if plugin_class is not None:
                            self.register_plugin(plugin_name,
                                                 plugin_class,
                                                 plugin_module)
                        else:
                            if config.debug("plugins"):
                                print_warning(
                                    "'register_plugin' function at %s: %s did "
                                    "not return a class." % (path, modname))
                    else:
                        if config.debug("plugins"):
                            print_warning(
                                "no 'register_plugin' function at %s: %s"
                                % (path, modname))

                        # delete from sys.modules?

                except Exception as e:
                    nameish = modname.split('.')[-1]
                    self.failed_plugins[nameish] = str(e)
                    if config.debug("plugins"):
                        import traceback
                        from rez.vendor.six.six import StringIO
                        out = StringIO()
                        traceback.print_exc(file=out)
                        print_debug(out.getvalue())

            # load config
            data, _ = _load_config_from_filepaths([os.path.join(path, "rezconfig")])
            deep_update(self.config_data, data)

    def get_plugin_class(self, plugin_name):
        """Returns the class registered under the given plugin name."""
        try:
            return self.plugin_classes[plugin_name]
        except KeyError:
            raise RezPluginError("Unrecognised %s plugin: '%s'"
                                 % (self.pretty_type_name, plugin_name))

    def get_plugin_module(self, plugin_name):
        """Returns the module containing the plugin of the given name."""
        try:
            return self.plugin_modules[plugin_name]
        except KeyError:
            raise RezPluginError("Unrecognised %s plugin: '%s'"
                                 % (self.pretty_type_name, plugin_name))

    @cached_property
    def config_schema(self):
        """Returns the merged configuration data schema for this plugin
        type."""
        from rez.config import _plugin_config_dict
        d = _plugin_config_dict.get(self.type_name, {})

        for name, plugin_class in self.plugin_classes.items():
            if hasattr(plugin_class, "schema_dict") \
                    and plugin_class.schema_dict:
                d_ = {name: plugin_class.schema_dict}
                deep_update(d, d_)
        return dict_to_schema(d, required=True, modifier=expand_system_vars)

    def create_instance(self, plugin, **instance_kwargs):
        """Create and return an instance of the given plugin."""
        return self.get_plugin_class(plugin)(**instance_kwargs)


class RezPluginManager(object):
    """Primary interface for working with registered plugins.

    Custom plugins are organized under a python package named 'rezplugins'.
    The direct sub-packages of 'rezplugins' are the plugin types supported by
    rez, and the modules below that are individual custom plugins extending
    that type.

    For example, rez provides plugins of type 'build_system': 'cmake' and 'make'::

        rezplugins/
          __init__.py
          build_system/
            __init__.py
            cmake.py
            make.py
          ...

    Here is an example of how to provide your own plugin.  In the example,
    we'll be adding a plugin for the SCons build system.

    1.  Create the 'rezplugins/build_system' directory structure, add the empty
        '__init__.py' files, and then place your new 'scons.py' plugin module
        into the 'build_system' sub-package::

            rezplugins/
              __init__.py
              build_system/
                __init__.py
                scons.py

    2.  Write your 'scons.py' plugin module, sub-classing your
        `SConsBuildSystem` class from `rez.build_systems.BuildSystem` base
        class.

        At the bottom of the module add a `register_plugin` function that
        returns your plugin class::

            def register_plugin():
                return SConsBuildSystem

    3   Set or append the rez config setting `plugin_path` to point to the
        directory **above** your 'rezplugins' directory.

        All 'rezplugin' packages found on the search path will all be merged
        into a single python package.

        Note:
            Even though 'rezplugins' is a python package, your sparse copy of
            it should  not be on the `PYTHONPATH`, just the `REZ_PLUGIN_PATH`.
            This is important  because it ensures that rez's copy of
            'rezplugins' is always found first.
    """
    def __init__(self):
        self._plugin_types = {}

    @cached_property
    def rezplugins_module_paths(self):
        paths = []
        for importer, name, ispkg in pkgutil.iter_modules():
            if not ispkg:
                continue

            module_path = os.path.join(importer.path, name)
            if os.path.isdir(os.path.join(module_path, "rezplugins")):
                paths.append(module_path)

        return paths

    # -- plugin types

    def _get_plugin_type(self, plugin_type):
        try:
            return self._plugin_types[plugin_type]()
        except KeyError:
            raise RezPluginError("Unrecognised plugin type: '%s'"
                                 % plugin_type)

    def register_plugin_type(self, type_class):
        if not issubclass(type_class, RezPluginType):
            raise TypeError("'type_class' must be a RezPluginType sub class")
        if type_class.type_name is None:
            raise TypeError("Subclasses of RezPluginType must provide a "
                            "'type_name' attribute")
        self._plugin_types[type_class.type_name] = LazySingleton(type_class)

    def get_plugin_types(self):
        """Return a list of the registered plugin types."""
        return self._plugin_types.keys()

    # -- plugins

    def get_plugins(self, plugin_type):
        """Return a list of the registered names available for the given plugin
        type."""
        return self._get_plugin_type(plugin_type).plugin_classes.keys()

    def get_plugin_class(self, plugin_type, plugin_name):
        """Return the class registered under the given plugin name."""
        plugin = self._get_plugin_type(plugin_type)
        return plugin.get_plugin_class(plugin_name)

    def get_plugin_module(self, plugin_type, plugin_name):
        """Return the module defining the class registered under the given
        plugin name."""
        plugin = self._get_plugin_type(plugin_type)
        return plugin.get_plugin_module(plugin_name)

    def get_plugin_config_data(self, plugin_type):
        """Return the merged configuration data for the plugin type."""
        plugin = self._get_plugin_type(plugin_type)
        return plugin.config_data

    def get_plugin_config_schema(self, plugin_type):
        plugin = self._get_plugin_type(plugin_type)
        return plugin.config_schema

    def get_failed_plugins(self, plugin_type):
        """Return a list of plugins for the given type that failed to load.

        Returns:
            List of 2-tuples:
            name (str): Name of the plugin.
            reason (str): Error message.
        """
        return self._get_plugin_type(plugin_type).failed_plugins.items()

    def create_instance(self, plugin_type, plugin_name, **instance_kwargs):
        """Create and return an instance of the given plugin."""
        plugin_type = self._get_plugin_type(plugin_type)
        return plugin_type.create_instance(plugin_name, **instance_kwargs)

    def get_summary_string(self):
        """Get a formatted string summarising the plugins that were loaded."""
        rows = [["PLUGIN TYPE", "NAME", "DESCRIPTION", "STATUS"],
                ["-----------", "----", "-----------", "------"]]
        for plugin_type in sorted(self.get_plugin_types()):
            type_name = plugin_type.replace('_', ' ')
            for name in sorted(self.get_plugins(plugin_type)):
                module = self.get_plugin_module(plugin_type, name)
                desc = (getattr(module, "__doc__", None) or '').strip()
                rows.append((type_name, name, desc, "loaded"))
            for (name, reason) in sorted(self.get_failed_plugins(plugin_type)):
                msg = "FAILED: %s" % reason
                rows.append((type_name, name, '', msg))
        return '\n'.join(columnise(rows))


# ------------------------------------------------------------------------------
# Plugin Types
# ------------------------------------------------------------------------------

class ShellPluginType(RezPluginType):
    """Support for different types of target shells, such as bash, tcsh.
    """
    type_name = "shell"


class ReleaseVCSPluginType(RezPluginType):
    """Support for different version control systems when releasing packages.
    """
    type_name = "release_vcs"


class ReleaseHookPluginType(RezPluginType):
    """Support for different version control systems when releasing packages.
    """
    type_name = "release_hook"


class BuildSystemPluginType(RezPluginType):
    """Support for different build systems when building packages.
    """
    type_name = "build_system"


class PackageRepositoryPluginType(RezPluginType):
    """Support for different package repositories for loading packages.
    """
    type_name = "package_repository"


class BuildProcessPluginType(RezPluginType):
    """Support for different build and release processes.
    """
    type_name = "build_process"


class CommandPluginType(RezPluginType):
    """Support for different custom Rez applications/subcommands.
    """
    type_name = "command"


plugin_manager = RezPluginManager()


plugin_manager.register_plugin_type(ShellPluginType)
plugin_manager.register_plugin_type(ReleaseVCSPluginType)
plugin_manager.register_plugin_type(ReleaseHookPluginType)
plugin_manager.register_plugin_type(BuildSystemPluginType)
plugin_manager.register_plugin_type(PackageRepositoryPluginType)
plugin_manager.register_plugin_type(BuildProcessPluginType)
plugin_manager.register_plugin_type(CommandPluginType)


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
