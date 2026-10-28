# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
test rezplugins manager behaviors
"""
from rez.tests.util import TestBase, TempdirMixin, restore_sys_path
from rez.plugin_managers import plugin_manager, uncache_rezplugins_module_paths
from rez.package_repository import package_repository_manager
from unittest.mock import patch
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

    def test_discovers_entry_points_once_for_all_plugin_types(self) -> None:
        """Installed distributions are scanned once across plugin types."""
        from rez.plugin_managers import entry_points

        with patch("rez.plugin_managers.entry_points", wraps=entry_points) as discover:
            plugin_manager.get_plugins("shell")
            plugin_manager.get_plugins("release_vcs")

        discover.assert_called_once_with()

    def test_rediscovers_entry_points_when_sys_path_changes(self) -> None:
        """Changing import locations invalidates entry-point discovery."""
        from rez.plugin_managers import entry_points

        with patch("rez.plugin_managers.entry_points", wraps=entry_points) as discover:
            plugin_manager.get_plugins("shell")
            with restore_sys_path():
                sys.path.append(self.data_path("extensions"))
                plugin_manager.get_plugins("release_vcs")

        self.assertEqual(discover.call_count, 2)

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

    def test_loads_config_once_per_plugin_path(self) -> None:
        """Each plugin directory's shared config is loaded only once."""
        from rez.plugin_managers import _load_config_from_filepaths

        with patch(
            "rez.plugin_managers._load_config_from_filepaths",
            wraps=_load_config_from_filepaths,
        ) as load_config:
            plugin_manager.get_plugins("shell")

        config_paths = [call.args[0][0] for call in load_config.call_args_list]
        self.assertGreater(len(config_paths), 0)
        self.assertEqual(len(config_paths), len(set(config_paths)))


if __name__ == '__main__':
    unittest.main()
