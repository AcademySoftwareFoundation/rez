"""
Manages loading of all types of Rez plugins.
"""
from rez import module_root_path
from rez.settings import settings
from rez.util import LazySingleton
import logging
import os.path
import sys

if sys.version_info < (2, 7):
    from rez.backport.null_handler import NullHandler
else:
    from logging import NullHandler

def get_search_paths(type_name):
    """
    The plugin search path for this type of plugin
    is controlled by the '<typename>_plugin_path' rez setting. For example,
    for plugin_type_name 'foo', the rezconfig entry would be 'foo_plugin_path',
    and the overriding env-var 'REZ_FOO_PLUGIN_PATH'.
    """
    plugin_path = os.path.join(module_root_path, "plugins", type_name)
    if not os.path.exists(plugin_path):
        raise RuntimeError("Unrecognised plugin type: '%s'" % type_name)

    configured_paths = settings.get("%s_plugin_path" % type_name)
    return [plugin_path] + configured_paths

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
        plugin_paths = get_search_paths(self.type_name)
        self.collect_plugins(plugin_paths)

    def collect_plugins(self, plugin_paths):
        from yapsy.PluginManager import PluginManager
        yapsy_logger = logging.getLogger("yapsy")
        if not yapsy_logger.handlers:
            h = logging.StreamHandler() if settings.debug_plugins else NullHandler()
            yapsy_logger.addHandler(h)

        mgr = PluginManager()
        mgr.setPluginPlaces(plugin_paths)
        if settings.debug_plugins:
            print "\nLoading %s plugins from:\n%s" \
                  % (self.pretty_type_name, '\n'.join(plugin_paths))

        mgr.collectPlugins()
        for plugin in mgr.getAllPlugins():
            factory = plugin.plugin_object
            if settings.debug_plugins:
                print "Loaded %s plugin: '%s'" % (self.pretty_type_name, factory.name())
            self.plugin_classes[factory.name()] = factory.target_type()

    def get_plugin_class(self, plugin_name):
        """Returns the class registered under the given plugin name."""
        try:
            return self.plugin_classes[plugin_name]
        except KeyError:
            # TODO add a PluginManagerError
            raise ValueError("Unrecognised %s plugin: '%s'"
                             % (self.pretty_type_name, plugin_name))

    def create_instance(self, plugin, **instance_kwargs):
        """Create and return an instance of the given plugin."""
        return self.get_plugin_class(plugin)(**instance_kwargs)


class RezPluginManager(object):
    """
    Primary interface for working with registered plugins.
    """
    def __init__(self):
        self._plugin_types = {}

    def _get_plugin_type(self, plugin_type):
        try:
            return self._plugin_types[plugin_type]()
        except KeyError:
            # TODO add a PluginManagerError
            raise ValueError("Unrecognised plugin type: '%s'" % (plugin_type))

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

    def get_plugin_class(self, plugin_type, plugin_name):
        """Return the class registered under the given plugin name."""
        try:
            return self._get_plugin_type(plugin_type).get_plugin_class(plugin_name)
        except KeyError:
            # TODO add a PluginManagerError
            raise ValueError("Unrecognised %s plugin: '%s'"
                             % (self.pretty_type_name, plugin_name))

    def get_plugins(self, plugin_type):
        """Return a list of the registered names available for the given plugin type."""
        return self._get_plugin_type(plugin_type).plugin_classes.keys()

    def create_instance(self, plugin_type, plugin_name, **instance_kwargs):
        """Create and return an instance of the given plugin."""
        plugin_type = self._get_plugin_type(plugin_type)
        return plugin_type().create_instance(plugin_name, **instance_kwargs)

#------------------------------------
# Plugin Types
#------------------------------------

class SourceRetrieverPluginType(RezPluginType):
    """Source retrievers download data from sources such as archives or repositories.
    """
    type_name = "source_retriever"

    def __init__(self):
        super(SourceRetrieverPluginType, self).__init__()
        self.ext_to_type = []
        self.extensions = set()

        for plugin_name, plugin_class in self.plugin_classes.iteritems():
            exts = plugin_class.supported_url_types()
            self.ext_to_type += [(x, plugin_name) for x in exts]
            self.extensions = self.extensions | set(exts)

        # ensures '.tar.gz' is seen before '.gz', for example
        self.ext_to_type = sorted(self.ext_to_type, key=lambda x: -len(x[0]))

    def create_instance(self, url, type=None, cache_path=None, cache_filename=None,
                        dry_run=False, **retriever_kwargs):
        plugin = type
        if not plugin:
            for ext, plug in self.ext_to_type:
                if url.endswith(ext):
                    plugin = plug
                    break

        if plugin is None:
            raise RuntimeError(("No source retriever is associated with the url: '%s'. "
                "Supported extensions are: %s") % (url, ', '.join(self.extensions)))

        return super(SourceRetrieverPluginType, self).create_instance(plugin,
            url=url,
            cache_path=cache_path,
            cache_filename=cache_filename,
            dry_run=dry_run,
            **retriever_kwargs)


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


plugin_manager = RezPluginManager()

plugin_manager.register_plugin_type(SourceRetrieverPluginType)
plugin_manager.register_plugin_type(ShellPluginType)
plugin_manager.register_plugin_type(ReleaseVCSPluginType)
plugin_manager.register_plugin_type(ReleaseHookPluginType)
plugin_manager.register_plugin_type(BuildSystemPluginType)
