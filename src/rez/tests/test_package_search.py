# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Test cases for package_search.py (package searching)
"""
import os

from rez.package_maker import make_package
from rez.package_search import get_plugins
from rez.tests.util import TestBase, TempdirMixin


class TestPackageSearch(TestBase, TempdirMixin):
    """Class for a package searching test case"""
    @classmethod
    def setUpClass(cls):
        TempdirMixin.setUpClass()

        cls.settings = dict(
            packages_path=[
                cls.root
            ]
        )

    @classmethod
    def tearDownClass(cls):
        TempdirMixin.tearDownClass()

    def test_get_plugins(self):
        """Ensure package plugins are obtained as expected."""

        with make_package('foo', self.root) as pkg:
            pkg.has_plugins = True

        with make_package('foo_plugin', self.root) as pkg:
            pkg.plugin_for = ["foo"]

        plugins = get_plugins('foo')
        self.assertEqual(plugins, ['foo_plugin'])

    def test_get_plugins_empty_folder(self):
        """When an empty folder is present, plugins should still be valid."""

        with make_package('foo', self.root) as pkg:
            pkg.has_plugins = True

        with make_package('foo_plugin', self.root) as pkg:
            pkg.plugin_for = ["foo"]

        os.mkdir(os.path.join(self.root, 'broken_pkg'))

        plugins = get_plugins('foo')
        self.assertEqual(plugins, ['foo_plugin'])
