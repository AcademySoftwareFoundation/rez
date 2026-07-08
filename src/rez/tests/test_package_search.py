# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
test package_search module
"""
import unittest

from rez.package_search import get_reverse_dependency_tree, get_plugins, \
    ResourceSearcher, ResourceSearchResultFormatter, ResourceSearchResult
from rez.tests.util import TestBase, TempdirMixin
from rez.version import Version

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

    def test_resource_searcher_family(self) -> None:
        """test ResourceSearcher finds a package family by name"""
        searcher = ResourceSearcher(package_paths=[self.solver_packages_path])
        resource_type, results = searcher.search("pydad")

        self.assertEqual(resource_type, "package")
        # pydad has 3 versions, all should be found
        self.assertEqual(len(results), 3)

    def test_resource_searcher_latest_only(self) -> None:
        """test ResourceSearcher with latest=True returns only newest version"""
        searcher = ResourceSearcher(package_paths=[self.solver_packages_path], latest=True)
        resource_type, results = searcher.search("pydad")

        self.assertEqual(resource_type, "package")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].resource.version, Version("3"))
    def test_formatter_default_output(self) -> None:
        """test ResourceSearchResultFormatter with default (no output_format) settings"""
        searcher = ResourceSearcher(package_paths=[self.solver_packages_path], latest=True)
        resource_type, results = searcher.search("pydad")

        formatter = ResourceSearchResultFormatter()
        formatted_lines = formatter.format_search_results(results)

        # default output just shows the qualified name
        self.assertEqual(len(formatted_lines), 1)
        text, color = formatted_lines[0]
        self.assertEqual(text, "pydad-3")
    def test_resource_search_result(self) -> None:
        """test ResourceSearchResult stores its attributes correctly"""
        result = ResourceSearchResult("fake_resource", "package")

        self.assertEqual(result.resource, "fake_resource")
        self.assertEqual(result.resource_type, "package")
        self.assertIsNone(result.validation_error)

        result_with_error = ResourceSearchResult("fake_resource", "package", "some error")
        self.assertEqual(result_with_error.validation_error, "some error")

if __name__ == '__main__':
    unittest.main()
