# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
test package searching (ResourceSearcher, ResourceSearchResultFormatter)
"""
from rez.package_search import ResourceSearcher, ResourceSearchResultFormatter
from rez.tests.util import TestBase, TempdirMixin
import os.path


class TestPackageSearch(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls) -> None:
        TempdirMixin.setUpClass()

        cls.solver_packages_path = cls.data_path("solver", "packages")
        cls.packages_base_path = cls.data_path("packages")
        cls.yaml_packages_path = os.path.join(cls.packages_base_path, "yaml_packages")
        cls.py_packages_path = os.path.join(cls.packages_base_path, "py_packages")

        cls.settings = dict(
            packages_path=[cls.solver_packages_path,
                           cls.yaml_packages_path,
                           cls.py_packages_path],
            package_filter=None)

    @classmethod
    def tearDownClass(cls) -> None:
        TempdirMixin.tearDownClass()

    def test_search_no_pattern_returns_all_families(self) -> None:
        """searching with no request returns every family, sorted by name."""
        searcher = ResourceSearcher()
        resource_type, results = searcher.search()

        self.assertEqual(resource_type, "family")
        names = [x.resource for x in results]
        self.assertEqual(names, sorted(names))
        self.assertIn("versioned", names)
        self.assertIn("timestamped", names)

    def test_search_family_glob(self) -> None:
        """a glob pattern matching several families returns them, sorted."""
        searcher = ResourceSearcher()
        resource_type, results = searcher.search("single_*")

        self.assertEqual(resource_type, "family")
        self.assertEqual(
            [x.resource for x in results],
            ["single_unversioned", "single_versioned"],
        )

    def test_search_no_match_returns_empty(self) -> None:
        """a pattern matching nothing returns an empty result list."""
        searcher = ResourceSearcher()
        resource_type, results = searcher.search("nonexistent_package_xyz")

        self.assertEqual(results, [])

    def test_search_single_family_without_version_returns_packages(self) -> None:
        """an exact, unambiguous family name returns packages, not just the family."""
        searcher = ResourceSearcher()
        resource_type, results = searcher.search("timestamped")

        self.assertEqual(resource_type, "package")
        versions = sorted(str(x.resource.version) for x in results)
        self.assertEqual(
            versions,
            ["1.0.5", "1.0.6", "1.1.0", "1.1.1", "1.2.0", "2.0.0", "2.1.0", "2.1.5"],
        )

    def test_search_with_version_range(self) -> None:
        """a request with a version range only returns matching packages."""
        searcher = ResourceSearcher()
        resource_type, results = searcher.search("timestamped-1.1+<2")

        self.assertEqual(resource_type, "package")
        versions = sorted(str(x.resource.version) for x in results)
        self.assertEqual(versions, ["1.1.0", "1.1.1", "1.2.0"])

    def test_search_latest_only(self) -> None:
        """latest=True returns only the highest version of each matching family."""
        searcher = ResourceSearcher(latest=True)
        resource_type, results = searcher.search("timestamped")

        self.assertEqual(resource_type, "package")
        self.assertEqual(len(results), 1)
        self.assertEqual(str(results[0].resource.version), "2.1.5")

    def test_search_after_time(self) -> None:
        """after_time excludes packages with a timestamp older than the given
        time; the boundary itself is included."""
        searcher = ResourceSearcher(after_time=5000)
        resource_type, results = searcher.search("timestamped")

        versions = sorted(str(x.resource.version) for x in results)
        self.assertEqual(versions, ["1.2.0", "2.0.0", "2.1.0", "2.1.5"])

    def test_search_before_time(self) -> None:
        """before_time excludes packages released at or after the given time."""
        searcher = ResourceSearcher(before_time=5000)
        resource_type, results = searcher.search("timestamped")

        versions = sorted(str(x.resource.version) for x in results)
        self.assertEqual(versions, ["1.0.5", "1.0.6", "1.1.0", "1.1.1"])

    def test_search_explicit_resource_type_variant(self) -> None:
        """resource_type='variant' iterates variants instead of packages."""
        searcher = ResourceSearcher(resource_type="variant")
        resource_type, results = searcher.search("variants_py")

        self.assertEqual(resource_type, "variant")
        self.assertEqual(len(results), 2)
        for result in results:
            self.assertEqual(result.resource_type, "variant")

    def test_search_explicit_resource_type_family(self) -> None:
        """resource_type='family' is honored even when a version range is given."""
        searcher = ResourceSearcher(resource_type="family")
        resource_type, results = searcher.search("timestamped-1.1")

        self.assertEqual(resource_type, "family")
        self.assertEqual([x.resource for x in results], ["timestamped"])


class TestResourceSearchResultFormatter(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls) -> None:
        TempdirMixin.setUpClass()

        cls.solver_packages_path = cls.data_path("solver", "packages")
        cls.packages_base_path = cls.data_path("packages")
        cls.yaml_packages_path = os.path.join(cls.packages_base_path, "yaml_packages")
        cls.py_packages_path = os.path.join(cls.packages_base_path, "py_packages")

        cls.settings = dict(
            packages_path=[cls.solver_packages_path,
                           cls.yaml_packages_path,
                           cls.py_packages_path],
            package_filter=None)

    @classmethod
    def tearDownClass(cls) -> None:
        TempdirMixin.tearDownClass()

    def _search(self, request, **kwargs):
        searcher = ResourceSearcher(**kwargs)
        return searcher.search(request)

    def test_format_defaults_to_qualified_name(self) -> None:
        """with no output_format, packages are formatted as their qualified name."""
        _, results = self._search("versioned-3.0")
        formatter = ResourceSearchResultFormatter()

        lines = formatter.format_search_results(results)

        self.assertEqual([text for text, _ in lines], ["versioned-3.0"])

    def test_format_family_ignores_output_format(self) -> None:
        """family results are always just the family name, regardless of output_format."""
        _, results = self._search("single_*")
        formatter = ResourceSearchResultFormatter(output_format="{qualified_name}")

        lines = formatter.format_search_results(results)

        self.assertEqual(
            [text for text, _ in lines],
            ["single_unversioned", "single_versioned"],
        )

    def test_format_with_custom_output_format(self) -> None:
        """output_format expands unambiguous abbreviations of resource attributes."""
        _, results = self._search("versioned-3.0")
        # "qual" is an unambiguous prefix of "qualified_name".
        formatter = ResourceSearchResultFormatter(output_format="{name}-{qual}")

        lines = formatter.format_search_results(results)

        self.assertEqual([text for text, _ in lines], ["versioned-versioned-3.0"])

    def test_format_ambiguous_abbreviation_left_unexpanded(self) -> None:
        """an abbreviation matching more than one field is left as-is."""
        _, results = self._search("versioned-3.0")
        # "v" is ambiguous: matches both "version" and "variants".
        formatter = ResourceSearchResultFormatter(output_format="{v}")

        lines = formatter.format_search_results(results)

        self.assertEqual([text for text, _ in lines], ["{v}"])

    def test_format_splits_output_on_literal_newline_token(self) -> None:
        """a literal '\\n' in output_format produces one formatted line per split."""
        _, results = self._search("versioned-3.0")
        formatter = ResourceSearchResultFormatter(output_format="{name}\\nsecond")

        lines = formatter.format_search_results(results)

        self.assertEqual([text for text, _ in lines], ["versioned", "second"])
