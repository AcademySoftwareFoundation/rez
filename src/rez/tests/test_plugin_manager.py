"""
test rezplugins manager behaviors
"""
from rez.tests.util import TestBase, TempdirMixin, restore_sys_path
from rez.plugin_managers import (
    uncache_sys_module_paths,
    RezPluginManager,
    ShellPluginType,
    ReleaseVCSPluginType,
    ReleaseHookPluginType,
    BuildSystemPluginType,
    PackageRepositoryPluginType,
    BuildProcessPluginType,
    CommandPluginType
)
import os
import sys
import unittest


class TestPluginManagers(TestBase, TempdirMixin):
    def __init__(self, *nargs, **kwargs):
        TestBase.__init__(self, *nargs, **kwargs)
        self._original_modules = set()
        self.plugin_manager = None

    def setUp(self):
        TestBase.setUp(self)
        uncache_sys_module_paths()

        plugin_manager = RezPluginManager()
        plugin_manager.register_plugin_type(ShellPluginType)
        plugin_manager.register_plugin_type(ReleaseVCSPluginType)
        plugin_manager.register_plugin_type(ReleaseHookPluginType)
        plugin_manager.register_plugin_type(BuildSystemPluginType)
        plugin_manager.register_plugin_type(PackageRepositoryPluginType)
        plugin_manager.register_plugin_type(BuildProcessPluginType)
        plugin_manager.register_plugin_type(CommandPluginType)

        self._original_modules.update(sys.modules.keys())
        self.plugin_manager = plugin_manager

    def tearDown(self):
        TestBase.tearDown(self)
        self.plugin_manager = None

        for key in set(sys.modules.keys()):
            if key not in self._original_modules:
                del sys.modules[key]
        self._original_modules.clear()

    def test_old_loading_style(self):
        """Test loading rez plugin from plugin_path"""
        path = os.path.realpath(os.path.dirname(__file__))
        self.update_settings(dict(
            plugin_path=[os.path.join(path, "data", "extensions", "foo")]
        ))

        cloud_cls = self.plugin_manager.get_plugin_class(
            "package_repository", "cloud")
        self.assertEqual(cloud_cls.name(), "cloud")

    def test_new_loading_style(self):
        """Test loading rez plugin from python modules"""
        path = os.path.realpath(os.path.dirname(__file__))
        with restore_sys_path():
            sys.path.append(os.path.join(path, "data", "extensions"))

            cloud_cls = self.plugin_manager.get_plugin_class(
                "package_repository", "cloud")
            self.assertEqual(cloud_cls.name(), "cloud")

    def test_plugin_override_1(self):
        """Test plugin from plugin_path can override the default"""
        path = os.path.realpath(os.path.dirname(__file__))
        self.update_settings(dict(
            plugin_path=[os.path.join(path, "data", "extensions", "non-mod")]
        ))

        mem_cls = self.plugin_manager.get_plugin_class(
            "package_repository", "memory")
        self.assertEqual("non-mod", mem_cls.on_test)

    def test_plugin_override_2(self):
        """Test plugin from python modules can override the default"""
        path = os.path.realpath(os.path.dirname(__file__))
        with restore_sys_path():
            sys.path.append(os.path.join(path, "data", "extensions"))

            mem_cls = self.plugin_manager.get_plugin_class(
                "package_repository", "memory")
            self.assertEqual("bar", mem_cls.on_test)

    def test_plugin_override_3(self):
        """Test plugin from python modules can override plugin_path"""
        path = os.path.realpath(os.path.dirname(__file__))
        with restore_sys_path():
            # setup new
            sys.path.append(os.path.join(path, "data", "extensions"))
            # setup old
            self.update_settings(dict(
                plugin_path=[os.path.join(path, "data", "extensions", "non-mod")]
            ))

            mem_cls = self.plugin_manager.get_plugin_class(
                "package_repository", "memory")
            self.assertEqual("bar", mem_cls.on_test)


if __name__ == '__main__':
    unittest.main()

