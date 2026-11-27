# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Additional unit tests for rez.packages covering edge cases and uncovered paths.
"""
import io
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

from rez.exceptions import PackageFamilyNotFoundError, ResourceError
from rez.package_repository import package_repository_manager
from rez.packages import (
    Package,
    PackageBaseResourceWrapper,
    PackageFamily,
    PackageSearchPath,
    Variant,
    create_package,
    get_completions,
    get_last_release_time,
    get_latest_package,
    get_latest_package_from_string,
    get_package,
    get_package_from_handle,
    get_package_from_repository,
    get_package_from_string,
    get_package_from_uri,
    get_variant,
    get_variant_from_uri,
)
from rez.resolved_context import ResolvedContext
from rez.serialise import FileFormat
from rez.tests.util import TempdirMixin, TestBase
from rez.utils.formatting import PackageRequest
from rez.utils.sourcecode import SourceCode
from rez.vendor.schema.schema import Schema, SchemaError
from rez.version import Version


class TestPackagesExtra(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        TempdirMixin.setUpClass()

        cls.solver_packages_path = cls.data_path("solver", "packages")
        cls.packages_base_path = cls.data_path("packages")
        cls.yaml_packages_path = os.path.join(cls.packages_base_path, "yaml_packages")
        cls.py_packages_path = os.path.join(cls.packages_base_path, "py_packages")

        cls.settings = dict(
            packages_path=[
                cls.solver_packages_path,
                cls.yaml_packages_path,
                cls.py_packages_path,
            ],
            package_filter=None,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        TempdirMixin.tearDownClass()
        super().tearDownClass()

    def test_base_wrapper_arbitrary_keys_not_implemented(self) -> None:
        """PackageBaseResourceWrapper.arbitrary_keys raises NotImplementedError."""
        pkg = create_package("foo", {"version": "1.0"})
        with self.assertRaises(NotImplementedError):
            PackageBaseResourceWrapper.arbitrary_keys(pkg)

    def test_is_local(self) -> None:
        """Package.is_local reflects whether the package resides in local_packages_path."""
        self.update_settings({"local_packages_path": self.py_packages_path})
        local_pkg = get_package_from_repository("versioned", "3.0", self.py_packages_path)
        remote_pkg = get_package_from_repository("versioned", "2.0", self.yaml_packages_path)
        self.assertTrue(local_pkg.is_local)
        self.assertFalse(remote_pkg.is_local)

    def test_set_context_and_late_binding_cache_and_in_context(self) -> None:
        """set_context updates context, late-binding caches results and sees in_context()."""
        pkg = get_package("late_binding", "1.0")
        # First access evaluates late binding; second access hits cache
        tools_first = pkg.tools
        tools_second = pkg.tools
        self.assertEqual(tools_first, ["util"])
        self.assertEqual(tools_second, ["util"])

        # Evaluate a late-bound function with a ResolvedContext attached
        def _late_tools():
            return ["yes"] if in_context() else ["no"]  # noqa: F821

        sc = SourceCode(func=_late_tools)
        sc.late_binding = True
        ctx_pkg = create_package(
            "ctx_late",
            {
                "version": "1.0",
                "tools": sc,
            },
        )
        # Without context
        self.assertEqual(ctx_pkg.tools, ["no"])

        # Clear cache and attach a ResolvedContext
        ctx_pkg._late_binding_returnvalues.clear()
        ctx = ResolvedContext(["nada"])
        ctx_pkg.set_context(ctx)
        self.assertIs(ctx_pkg.context, ctx)
        self.assertEqual(ctx_pkg.tools, ["yes"])

    def test_print_info_package_and_variant(self) -> None:
        """print_info writes package and variant info, handling config, release keys, and stdout."""
        pkg = create_package(
            "info_pkg",
            {
                "version": "1.0",
                "description": "info test",
                "timestamp": 123456,
                "config": {"default_relocatable": True},
                "variants": [["python-2.7"]],
            },
        )

        # Package print_info with default include_release=False
        buf = io.StringIO()
        pkg.print_info(buf=buf)
        output = buf.getvalue()
        self.assertIn("info_pkg", output)
        self.assertNotIn("timestamp", output)

        # Package print_info with include_release=True, skip_attributes, and FileFormat.py
        buf_py = io.StringIO()
        pkg.print_info(
            buf=buf_py,
            format_=FileFormat.py,
            skip_attributes=["description"],
            include_release=True,
        )
        output_py = buf_py.getvalue()
        self.assertIn("timestamp", output_py)
        self.assertNotIn("info test", output_py)

        # Variant print_info exercises self.parent.data.get("config")
        variant = pkg.get_variant(0)
        buf_var = io.StringIO()
        variant.print_info(buf=buf_var)
        self.assertIn("info_pkg", buf_var.getvalue())

        # buf=None defaults to sys.stdout
        stdout_buf = io.StringIO()
        with patch.object(sys, "stdout", stdout_buf):
            pkg.print_info()
        self.assertIn("info_pkg", stdout_buf.getvalue())

    def test_package_arbitrary_keys_and_as_exact_requirement(self) -> None:
        """Package.arbitrary_keys and Package.as_exact_requirement."""
        pkg = create_package(
            "arb_pkg",
            {
                "version": "1.2.3",
                "custom_field": "hello",
                "another_extra": 42,
            },
        )
        self.assertEqual(pkg.arbitrary_keys(), {"custom_field", "another_extra"})
        self.assertEqual(pkg.as_exact_requirement(), "arb_pkg==1.2.3")

        unver_pkg = create_package("unver_arb", {"description": "no version"})
        self.assertEqual(unver_pkg.as_exact_requirement(), "unver_arb")

    def test_is_relocatable_precedence(self) -> None:
        """Package.is_relocatable checks package attr, per-repo, per-package, then global default."""
        explicit_true = create_package("reloc_pkg", {"version": "1.0", "relocatable": True})
        self.assertTrue(explicit_true.is_relocatable)

        explicit_false = create_package("reloc_pkg2", {"version": "1.0", "relocatable": False})
        self.assertFalse(explicit_false.is_relocatable)

        pkg = create_package("reloc_unset", {"version": "1.0"})
        repo_loc = pkg.repository.location

        # Per-repository setting wins over per-package and global
        self.update_settings(
            {
                "default_relocatable_per_repository": {repo_loc: False},
                "default_relocatable_per_package": {"reloc_unset": True},
                "default_relocatable": True,
            }
        )
        self.assertFalse(pkg.is_relocatable)

        # Per-package setting wins over global
        self.update_settings(
            {
                "default_relocatable_per_repository": {},
                "default_relocatable_per_package": {"reloc_unset": False},
                "default_relocatable": True,
            }
        )
        self.assertFalse(pkg.is_relocatable)

        # Falls back to global default_relocatable
        self.update_settings(
            {
                "default_relocatable_per_repository": {},
                "default_relocatable_per_package": {},
                "default_relocatable": False,
            }
        )
        self.assertFalse(pkg.is_relocatable)

    def test_is_cachable_precedence(self) -> None:
        """Package.is_cachable checks package attr, per-repo, per-package, global, then is_relocatable."""
        explicit_true = create_package("cache_pkg", {"version": "1.0", "cachable": True})
        self.assertTrue(explicit_true.is_cachable)

        pkg = create_package("cache_unset", {"version": "1.0"})
        repo_loc = pkg.repository.location

        # Per-repository setting
        self.update_settings(
            {
                "default_cachable_per_repository": {repo_loc: True},
                "default_cachable_per_package": {"cache_unset": False},
                "default_cachable": False,
            }
        )
        self.assertTrue(pkg.is_cachable)

        # Per-package setting
        self.update_settings(
            {
                "default_cachable_per_repository": {},
                "default_cachable_per_package": {"cache_unset": False},
                "default_cachable": True,
            }
        )
        self.assertFalse(pkg.is_cachable)

        # Global default_cachable
        self.update_settings(
            {
                "default_cachable_per_repository": {},
                "default_cachable_per_package": {},
                "default_cachable": True,
            }
        )
        self.assertTrue(pkg.is_cachable)

        # None falls back to is_relocatable
        self.update_settings(
            {
                "default_cachable_per_repository": {},
                "default_cachable_per_package": {},
                "default_cachable": None,
                "default_relocatable": False,
            }
        )
        self.assertFalse(pkg.is_cachable)

    def test_get_variant_found_and_missing(self) -> None:
        """Package.get_variant returns matching Variant or None when index not found."""
        pkg = get_package("variants_py", "2.0")
        self.assertGreater(pkg.num_variants, 0)
        v0 = pkg.get_variant(0)
        self.assertIsNotNone(v0)
        self.assertEqual(v0.index, 0)
        self.assertIsNone(pkg.get_variant(99))

    def test_variant_getattr_arbitrary_keys_and_requires(self) -> None:
        """Variant forwards arbitrary attributes, arbitrary_keys, qualified_name, and get_requires."""
        pkg = create_package(
            "var_pkg",
            {
                "version": "2.0",
                "requires": ["foo-1"],
                "build_requires": ["cmake-3"],
                "private_build_requires": ["ninja-1"],
                "custom_attr": "val",
                "variants": [["python-2.7"]],
            },
        )
        variant = pkg.get_variant(0)
        self.assertEqual(variant.custom_attr, "val")
        self.assertEqual(variant.arbitrary_keys(), {"custom_attr"})
        self.assertEqual(variant.qualified_name, "var_pkg-2.0[0]")

        with self.assertRaises(AttributeError) as ctx:
            _ = variant.no_such_attribute
        self.assertIn("Variant instance has no attribute 'no_such_attribute'", str(ctx.exception))

        self.assertEqual(
            variant.get_requires(),
            [PackageRequest("foo-1"), PackageRequest("python-2.7")],
        )
        self.assertEqual(
            variant.get_requires(build_requires=True),
            [
                PackageRequest("foo-1"),
                PackageRequest("python-2.7"),
                PackageRequest("cmake-3"),
            ],
        )
        self.assertEqual(
            variant.get_requires(build_requires=True, private_build_requires=True),
            [
                PackageRequest("foo-1"),
                PackageRequest("python-2.7"),
                PackageRequest("cmake-3"),
                PackageRequest("ninja-1"),
            ],
        )

        # Unvarianted package has index=None and empty variant_requires
        no_var_pkg = create_package("novar_pkg", {"version": "1.0"})
        novar = no_var_pkg.get_variant(None)
        self.assertIsNotNone(novar)
        self.assertEqual(novar.qualified_name, "novar_pkg-1.0[]")
        self.assertEqual(novar.variant_requires, [])
        self.assertIsNone(novar._non_shortlinked_subpath)

        fs_var = get_package("variants_py", "2.0").get_variant(0)
        self.assertIsInstance(fs_var._non_shortlinked_subpath, str)

    @unittest.expectedFailure
    def test_variant_parent_attribute_error_reraises_value_error(self) -> None:
        """Variant.parent should raise ValueError when repository lookup raises AttributeError.

        Expected failure: reraise(e, ValueError) in src/rez/utils/__init__.py:15-29
        re-raises AttributeError in src/rez/packages.py:415-419, which triggers
        RecursionError via Variant.__getattr__.
        """
        pkg = get_package("variants_py", "2.0")
        variant = pkg.get_variant(0)
        detached_variant = Variant(variant.resource, parent=None)
        with patch.object(
            detached_variant.repository,
            "get_parent_package",
            side_effect=AttributeError("missing parent"),
        ):
            with self.assertRaises(ValueError):
                _ = detached_variant.parent

    def test_variant_install_returns_self_when_same_resource(self) -> None:
        """Variant.install returns self when installing into its own repository."""
        pkg = get_package("variants_py", "2.0")
        variant = pkg.get_variant(0)
        result = variant.install(self.py_packages_path)
        self.assertIs(result, variant)

    def test_package_search_path(self) -> None:
        """PackageSearchPath iterates packages and checks repository membership via __contains__."""
        search_path = PackageSearchPath([self.solver_packages_path, self.py_packages_path])
        found = list(search_path.iter_packages("pyfoo", ">=3.1.0"))
        self.assertEqual([p.qualified_name for p in found], ["pyfoo-3.1.0"])

        in_pkg = get_package_from_repository("pyfoo", "3.0.0", self.solver_packages_path)
        out_pkg = get_package_from_repository("versioned", "2.0", self.yaml_packages_path)
        self.assertIn(in_pkg, search_path)
        self.assertNotIn(out_pkg, search_path)

    def test_get_package_helpers(self) -> None:
        """Test get_package miss, get_package_from_repository str/Version, handle, and string."""
        self.assertIsNone(get_package("does_not_exist", "1.0"))

        pkg_by_str = get_package_from_repository("versioned", "3.0", self.py_packages_path)
        pkg_by_ver = get_package_from_repository("versioned", Version("3.0"), self.py_packages_path)
        self.assertEqual(pkg_by_str, pkg_by_ver)

        # get_package_from_handle with ResourceHandle and dict
        from_handle = get_package_from_handle(pkg_by_str.handle)
        from_dict = get_package_from_handle(pkg_by_str.handle.to_dict())
        self.assertEqual(from_handle, pkg_by_str)
        self.assertEqual(from_dict, pkg_by_str)

        # get_package_from_string
        self.assertEqual(get_package_from_string("versioned-3.0"), pkg_by_str)
        self.assertIsNone(get_package_from_string("does_not_exist-1.0"))

        # get_variant with ResourceHandle and dict
        var_pkg = get_package("variants_py", "2.0")
        v0 = var_pkg.get_variant(0)
        self.assertEqual(get_variant(v0.handle), v0)
        self.assertEqual(get_variant(v0.handle.to_dict()), v0)

    def test_get_package_and_variant_from_uri_miss(self) -> None:
        """Test get_package_from_uri and get_variant_from_uri return None on explicit path miss."""
        pkg = get_package_from_repository("versioned", "3.0", self.py_packages_path)
        var_pkg = get_package_from_repository("variants_py", "2.0", self.py_packages_path)
        variant = var_pkg.get_variant(0)

        # Explicit paths not containing the URI return None
        self.assertIsNone(get_package_from_uri(pkg.uri, paths=[self.solver_packages_path]))
        self.assertIsNone(get_variant_from_uri(variant.uri, paths=[self.solver_packages_path]))

    @unittest.expectedFailure
    def test_get_package_and_variant_from_uri_fallback(self) -> None:
        """Test get_package_from_uri and get_variant_from_uri fallback when paths=None.

        Expected failure: src/rez/packages.py:803,857 use os.path.split(uri)
        (a 2-tuple) instead of uri.split(os.path.sep), so the fallback returns None.
        """
        pkg = get_package_from_repository("versioned", "3.0", self.py_packages_path)
        combined_pkg = get_package_from_repository("multi", "1.0", self.yaml_packages_path)
        var_pkg = get_package_from_repository("variants_py", "2.0", self.py_packages_path)
        variant = var_pkg.get_variant(0)
        combined_variant = combined_pkg.get_variant(0)

        # Fallback path when paths=None and packages_path does not contain the repo
        self.update_settings({"packages_path": [self.solver_packages_path]})
        # Non-combined URI ('<' not in uri)
        self.assertEqual(get_package_from_uri(pkg.uri), pkg)
        self.assertEqual(get_variant_from_uri(variant.uri), variant)
        # Combined URI ('<' in uri)
        self.assertEqual(get_package_from_uri(combined_pkg.uri), combined_pkg)
        self.assertEqual(get_variant_from_uri(f"{combined_pkg.uri}[0]"), combined_variant)

    def test_get_last_release_time(self) -> None:
        """get_last_release_time returns 0 if unknown/missing or max timestamp across repos."""
        # Non-existent family -> 0
        self.assertEqual(get_last_release_time("nonexistent_pkg"), 0)

        # Repo returning 0 short-circuits to 0
        repo1 = MagicMock()
        repo1.get_package_family.return_value = MagicMock()
        repo1.get_last_release_time.return_value = 0

        repo2 = MagicMock()
        repo2.get_package_family.return_value = MagicMock()
        repo2.get_last_release_time.return_value = 2000

        with patch.object(package_repository_manager, "get_repository", side_effect=[repo1, repo2]):
            self.assertEqual(get_last_release_time("foo", paths=["/p1", "/p2"]), 0)

        # Non-zero timestamps return maximum
        repo1.get_last_release_time.return_value = 1000
        with patch.object(package_repository_manager, "get_repository", side_effect=[repo1, repo2]):
            self.assertEqual(get_last_release_time("foo", paths=["/p1", "/p2"]), 2000)

    def test_get_completions(self) -> None:
        """get_completions handles prefixes, family_only, operators (!/~), and delimiters."""
        # family_only=True with operator or delimiter returns empty set
        self.assertEqual(get_completions("~py", family_only=True), set())
        self.assertEqual(get_completions("!py", family_only=True), set())
        self.assertEqual(get_completions("python-2", family_only=True), set())

        # family_only=True with plain prefix returns matching family names
        fams = get_completions("pyt", family_only=True)
        self.assertEqual(fams, {"python"})

        # Operator prefix with family_only=False prepends operator to completions
        ops = get_completions("~python-2.6")
        self.assertEqual(ops, {"~python-2.6.0", "~python-2.6.8"})

        excl = get_completions("!python-2.7")
        self.assertEqual(excl, {"!python-2.7.0"})

    def test_get_latest_package_error_and_from_string(self) -> None:
        """get_latest_package raises PackageFamilyNotFoundError when error=True."""
        with self.assertRaises(PackageFamilyNotFoundError):
            get_latest_package("nonexistent_pkg", error=True)

        self.assertIsNone(get_latest_package("nonexistent_pkg", error=False))

        latest = get_latest_package_from_string("python-2.6+<2.7")
        self.assertEqual(latest.qualified_name, "python-2.6.8")

        with self.assertRaises(PackageFamilyNotFoundError):
            get_latest_package_from_string("nonexistent_pkg-1+", error=True)

    def test_check_class_raises_resource_error(self) -> None:
        """Instantiating Package/PackageFamily/Variant with wrong resource type raises ResourceError."""
        pkg = get_package("versioned", "3.0")
        with self.assertRaises(ResourceError):
            PackageFamily(pkg.resource)
        with self.assertRaises(ResourceError):
            Package(pkg.parent.resource)
        with self.assertRaises(ResourceError):
            Variant(pkg.resource)

    def test_late_binding_schema_validation_none_vs_invalid(self) -> None:
        """Late-bound schema-validated attr returns None cleanly on None and raises SchemaError on invalid value."""
        def _return_none():
            return None

        sc_none = SourceCode(func=_return_none)
        sc_none.late_binding = True
        pkg_none = create_package(
            "late_none",
            {
                "version": "1.0",
                "requires": sc_none,
            },
        )

        def _return_invalid():
            return 123

        sc_invalid = SourceCode(func=_return_invalid)
        sc_invalid.late_binding = True
        pkg_invalid = create_package(
            "late_invalid",
            {
                "version": "1.0",
                "requires": sc_invalid,
            },
        )

        with patch.dict(PackageBaseResourceWrapper.late_bind_schemas, {"requires": Schema([str])}):
            self.assertIsNone(pkg_none.requires)
            self.assertIsNone(pkg_none.requires)
            with self.assertRaises(SchemaError):
                _ = pkg_invalid.requires


if __name__ == "__main__":
    unittest.main()
