# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Unit tests for ``rez.cli.pkg-cache`` (``rez-pkg-cache``).
"""
import argparse
import contextlib
import importlib
import io
import os
import types
import unittest
from unittest.mock import MagicMock, patch

from rez.cli._main import _add_common_args
from rez.package_cache import PackageCache
from rez.tests.util import TempdirMixin, TestBase


pkg_cache_cli = importlib.import_module("rez.cli.pkg-cache")


def _make_variant(name="foo", qualified_name="foo-1.0.0", uri="foo-1.0.0[]", root="/pkgs/foo/1.0.0"):
    variant = MagicMock()
    variant.name = name
    variant.parent.qualified_name = qualified_name
    variant.uri = uri
    variant.root = root
    return variant


class TestCliPkgCache(TestBase, TempdirMixin):
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
        self.cache_dir = os.path.join(self.root, "pkg_cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        self.parser = argparse.ArgumentParser(prog="rez-pkg-cache")
        pkg_cache_cli.setup_parser(self.parser)
        _add_common_args(self.parser)

    def _run_cli(self, args):
        opts = self.parser.parse_args(args)
        pkg_cache_cli.command(opts, self.parser)
        return opts

    def test_setup_parser_defaults_and_options(self) -> None:
        opts = self.parser.parse_args([])
        self.assertIsNone(opts.add_variants)
        self.assertFalse(opts.logs)
        self.assertIsNone(opts.remove_variants)
        self.assertFalse(opts.clean)
        self.assertFalse(opts.daemon)
        self.assertIsNone(opts.pkg_cache_mode)
        self.assertEqual(opts.columns, ["status", "package", "variant_uri", "cache_path"])
        self.assertFalse(opts.force)
        self.assertIsNone(opts.DIR)

        opts_custom = self.parser.parse_args([
            "--add-variants", "foo-1.0[]", "bar-2.0[]",
            "--pkg-cache-mode", "sync",
            "--columns", "status", "orig_path",
            "--force",
            self.cache_dir,
        ])
        self.assertEqual(opts_custom.add_variants, ["foo-1.0[]", "bar-2.0[]"])
        self.assertEqual(opts_custom.pkg_cache_mode, "sync")
        self.assertEqual(opts_custom.columns, ["status", "orig_path"])
        self.assertTrue(opts_custom.force)
        self.assertEqual(opts_custom.DIR, self.cache_dir)

    def test_missing_cache_dir_raises_parser_error(self) -> None:
        self.update_settings({"cache_packages_path": None})
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as cm:
                self._run_cli([])
        self.assertEqual(cm.exception.code, 2)
        self.assertIn("cache_packages_path", stderr.getvalue())

    def test_uses_configured_cache_packages_path_when_dir_omitted(self) -> None:
        self.update_settings({"cache_packages_path": self.cache_dir})
        with patch.object(PackageCache, "clean") as mock_clean:
            self._run_cli(["--clean"])
        mock_clean.assert_called_once_with()

    def test_daemon_mode(self) -> None:
        with patch.object(PackageCache, "run_daemon") as mock_daemon:
            self._run_cli(["--daemon", self.cache_dir])
        mock_daemon.assert_called_once_with()

    def test_clean_mode(self) -> None:
        with patch.object(PackageCache, "clean") as mock_clean:
            self._run_cli(["--clean", self.cache_dir])
        mock_clean.assert_called_once_with()

    def test_logs_mode(self) -> None:
        with patch("rez.utils.logging_.view_file_logs") as mock_view:
            self._run_cli(["--logs", self.cache_dir])
        mock_view.assert_called_once()
        args, kwargs = mock_view.call_args
        self.assertTrue(args[0].endswith("*.log"))
        self.assertIn(self.cache_dir, args[0])
        self.assertEqual(kwargs, {"loglevel_index": 4})

    def test_add_variants_missing_variant_exits(self) -> None:
        stderr = io.StringIO()
        with patch("rez.packages.get_variant_from_uri", return_value=None):
            with contextlib.redirect_stderr(stderr):
                with self.assertRaises(SystemExit) as cm:
                    self._run_cli([self.cache_dir, "-a", "missing-1.0[]"])
        self.assertEqual(cm.exception.code, 1)
        self.assertIn("No such variant: missing-1.0[]", stderr.getvalue())

    def test_add_variants_modes_and_statuses(self) -> None:
        variant = _make_variant()

        cases = [
            # (pkg_cache_mode, config_async, expected_wait, status, log_fn, expected_msg)
            (
                "async", False, False, PackageCache.VARIANT_CREATED,
                "print_info", "Successfully cached to: %s",
            ),
            (
                "sync", True, True, PackageCache.VARIANT_FOUND,
                "print_info", "Already exists: %s",
            ),
            (
                None, True, False, PackageCache.VARIANT_COPYING,
                "print_warning", "Another process is currently copying to: %s",
            ),
            (
                None, False, True, PackageCache.VARIANT_CREATED,
                "print_info", "Successfully cached to: %s",
            ),
        ]

        for mode, cfg_async, expected_wait, status, log_fn, expected_msg in cases:
            with self.subTest(mode=mode, cfg_async=cfg_async, status=status):
                self.update_settings({"package_cache_async": cfg_async})
                args = ["-a", "foo-1.0.0[]", "-f"]
                if mode is not None:
                    args.extend(["--pkg-cache-mode", mode])
                args.append(self.cache_dir)

                with patch("rez.packages.get_variant_from_uri", return_value=variant), \
                        patch.object(PackageCache, "add_variant", return_value=("/cache/foo", status)) as mock_add, \
                        patch(f"rez.utils.logging_.{log_fn}") as mock_log:
                    self._run_cli(args)

                mock_add.assert_called_once_with(variant, force=True, wait_for_copying=expected_wait)
                mock_log.assert_any_call(expected_msg, "/cache/foo")

    def test_add_variants_skipped_logs_disk_usage_warning(self) -> None:
        variant = _make_variant()
        self.update_settings({
            "cache_packages_path": self.cache_dir,
            "package_cache_async": False,
            "package_cache_space_buffer": 100 * 1024**2,
        })
        fake_usage = types.SimpleNamespace(free=50 * 1024**2)

        with patch("rez.packages.get_variant_from_uri", return_value=variant), \
                patch.object(PackageCache, "add_variant", return_value=(None, PackageCache.VARIANT_SKIPPED)), \
                patch("shutil.disk_usage", return_value=fake_usage) as mock_du, \
                patch("rez.utils.logging_.print_warning") as mock_warn:
            self._run_cli([self.cache_dir, "-a", "foo-1.0.0[]"])

        mock_du.assert_called_once_with(self.cache_dir)
        mock_warn.assert_called_once()
        msg = mock_warn.call_args[0][0]
        self.assertIn("50.00MB", msg)
        self.assertIn("100.00MB", msg)

    @unittest.expectedFailure
    def test_add_variants_skipped_logs_disk_usage_warning_uses_cli_dir(self) -> None:
        """src/rez/cli/pkg-cache.py:103 reads config.cache_packages_path instead of pkgcache.path."""
        variant = _make_variant()
        self.update_settings({
            "cache_packages_path": None,
            "package_cache_async": False,
            "package_cache_space_buffer": 100 * 1024**2,
        })
        fake_usage = types.SimpleNamespace(free=50 * 1024**2)

        with patch("rez.packages.get_variant_from_uri", return_value=variant), \
                patch.object(PackageCache, "add_variant", return_value=(None, PackageCache.VARIANT_SKIPPED)), \
                patch("shutil.disk_usage", return_value=fake_usage) as mock_du, \
                patch("rez.utils.logging_.print_warning") as mock_warn:
            self._run_cli([self.cache_dir, "-a", "foo-1.0.0[]"])

        mock_du.assert_called_once_with(self.cache_dir)
        mock_warn.assert_called_once()

    def test_remove_variants_missing_variant_exits(self) -> None:
        stderr = io.StringIO()
        with patch("rez.packages.get_variant_from_uri", return_value=None):
            with contextlib.redirect_stderr(stderr):
                with self.assertRaises(SystemExit) as cm:
                    self._run_cli([self.cache_dir, "-r", "missing-1.0[]"])
        self.assertEqual(cm.exception.code, 1)
        self.assertIn("No such variant: missing-1.0[]", stderr.getvalue())

    def test_remove_variants_statuses(self) -> None:
        variant = _make_variant()
        cases = [
            (PackageCache.VARIANT_NOT_FOUND, "print_error", "No such variant found in cache"),
            (PackageCache.VARIANT_COPYING, "print_warning", "Another process is currently caching this variant"),
            (PackageCache.VARIANT_REMOVED, "print_info", "Variant successfully removed"),
        ]
        for status, log_fn, expected_msg in cases:
            with self.subTest(status=status):
                with patch("rez.packages.get_variant_from_uri", return_value=variant), \
                        patch.object(PackageCache, "remove_variant", return_value=status) as mock_rm, \
                        patch(f"rez.utils.logging_.{log_fn}") as mock_log:
                    self._run_cli([self.cache_dir, "-r", "foo-1.0.0[]"])

                mock_rm.assert_called_once_with(variant)
                mock_log.assert_any_call(expected_msg)

    def test_list_variants_empty_exits_zero(self) -> None:
        stderr = io.StringIO()
        with patch.object(PackageCache, "get_variants", return_value=[]):
            with patch("sys.stdout.isatty", return_value=False):
                with contextlib.redirect_stderr(stderr):
                    with self.assertRaises(SystemExit) as cm:
                        self._run_cli([self.cache_dir])
        self.assertEqual(cm.exception.code, 0)
        self.assertIn("No cached packages.", stderr.getvalue())

    def test_list_variants_non_tty_all_columns_and_sorting(self) -> None:
        v_pending = _make_variant("zeta", "zeta-1.0", "zeta-1.0[]", "/orig/zeta")
        v_stalled = _make_variant("beta", "beta-1.0", "beta-1.0[]", "/orig/beta")
        v_copying = _make_variant("alpha", "alpha-1.0", "alpha-1.0[]", "/orig/alpha")
        v_cached_b = _make_variant("bar", "bar-1.0", "bar-1.0[]", "/orig/bar")
        v_cached_a = _make_variant("aardvark", "aardvark-1.0", "aardvark-1.0[]", "/orig/aardvark")

        entries = [
            (v_pending, "", PackageCache.VARIANT_PENDING),
            (v_stalled, "/cache/beta", PackageCache.VARIANT_COPY_STALLED),
            (v_copying, "/cache/alpha", PackageCache.VARIANT_COPYING),
            (v_cached_b, "/cache/bar", PackageCache.VARIANT_FOUND),
            (v_cached_a, "/cache/aardvark", PackageCache.VARIANT_FOUND),
        ]

        with patch.object(PackageCache, "get_variants", return_value=entries), \
                patch("sys.stdout.isatty", return_value=False), \
                patch("rez.utils.formatting.print_colored_columns") as mock_pcc:
            self._run_cli([
                self.cache_dir,
                "-c", "status", "package", "variant_uri", "orig_path", "cache_path",
            ])

        mock_pcc.assert_called_once()
        rows = mock_pcc.call_args[0][1]
        self.assertEqual(len(rows), 5)
        # Sorted by status priority (cached=0, copying=1, stalled=2, pending=3), then variant.name
        self.assertEqual(rows[0][:5], ["cached", "aardvark-1.0", "aardvark-1.0[]", "/orig/aardvark", "/cache/aardvark"])
        self.assertEqual(rows[1][:5], ["cached", "bar-1.0", "bar-1.0[]", "/orig/bar", "/cache/bar"])
        self.assertEqual(rows[2][:5], ["copying", "alpha-1.0", "alpha-1.0[]", "/orig/alpha", "/cache/alpha"])
        self.assertEqual(rows[3][:5], ["stalled", "beta-1.0", "beta-1.0[]", "/orig/beta", "/cache/beta"])
        self.assertEqual(rows[4][:5], ["pending", "zeta-1.0", "zeta-1.0[]", "/orig/zeta", "-"])

    def test_list_variants_tty_prints_header_and_underlines(self) -> None:
        v_cached = _make_variant("foo", "foo-1.0", "foo-1.0[]", "/orig/foo")
        entries = [(v_cached, "/cache/foo", PackageCache.VARIANT_FOUND)]
        stdout = io.StringIO()

        with patch.object(PackageCache, "get_variants", return_value=entries), \
                patch.object(stdout, "isatty", return_value=True), \
                contextlib.redirect_stdout(stdout), \
                patch("rez.utils.formatting.print_colored_columns") as mock_pcc:
            self._run_cli([self.cache_dir])

        self.assertIn(f"Package cache at {self.cache_dir}:", stdout.getvalue())
        rows = mock_pcc.call_args[0][1]
        self.assertEqual(rows[0], ["status", "package", "variant uri", "cache path", None])
        self.assertEqual(rows[1], ["------", "-------", "-----------", "----------", None])
        self.assertEqual(rows[2][:4], ["cached", "foo-1.0", "foo-1.0[]", "/cache/foo"])
