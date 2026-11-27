# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Unit tests for rez.package_search.
"""
from __future__ import annotations

import io
import unittest
from unittest.mock import patch

from rez.config import config
from rez.exceptions import PackageFamilyNotFoundError, ResourceContentError
from rez.package_repository import package_repository_manager
from rez.package_search import (
    ResourceSearcher,
    ResourceSearchResult,
    ResourceSearchResultFormatter,
    get_plugins,
    get_reverse_dependency_tree,
)
from rez.tests.util import TestBase
from rez.utils.colorize import critical, error, info


def _make_memory_repo(data):
    mem_path = "memory@%s" % hex(id(data))
    repo = package_repository_manager.get_repository(mem_path)
    repo.data = data
    return mem_path


class TestGetReverseDependencyTree(TestBase):
    def test_unknown_package_raises(self):
        mem_path = _make_memory_repo({"foo": {"1.0": {"name": "foo", "version": "1.0"}}})
        with self.assertRaises(PackageFamilyNotFoundError):
            get_reverse_dependency_tree("nonexistent", paths=[mem_path])

    def test_depth_zero(self):
        mem_path = _make_memory_repo({
            "a": {"1.0": {"name": "a", "version": "1.0"}},
            "b": {"1.0": {"name": "b", "version": "1.0", "requires": ["a"]}},
        })
        pkgs_list, g = get_reverse_dependency_tree("a", depth=0, paths=[mem_path])
        self.assertEqual(pkgs_list, [["a"]])
        self.assertEqual(g.nodes(), ["a"])
        self.assertEqual(g.edges(), [])

    def test_multi_level_and_depth_limit(self):
        mem_path = _make_memory_repo({
            "a": {"1.0": {"name": "a", "version": "1.0"}},
            "b": {"1.0": {"name": "b", "version": "1.0", "requires": ["a"]}},
            "c": {"1.0": {"name": "c", "version": "1.0", "requires": ["b"]}},
            "d": {"1.0": {"name": "d", "version": "1.0", "requires": ["a"]}},
            "e": {"1.0": {"name": "e", "version": "1.0"}},
            "empty_family": {},
        })
        pkgs_list, g = get_reverse_dependency_tree("a", paths=[mem_path])
        self.assertEqual(pkgs_list, [["a"], ["b", "d"], ["c"]])
        self.assertEqual(set(g.nodes()), {"a", "b", "c", "d"})
        self.assertEqual(set(g.edges()), {("b", "a"), ("d", "a"), ("c", "b")})

        pkgs_list_d1, g_d1 = get_reverse_dependency_tree("a", depth=1, paths=[mem_path])
        self.assertEqual(pkgs_list_d1, [["a"], ["b", "d"]])
        self.assertEqual(set(g_d1.nodes()), {"a", "b", "d"})
        self.assertEqual(set(g_d1.edges()), {("b", "a"), ("d", "a")})

    def test_uses_latest_version_and_ignores_conflicts(self):
        mem_path = _make_memory_repo({
            "a": {"1.0": {"name": "a", "version": "1.0"}},
            "old_dep": {
                "1.0": {"name": "old_dep", "version": "1.0", "requires": ["a"]},
                "2.0": {"name": "old_dep", "version": "2.0"},
            },
            "conflicter": {
                "1.0": {"name": "conflicter", "version": "1.0", "requires": ["!a"]},
            },
        })
        pkgs_list, g = get_reverse_dependency_tree("a", paths=[mem_path])
        self.assertEqual(pkgs_list, [["a"]])
        self.assertEqual(g.edges(), [])

    def test_build_requires_and_private_build_requires(self):
        mem_path = _make_memory_repo({
            "a": {"1.0": {"name": "a", "version": "1.0"}},
            "b": {
                "1.0": {
                    "name": "b",
                    "version": "1.0",
                    "build_requires": ["a"],
                }
            },
        })
        pkgs_no_br, _ = get_reverse_dependency_tree("a", paths=[mem_path], build_requires=False)
        self.assertEqual(pkgs_no_br, [["a"]])

        pkgs_br, _ = get_reverse_dependency_tree("a", paths=[mem_path], build_requires=True)
        self.assertEqual(pkgs_br, [["a"], ["b"]])

    @unittest.expectedFailure
    def test_private_build_requires_includes_dependents(self):
        # src/rez/package_search.py:86 uses
        # `pbr = (private_build_requires and pkg.name == package_name)`, which
        # prevents traversing dependents' private_build_requires.
        mem_path = _make_memory_repo({
            "app": {
                "1.0": {
                    "name": "app",
                    "version": "1.0",
                    "private_build_requires": ["tool"],
                }
            },
            "tool": {"1.0": {"name": "tool", "version": "1.0"}},
        })
        pkgs_pbr, _ = get_reverse_dependency_tree(
            "tool", paths=[mem_path], private_build_requires=True
        )
        self.assertEqual(pkgs_pbr, [["tool"], ["app"]])

    def test_cyclic_dependencies_and_variants(self):
        mem_path = _make_memory_repo({
            "a": {
                "1.0": {
                    "name": "a",
                    "version": "1.0",
                    "requires": ["b"],
                }
            },
            "b": {
                "1.0": {
                    "name": "b",
                    "version": "1.0",
                    "variants": [["a"], ["other"]],
                }
            },
            "other": {"1.0": {"name": "other", "version": "1.0"}},
        })
        pkgs_list, g = get_reverse_dependency_tree("a", paths=[mem_path])
        self.assertEqual(pkgs_list, [["a"], ["b"]])
        self.assertEqual(set(g.edges()), {("b", "a")})


class TestGetPlugins(TestBase):
    def test_no_plugins_flag(self):
        mem_path = _make_memory_repo({
            "app": {"1.0": {"name": "app", "version": "1.0", "has_plugins": False}},
            "plug": {"1.0": {"name": "plug", "version": "1.0", "plugin_for": ["app"]}},
        })
        self.assertEqual(get_plugins("app", paths=[mem_path]), [])

    def test_finds_plugins_and_skips_self_and_non_plugins(self):
        mem_path = _make_memory_repo({
            "app": {
                "1.0": {
                    "name": "app",
                    "version": "1.0",
                    "has_plugins": True,
                    "plugin_for": ["app"],
                }
            },
            "plug1": {"1.0": {"name": "plug1", "version": "1.0", "plugin_for": ["app"]}},
            "plug2": {"1.0": {"name": "plug2", "version": "1.0", "plugin_for": ["other", "app"]}},
            "other": {"1.0": {"name": "other", "version": "1.0"}},
        })
        plugins = get_plugins("app", paths=[mem_path])
        self.assertEqual(sorted(plugins), ["plug1", "plug2"])

    @unittest.expectedFailure
    def test_empty_package_family_skipped(self):
        # src/rez/package_search.py:158-159 raises AttributeError when
        # get_latest_package returns None for an empty package family.
        mem_path = _make_memory_repo({
            "app": {"1.0": {"name": "app", "version": "1.0", "has_plugins": True}},
            "plug": {"1.0": {"name": "plug", "version": "1.0", "plugin_for": ["app"]}},
            "empty_family": {},
        })
        self.assertEqual(get_plugins("app", paths=[mem_path]), ["plug"])


class TestResourceSearcher(TestBase):
    def test_init_package_paths_modes(self):
        s_explicit = ResourceSearcher(package_paths=["/some/path"])
        self.assertEqual(s_explicit.package_paths, ["/some/path"])

        s_no_local = ResourceSearcher(no_local=True)
        self.assertEqual(s_no_local.package_paths, config.nonlocal_packages_path)

        s_default = ResourceSearcher()
        self.assertIsNone(s_default.package_paths)

    def test_parse_request(self):
        self.assertEqual(ResourceSearcher._parse_request(None), ("*", None))
        self.assertEqual(ResourceSearcher._parse_request("foo"), ("foo", None))

        name, vrange = ResourceSearcher._parse_request("foo-1.0+")
        self.assertEqual(name, "foo")
        self.assertIsNotNone(vrange)
        self.assertEqual(str(vrange), "1.0+")

        # Glob pattern is parsed with no version range
        self.assertEqual(ResourceSearcher._parse_request("foo*"), ("foo*", None))
        # Invalid Requirement falls back to raw pattern
        self.assertEqual(ResourceSearcher._parse_request("foo--1"), ("foo--1", None))

    def test_search_families_and_empty_results(self):
        mem_path = _make_memory_repo({
            "alpha": {"1.0": {"name": "alpha", "version": "1.0"}},
            "beta": {"1.0": {"name": "beta", "version": "1.0"}},
        })
        searcher = ResourceSearcher(package_paths=[mem_path])

        rtype, results = searcher.search(None)
        self.assertEqual(rtype, "family")
        self.assertEqual([r.resource for r in results], ["alpha", "beta"])
        self.assertTrue(all(r.resource_type == "family" for r in results))

        rtype_none, results_none = searcher.search("nomatch*")
        self.assertEqual(rtype_none, "family")
        self.assertEqual(results_none, [])

    def test_search_packages_single_family_version_range_and_latest(self):
        mem_path = _make_memory_repo({
            "alpha": {
                "1.0": {"name": "alpha", "version": "1.0"},
                "2.0": {"name": "alpha", "version": "2.0"},
                "3.0": {"name": "alpha", "version": "3.0"},
            },
            "beta": {"1.0": {"name": "beta", "version": "1.0"}},
        })
        # Single matching family auto-selects "package"
        searcher = ResourceSearcher(package_paths=[mem_path])
        rtype, results = searcher.search("alpha")
        self.assertEqual(rtype, "package")
        self.assertEqual([str(r.resource.version) for r in results], ["1.0", "2.0", "3.0"])

        # Version range auto-selects "package"
        rtype_v, results_v = searcher.search("alpha-2.0+")
        self.assertEqual(rtype_v, "package")
        self.assertEqual([str(r.resource.version) for r in results_v], ["2.0", "3.0"])

        # latest=True returns only highest version
        searcher_latest = ResourceSearcher(package_paths=[mem_path], latest=True)
        _, results_latest = searcher_latest.search("alpha")
        self.assertEqual([str(r.resource.version) for r in results_latest], ["3.0"])

    def test_search_time_filters(self):
        mem_path = _make_memory_repo({
            "alpha": {
                "1.0": {"name": "alpha", "version": "1.0", "timestamp": 100},
                "2.0": {"name": "alpha", "version": "2.0", "timestamp": 200},
                "3.0": {"name": "alpha", "version": "3.0", "timestamp": 300},
            },
        })
        searcher = ResourceSearcher(
            package_paths=[mem_path],
            resource_type="package",
            after_time=150,
            before_time=300,
        )
        rtype, results = searcher.search("alpha")
        self.assertEqual(rtype, "package")
        self.assertEqual([str(r.resource.version) for r in results], ["2.0"])

    def test_search_variants(self):
        mem_path = _make_memory_repo({
            "alpha": {
                "1.0": {
                    "name": "alpha",
                    "version": "1.0",
                    "variants": [["dep1"], ["dep2"]],
                },
            },
        })
        searcher = ResourceSearcher(package_paths=[mem_path], resource_type="variant")
        rtype, results = searcher.search("alpha")
        self.assertEqual(rtype, "variant")
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r.resource_type == "variant" for r in results))

    def test_search_validation_errors(self):
        mem_path = _make_memory_repo({
            "alpha": {
                "1.0": {
                    "name": "alpha",
                    "version": "1.0",
                    "variants": [["dep1"]],
                },
            },
        })
        # Package validation failure recorded when resource_type == "package"
        searcher_pkg = ResourceSearcher(
            package_paths=[mem_path], resource_type="package", validate=True
        )
        with patch("rez.packages.Package.validate_data", side_effect=ResourceContentError("bad pkg")):
            rtype, results = searcher_pkg.search("alpha")
        self.assertEqual(rtype, "package")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].validation_error, "bad pkg")

        # Package validation failure skips variants when resource_type == "variant"
        searcher_var = ResourceSearcher(
            package_paths=[mem_path], resource_type="variant", validate=True
        )
        with patch("rez.packages.Package.validate_data", side_effect=ResourceContentError("bad pkg")):
            _, results_skip = searcher_var.search("alpha")
        self.assertEqual(results_skip, [])

        # Variant validation failure recorded
        with patch("rez.packages.Package.validate_data", return_value=None), patch(
            "rez.packages.Variant.validate_data", side_effect=ResourceContentError("bad var")
        ):
            _, results_var_err = searcher_var.search("alpha")
        self.assertEqual(len(results_var_err), 1)
        self.assertEqual(results_var_err[0].resource_type, "variant")
        self.assertEqual(results_var_err[0].validation_error, "bad var")

        # Valid variant with validate=True
        with patch("rez.packages.Package.validate_data", return_value=None), patch(
            "rez.packages.Variant.validate_data", return_value=None
        ):
            _, results_var_ok = searcher_var.search("alpha")
        self.assertEqual(len(results_var_ok), 1)
        self.assertIsNone(results_var_ok[0].validation_error)

        # iter_variants raising ResourceContentError is caught
        with patch("rez.packages.Package.validate_data", return_value=None), patch(
            "rez.packages.Package.iter_variants", side_effect=ResourceContentError("bad variants")
        ):
            _, results_iter_err = searcher_var.search("alpha")
        self.assertEqual(results_iter_err, [])


class TestResourceSearchResultFormatter(TestBase):
    def _make_package(self):
        mem_path = _make_memory_repo({
            "alpha": {
                "1.2.3": {
                    "name": "alpha",
                    "version": "1.2.3",
                    "description": "line1\nline2",
                }
            }
        })
        searcher = ResourceSearcher(package_paths=[mem_path], resource_type="package")
        _, results = searcher.search("alpha")
        return results[0]

    def test_format_family_and_default_and_validation_error(self):
        pkg_res = self._make_package()
        fam_res = ResourceSearchResult("alpha", "family")
        err_res = ResourceSearchResult(pkg_res.resource, "package", validation_error="invalid data")

        fmt = ResourceSearchResultFormatter()
        lines = fmt.format_search_results([fam_res, pkg_res, err_res])
        self.assertEqual(
            lines,
            [
                ("alpha", info),
                ("alpha-1.2.3", info),
                ("alpha-1.2.3", error),
                ("invalid data", critical),
            ],
        )

    def test_format_with_output_format_and_suppress_newlines(self):
        pkg_res = self._make_package()
        fmt = ResourceSearchResultFormatter(
            output_format="{qualified_name}\\n{description}",
            suppress_newlines=True,
        )
        lines = fmt.format_search_results([pkg_res])
        self.assertEqual(
            lines,
            [
                ("alpha-1.2.3", info),
                ("line1\\nline2", info),
            ],
        )

        fmt_keep = ResourceSearchResultFormatter(
            output_format="{description}",
            suppress_newlines=False,
        )
        lines_keep = fmt_keep.format_search_results([pkg_res])
        self.assertEqual(lines_keep, [("line1\nline2", info)])

    def test_format_handles_resource_content_error(self):
        pkg_res = self._make_package()
        fmt = ResourceSearchResultFormatter(output_format="{name}")
        with patch.object(pkg_res.resource, "format", side_effect=ResourceContentError("corrupt")):
            lines = fmt.format_search_results([pkg_res])
        self.assertEqual(
            lines,
            [
                ("alpha-1.2.3", error),
                ("corrupt", critical),
            ],
        )

    def test_print_search_results(self):
        fam_res = ResourceSearchResult("alpha", "family")
        buf = io.StringIO()
        fmt = ResourceSearchResultFormatter()
        with patch("rez.package_search.Printer") as mock_printer:
            fmt.print_search_results([fam_res], buf=buf)
            mock_printer.assert_called_once_with(buf)
            mock_printer.return_value.assert_called_once_with("alpha", info)

        # Also exercise real Printer with StringIO
        buf_real = io.StringIO()
        fmt.print_search_results([fam_res], buf=buf_real)
        self.assertIn("alpha", buf_real.getvalue())
