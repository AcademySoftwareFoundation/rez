# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
test rezplugins manager behaviors
"""
from rez.tests.util import TestBase, TempdirMixin, restore_sys_path
from rez.plugin_managers import plugin_manager, uncache_rezplugins_module_paths
from rez.package_repository import package_repository_manager
import sys
import unittest


class TestPluginManagers(TestBase, TempdirMixin):
    def __init__(self, *nargs, **kwargs) -> None:
        TestBase.__init__(self, *nargs, **kwargs)
        self._reset_plugin_manager()

    @classmethod
    def _reset_plugin_manager(cls) -> None:
        # for resetting package_repository type plugins
        package_repository_manager.clear_caches()
        package_repository_manager.pool.resource_classes.clear()
        # for resetting new-style plugins
        uncache_rezplugins_module_paths()

        plugin_types = []
        for singleton in plugin_manager._plugin_types.values():
            plugin_types.append(singleton.instance_class)
        plugin_manager._plugin_types.clear()

        for plugin_type in plugin_types:
            plugin_manager.register_plugin_type(plugin_type)

        for key in list(sys.modules.keys()):
            if key.startswith("rezplugins."):
                del sys.modules[key]

    @classmethod
    def setUpClass(cls) -> None:
        cls.settings = {"debug_plugins": True}

    @classmethod
    def tearDownClass(cls) -> None:
        cls._reset_plugin_manager()

    def setUp(self) -> None:
        TestBase.setUp(self)
        self._reset_plugin_manager()

    def test_load_plugin_from_plugin_path(self) -> None:
        """Test loading rez plugin from plugin_path"""
        self.update_settings(dict(
            plugin_path=[self.data_path("extensions", "foo")]
        ))

        cloud_cls = plugin_manager.get_plugin_class(
            "package_repository", "cloud")
        self.assertEqual(cloud_cls.name(), "cloud")

    def test_load_plugin_from_python_module(self) -> None:
        """Test loading rez plugin from python modules"""
        with restore_sys_path():
            sys.path.append(self.data_path("extensions"))

            cloud_cls = plugin_manager.get_plugin_class(
                "package_repository", "cloud")
            self.assertEqual(cloud_cls.name(), "cloud")

    def test_load_plugin_from_entry_points(self) -> None:
        """Test loading rez plugin from setuptools entry points"""
        with restore_sys_path():
            sys.path.append(self.data_path("extensions", "baz"))
            baz_cls = plugin_manager.get_plugin_class("command", "baz_cmd")
            self.assertEqual(baz_cls.name(), "baz_cmd")

    def test_plugin_override_1(self) -> None:
        """Test plugin from plugin_path can override the default"""
        self.update_settings(dict(
            plugin_path=[self.data_path("extensions", "non-mod")]
        ))

        mem_cls = plugin_manager.get_plugin_class(
            "package_repository", "memory")
        self.assertEqual("non-mod", mem_cls.on_test)

    def test_plugin_override_2(self) -> None:
        """Test plugin from python modules can override the default"""
        with restore_sys_path():
            sys.path.append(self.data_path("extensions"))

            mem_cls = plugin_manager.get_plugin_class(
                "package_repository", "memory")
            self.assertEqual("bar", mem_cls.on_test)

    def test_plugin_override_3(self) -> None:
        """Test plugin from python modules can override plugin_path"""
        with restore_sys_path():
            # setup new
            sys.path.append(self.data_path("extensions"))
            # setup old
            self.update_settings(dict(
                plugin_path=[self.data_path("extensions", "non-mod")]
            ))

            mem_cls = plugin_manager.get_plugin_class(
                "package_repository", "memory")
            self.assertEqual("bar", mem_cls.on_test)


if __name__ == '__main__':
    unittest.main()
