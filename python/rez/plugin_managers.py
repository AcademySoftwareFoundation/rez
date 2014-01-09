"""
Manages loading of all types of Rez plugins.
"""
from yapsy.PluginManager import PluginManager
from yapsy.IPlugin import IPlugin
from rez import module_root_path
from rez.settings import settings
import logging
import os.path
import os
import sys

if sys.version_info < (2,7):
    from rez.contrib.null_handler import NullHandler
else:
    from logging import NullHandler



class RezPluginFactory(IPlugin):
    """Pure abstract class for creating a plugin type instance.
    """
    #__metaclass__ = abc.ABCMeta

    def target_type(self):
        """ Override this function to return the type this factory creates. """
        raise NotImplementedError

    def name(self):
        """ @returns The name of the plugin type this factory creates. """
        return self.target_type().name()



class RezPluginManager(object):
    def __init__(self, plugin_type_name):
        """ Init a plugin manager. Type name must correspond with one of the source directories
        found under the 'plugins' directory. The plugin search path for this type of plugin is
        controlled by the '<typename>_plugin_path' rez setting. For example, for plugin_type_name
        'foo', the rezconfig entry would be 'foo_plugin_path', and the overriding env-var
        'REZ_FOO_PLUGIN_PATH'.
        """
        self.type_name = plugin_type_name
        self.pretty_type_name = self.type_name.replace('_',' ')
        self.factories = {}

        yapsy_logger = logging.getLogger("yapsy")
        if not yapsy_logger.handlers:
            # TODO improve when we introduce standard logging to Rez
            yapsy_logger.addHandler(NullHandler())
            """
            if self.verbosity:
                h = logging.StreamHandler()
            else:
                h = logging.NullHandler()
            """
            pass

        plugin_path = os.path.join(module_root_path, "plugins", self.type_name)
        if not os.path.exists(plugin_path):
            raise RuntimeError("Unrecognised plugin type: '%s'" % self.type_name)

        configured_paths = settings.get("%s_plugin_path" % self.type_name)
        plugin_paths = [plugin_path] + configured_paths
        mgr = PluginManager()
        mgr.setPluginPlaces(plugin_paths)

        mgr.collectPlugins()
        for plugin in mgr.getAllPlugins():
            factory = plugin.plugin_object
            # TODO only print if logging
            print "Loaded %s plugin: '%s'" % (self.pretty_type_name, factory.name())
            self.factories[factory.name()] = factory

    def get_plugins(self):
        return self.factories.keys()

    def create_instance(self, plugin, **instance_kwargs):
        '''Create and return an instance of the given plugin.
        '''
        factory = self.factories.get(plugin)
        if factory is None:
            raise RuntimeError("Unrecognised %s plugin: '%s'" % (self.pretty_type_name, plugin))

        return factory.target_type()(**instance_kwargs)



class SourceRetrieverPluginManager(RezPluginManager):
    """
    Source retrievers download data from sources such as archives or repositories.
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



# singletons
source_retriever_plugin_manager = SourceRetrieverPluginManager()
