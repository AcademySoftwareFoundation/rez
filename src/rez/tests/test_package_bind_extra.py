# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Additional unit tests for rez.package_bind covering bind module discovery,
verbose fuzzy matching, bind_package execution, dependency traversal, and error handling.
"""
import contextlib
import io
import os
import re
import tempfile
import textwrap
from unittest import mock

from rez import package_bind
from rez.exceptions import RezBindError
from rez.tests.util import TempdirMixin, TestBase
from rez.version import VersionRange


class TestPackageBindExtra(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        TempdirMixin.setUpClass()

    @classmethod
    def tearDownClass(cls) -> None:
        TempdirMixin.tearDownClass()
        super().tearDownClass()

    def setUp(self) -> None:
        super().setUp()
        self.test_dir = tempfile.mkdtemp(dir=self.root)
        self.bind_dir = os.path.join(self.test_dir, "bind")
        self.install_dir = os.path.join(self.test_dir, "packages")
        os.makedirs(self.bind_dir)
        os.makedirs(self.install_dir)
        self.update_settings({
            "bind_module_path": [self.bind_dir],
            "local_packages_path": self.install_dir,
        })

    def _write_bind_module(self, name: str, source: str) -> str:
        filepath = os.path.join(self.bind_dir, f"{name}.py")
        with open(filepath, "w") as f:
            f.write(textwrap.dedent(source))
        return filepath

    def test_get_bind_modules_verbose_and_invalid_path(self) -> None:
        """Test get_bind_modules with verbose=True, non-existent paths, and non-module entries."""
        self._write_bind_module("custom_mod", "def bind(path, **kwargs): return []\n")
        self._write_bind_module("_private", "def bind(path, **kwargs): return []\n")
        with open(os.path.join(self.bind_dir, "notes.txt"), "w") as f:
            f.write("not a python module\n")
        os.makedirs(os.path.join(self.bind_dir, "subdir.py"))

        missing_dir = os.path.join(self.test_dir, "does_not_exist")
        self.update_settings({"bind_module_path": [missing_dir, self.bind_dir]})

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            modules = package_bind.get_bind_modules(verbose=True)

        output = buf.getvalue()
        self.assertIn(f"searching {missing_dir}...", output)
        self.assertIn(f"searching {self.bind_dir}...", output)
        self.assertIn("custom_mod", modules)
        self.assertNotIn("_private", modules)
        self.assertNotIn("notes", modules)
        self.assertNotIn("subdir", modules)

    def test_find_bind_module_not_found_quiet_and_verbose(self) -> None:
        """Test find_bind_module when missing with verbose=False and verbose=True (with/without close matches)."""
        buf_quiet = io.StringIO()
        with contextlib.redirect_stdout(buf_quiet):
            result_quiet = package_bind.find_bind_module("nonexistent_xyz_pkg", verbose=False)
        self.assertIsNone(result_quiet)
        self.assertEqual(buf_quiet.getvalue(), "")

        buf_close = io.StringIO()
        with contextlib.redirect_stdout(buf_close):
            result_close = package_bind.find_bind_module("pythn", verbose=True)
        self.assertIsNone(result_close)
        close_out = buf_close.getvalue()
        self.assertIn("'pythn' not found. Close matches:", close_out)
        self.assertIn("python", close_out)

        buf_none = io.StringIO()
        with contextlib.redirect_stdout(buf_none):
            result_none = package_bind.find_bind_module("zzzzzzzzzz_no_match", verbose=True)
        self.assertIsNone(result_none)
        self.assertIn("No matches.", buf_none.getvalue())

    def test_bind_package_missing_module_raises(self) -> None:
        """Test bind_package raises RezBindError when the primary bind module does not exist."""
        with self.assertRaisesRegex(RezBindError, "Bind module not found for 'nonexistent_bind_pkg'"):
            package_bind.bind_package("nonexistent_bind_pkg", path=self.install_dir, quiet=True)

    def test_bind_package_missing_bind_func_raises(self) -> None:
        """Test bind_package raises RezBindError when a bind module lacks a bind() function."""
        bindfile = self._write_bind_module("no_bind_fn", "VALUE = 1\n")
        with self.assertRaisesRegex(RezBindError, f"'bind' function missing in {re.escape(bindfile)}"):
            package_bind.bind_package("no_bind_fn", path=self.install_dir, quiet=True)

    def test_bind_package_with_setup_parser_and_verbose_output(self) -> None:
        """Test bind_package with setup_parser, bind_args, and quiet=False summary output."""
        self._write_bind_module(
            "with_parser",
            """
            from rez.package_maker import make_package
            from rez.version import Version

            def setup_parser(parser):
                parser.add_argument("--tag", default="alpha")

            def bind(path, version_range=None, opts=None, parser=None):
                with make_package("with_parser", path) as pkg:
                    pkg.version = Version("1.0")
                    pkg.description = opts.tag
                return pkg.installed_variants
            """,
        )

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            variants = package_bind.bind_package(
                "with_parser",
                path=self.install_dir,
                bind_args=["--tag", "beta"],
                quiet=False,
            )

        self.assertEqual(len(variants), 1)
        self.assertEqual(variants[0].name, "with_parser")
        self.assertEqual(variants[0].parent.description, "beta")

        output = buf.getvalue()
        self.assertIn(f"creating package 'with_parser' in {self.install_dir}...", output)
        self.assertIn("The following packages were installed:", output)
        self.assertIn("PACKAGE", output)
        self.assertIn("URI", output)
        self.assertIn("with_parser", output)

    def test_bind_package_default_local_packages_path(self) -> None:
        """Test bind_package defaults to config.local_packages_path when path=None and setup_parser is absent."""
        self._write_bind_module(
            "default_dest",
            """
            from rez.package_maker import make_package
            from rez.version import Version

            def bind(path, version_range=None, opts=None, parser=None):
                with make_package("default_dest", path) as pkg:
                    pkg.version = Version("2.0")
                return pkg.installed_variants
            """,
        )

        variants = package_bind.bind_package("default_dest", path=None, quiet=True)
        self.assertEqual(len(variants), 1)
        self.assertTrue(os.path.isdir(os.path.join(self.install_dir, "default_dest", "2.0")))

    def test_bind_package_empty_variants_quiet_false(self) -> None:
        """Test bind_package does not print installed summary when bind() returns no variants."""
        self._write_bind_module(
            "empty_mod",
            """
            def bind(path, version_range=None, opts=None, parser=None):
                return []
            """,
        )

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            variants = package_bind.bind_package("empty_mod", path=self.install_dir, quiet=False)

        self.assertEqual(variants, [])
        self.assertNotIn("The following packages were installed:", buf.getvalue())

    def test_bind_package_dependencies_and_conflicts(self) -> None:
        """Test bind_package binds non-conflict dependencies and skips conflict requirements."""
        self._write_bind_module(
            "primary_pkg",
            """
            from rez.package_maker import make_package
            from rez.version import Version

            def setup_parser(parser):
                parser.add_argument("--primary-only", action="store_true")

            def bind(path, version_range=None, opts=None, parser=None):
                assert version_range is not None
                assert opts.primary_only is True
                with make_package("primary_pkg", path) as pkg:
                    pkg.version = Version("1.0")
                    pkg.requires = ["dep_ok-1+", "!conflict_pkg"]
                return pkg.installed_variants
            """,
        )
        self._write_bind_module(
            "dep_ok",
            """
            from rez.package_maker import make_package
            from rez.version import Version

            def bind(path, version_range=None, opts=None, parser=None):
                assert version_range is None
                with make_package("dep_ok", path) as pkg:
                    pkg.version = Version("1.2")
                return pkg.installed_variants
            """,
        )
        self._write_bind_module(
            "conflict_pkg",
            """
            def bind(path, version_range=None, opts=None, parser=None):
                raise AssertionError("conflict_pkg should not be bound")
            """,
        )

        variants = package_bind.bind_package(
            "primary_pkg",
            path=self.install_dir,
            version_range=VersionRange("1.0"),
            no_deps=False,
            bind_args=["--primary-only"],
            quiet=True,
        )

        bound_names = sorted(v.name for v in variants)
        self.assertEqual(bound_names, ["dep_ok", "primary_pkg"])

    def test_bind_package_no_deps_skips_dependencies(self) -> None:
        """Test bind_package with no_deps=True does not bind package dependencies."""
        self._write_bind_module(
            "primary_nodeps",
            """
            from rez.package_maker import make_package
            from rez.version import Version

            def bind(path, version_range=None, opts=None, parser=None):
                with make_package("primary_nodeps", path) as pkg:
                    pkg.version = Version("1.0")
                    pkg.requires = ["dep_should_skip"]
                return pkg.installed_variants
            """,
        )
        self._write_bind_module(
            "dep_should_skip",
            """
            def bind(path, version_range=None, opts=None, parser=None):
                raise AssertionError("dependency should not be bound when no_deps=True")
            """,
        )

        variants = package_bind.bind_package(
            "primary_nodeps",
            path=self.install_dir,
            no_deps=True,
            quiet=True,
        )
        self.assertEqual([v.name for v in variants], ["primary_nodeps"])

    def test_print_package_list_sorts_and_deduplicates(self) -> None:
        """Test _print_package_list deduplicates variants per package and sorts by package name."""
        pkg_z = mock.MagicMock()
        pkg_z.name = "zeta"
        pkg_z.uri = "/pkgs/zeta/1.0"

        pkg_a = mock.MagicMock()
        pkg_a.name = "alpha"
        pkg_a.uri = "/pkgs/alpha/1.0"

        v1 = mock.MagicMock()
        v1.parent = pkg_z
        v2 = mock.MagicMock()
        v2.parent = pkg_a
        v3 = mock.MagicMock()
        v3.parent = pkg_a

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            package_bind._print_package_list([v1, v2, v3])

        lines = [line.strip() for line in buf.getvalue().strip().splitlines()]
        self.assertEqual(len(lines), 4)
        self.assertTrue(lines[0].startswith("PACKAGE"))
        self.assertTrue(lines[1].startswith("-------"))
        self.assertTrue(lines[2].startswith("alpha"))
        self.assertTrue(lines[3].startswith("zeta"))
