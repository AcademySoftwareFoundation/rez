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

class RezPluginManager(object):
    type_name = None

    def __init__(self):
        """ Init a plugin manager.

        Type name must correspond with one of the source directories found under
        the 'plugins' directory. The plugin search path for this type of plugin
        is controlled by the '<typename>_plugin_path' rez setting. For example,
        for plugin_type_name 'foo', the rezconfig entry would be 'foo_plugin_path',
        and the overriding env-var 'REZ_FOO_PLUGIN_PATH'.
        """
        if self.type_name is None:
            raise TypeError("Subclasses of RezPluginManager must provide a "
                            "'type_name' attribute")
        self.pretty_type_name = self.type_name.replace('_', ' ')
        self.plugin_classes = {}

        plugin_path = os.path.join(module_root_path, "plugins", self.type_name)
        if not os.path.exists(plugin_path):
            raise RuntimeError("Unrecognised plugin type: '%s'" % self.type_name)

        configured_paths = settings.get("%s_plugin_path" % self.type_name)
        plugin_paths = [plugin_path] + configured_paths
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

    def get_plugins(self):
        """Returns a list of the plugin names available."""
        return self.plugin_classes.keys()

    def get_plugin_class(self, plugin_name):
        """Returns the class registered under the given plugin name."""
        plugin_class = self.plugin_classes.get(plugin_name)
        if plugin_class is None:
            # TODO add a PluginManagerError
            raise RuntimeError("Unrecognised %s plugin: '%s'"
                               % (self.pretty_type_name, plugin_name))
        return plugin_class

    def create_instance(self, plugin, **instance_kwargs):
        """Create and return an instance of the given plugin."""
        return self.get_plugin_class(plugin)(**instance_kwargs)


class SourceRetrieverPluginManager(RezPluginManager):
    """Source retrievers download data from sources such as archives or repositories.
    """
    type_name = "source_retriever"

    def __init__(self):
        super(SourceRetrieverPluginManager, self).__init__()
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

        return super(SourceRetrieverPluginManager, self).create_instance(plugin,
            url=url,
            cache_path=cache_path,
            cache_filename=cache_filename,
            dry_run=dry_run,
            **retriever_kwargs)


class ShellPluginManager(RezPluginManager):
    """Support for different types of target shells, such as bash, tcsh.
    """
    type_name = "shell"


class ReleaseVCSPluginManager(RezPluginManager):
    """Support for different version control systems when releasing packages.
    """
    type_name = "release_vcs"


class ReleaseHookPluginManager(RezPluginManager):
    """Support for different version control systems when releasing packages.
    """
    type_name = "release_hook"


class BuildSystemPluginManager(RezPluginManager):
    """Support for different build systems when building packages.
    """
    type_name = "build_system"


# singletons
source_retriever_plugin_manager = LazySingleton(SourceRetrieverPluginManager)
shell_plugin_manager            = LazySingleton(ShellPluginManager)
release_vcs_plugin_manager      = LazySingleton(ReleaseVCSPluginManager)
release_hook_plugin_manager     = LazySingleton(ReleaseHookPluginManager)
build_system_plugin_manager     = LazySingleton(BuildSystemPluginManager)
