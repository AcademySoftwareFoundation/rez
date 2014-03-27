"""
Manages loading of all types of Rez plugins.
"""
from yapsy.PluginManager import PluginManager
from rez import module_root_path
from rez.settings import settings
from rez.util import LazySingleton
import logging
import os.path
import os
import sys

if sys.version_info < (2,7):
    from rez.backport.null_handler import NullHandler
else:
    from logging import NullHandler



class RezPluginManager(object):
    def __init__(self, plugin_type_name):
        """ Init a plugin manager.

        Type name must correspond with one of the source directories found under
        the 'plugins' directory. The plugin search path for this type of plugin
        is controlled by the '<typename>_plugin_path' rez setting. For example,
        for plugin_type_name 'foo', the rezconfig entry would be 'foo_plugin_path',
        and the overriding env-var 'REZ_FOO_PLUGIN_PATH'.
        """
        self.type_name = plugin_type_name
        self.pretty_type_name = self.type_name.replace('_',' ')
        self.factories = {}

        yapsy_logger = logging.getLogger("yapsy")
        if not yapsy_logger.handlers:
            h = logging.StreamHandler() if settings.debug_plugins else NullHandler()
            yapsy_logger.addHandler(h)

        plugin_path = os.path.join(module_root_path, "plugins", self.type_name)
        if not os.path.exists(plugin_path):
            raise RuntimeError("Unrecognised plugin type: '%s'" % self.type_name)

        configured_paths = settings.get("%s_plugin_path" % self.type_name)
        plugin_paths = [plugin_path] + configured_paths
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
            self.factories[factory.name()] = factory

    def get_plugins(self):
        """Returns a list of the plugin names available."""
        return self.factories.keys()

    def get_plugin_class(self, plugin):
        """Returns the class registered under the given plugin name."""
        factory = self.factories.get(plugin)
        if factory is None:
            # TODO add a PluginManagerError
            raise RuntimeError("Unrecognised %s plugin: '%s'"
                               % (self.pretty_type_name, plugin))
        return factory.target_type()

    def create_instance(self, plugin, **instance_kwargs):
        """Create and return an instance of the given plugin."""
        cls = self.get_plugin_class(plugin)
        return cls(**instance_kwargs)



class SourceRetrieverPluginManager(RezPluginManager):
    """Source retrievers download data from sources such as archives or repositories.
    """
    def __init__(self):
        super(SourceRetrieverPluginManager,self).__init__("source_retriever")
        self.ext_to_type = []
        self.exts = set()

        for k,v in self.factories.iteritems():
            exts = v.target_type().supported_url_types()
            self.ext_to_type += [(x,k) for x in exts]
            self.exts = self.exts | set(exts)

        # ensures '.tar.gz' is seen before '.gz', for example
        self.ext_to_type = sorted(self.ext_to_type, key=lambda x:-len(x[0]))

    def create_instance(self, url, type=None, cache_path=None, cache_filename=None, \
                        dry_run=False, **retriever_kwargs):
        plugin = type
        if not plugin:
            for ext,plug in self.ext_to_type:
                if url.endswith(ext):
                    plugin = plug
                    break

        if plugin is None:
            raise RuntimeError(("No source retriever is associated with the url: '%s'. " \
                "Supported extensions are: %s") % (url, ', '.join(self.exts)))

        return super(SourceRetrieverPluginManager,self).create_instance(plugin, \
            url=url,
            cache_path=cache_path,
            cache_filename=cache_filename,
            dry_run=dry_run,
            **retriever_kwargs)



class ShellPluginManager(RezPluginManager):
    """Support for different types of target shells, such as bash, tcsh.
    """
    def __init__(self):
        super(ShellPluginManager,self).__init__("shell")

    def create_instance(self, shell=None):
        if not shell:
            from rez.system import system
            shell = system.shell

        return super(ShellPluginManager,self).create_instance(shell)



class ReleaseVCSPluginManager(RezPluginManager):
    """Support for different version control systems when releasing packages.
    """
    def __init__(self):
        super(ReleaseVCSPluginManager,self).__init__("release_vcs")

    def create_instance(self, vcs_name, path):
        return super(ReleaseVCSPluginManager,self).create_instance( \
            vcs_name, path=path)



class ReleaseHookPluginManager(RezPluginManager):
    """Support for different version control systems when releasing packages.
    """
    def __init__(self):
        super(ReleaseHookPluginManager,self).__init__("release_hook")

    def create_instance(self, name, source_path):
        return super(ReleaseHookPluginManager,self).create_instance( \
            name, source_path=source_path)



class BuildSystemPluginManager(RezPluginManager):
    """Support for different build systems when building packages.
    """
    def __init__(self):
        super(BuildSystemPluginManager,self).__init__("build_system")

    def create_instance(self, buildsys_name, working_dir):
        return super(BuildSystemPluginManager,self).create_instance( \
            buildsys_name, working_dir=working_dir)



# singletons
source_retriever_plugin_manager = LazySingleton(SourceRetrieverPluginManager)
shell_plugin_manager            = LazySingleton(ShellPluginManager)
release_vcs_plugin_manager      = LazySingleton(ReleaseVCSPluginManager)
release_hook_plugin_manager     = LazySingleton(ReleaseHookPluginManager)
build_system_plugin_manager     = LazySingleton(BuildSystemPluginManager)
