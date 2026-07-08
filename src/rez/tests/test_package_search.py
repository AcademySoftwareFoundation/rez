# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
test package_search module
"""
import unittest

from rez.package_search import get_reverse_dependency_tree, get_plugins, \
    ResourceSearcher
from rez.tests.util import TestBase, TempdirMixin


class TestPackageSearch(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls) -> None:
        TempdirMixin.setUpClass()

        cls.solver_packages_path = cls.data_path("solver", "packages")

        cls.settings = dict(
            packages_path=[cls.solver_packages_path],
        )

    @classmethod
    def tearDownClass(cls) -> None:
        TempdirMixin.tearDownClass()

    def test_reverse_dependency_tree(self) -> None:
        """test get_reverse_dependency_tree finds direct and indirect parents"""
        pkgs_list, g = get_reverse_dependency_tree("pymum")

        self.assertEqual(pkgs_list[0], ["pymum"])
        self.assertEqual(pkgs_list[1], ["pydad", "pyson"])

    def test_reverse_dependency_tree_depth_limit(self) -> None:
        """test get_reverse_dependency_tree respects depth limit"""
        pkgs_list, g = get_reverse_dependency_tree("pymum", depth=0)

        # depth=0 means only the root package itself, no parents
        self.assertEqual(len(pkgs_list), 1)
        self.assertEqual(pkgs_list[0], ["pymum"])

if __name__ == '__main__':
    unittest.main()
