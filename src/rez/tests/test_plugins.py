"""
Test the plugin system
"""
from rez.tests.util import TestBase
from rez.plugin_managers import plugin_manager


class TestPlugins(TestBase):
    @classmethod
    def setUpClass(cls):
        cls.settings = {}

    def test_1(self):
        """Test that the custom plugin is present."""
        plugin_names = plugin_manager.get_plugins('package_repository')
        self.assertTrue("stub" in plugin_names)

    def test_2(self):
        """Test plugin config settings."""
        from rez.config import config

        self.assertTrue(config.plugins.package_repository.stub.floob is True)
