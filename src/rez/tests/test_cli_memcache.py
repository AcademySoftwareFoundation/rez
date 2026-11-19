# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Unit tests for rez.cli.memcache.
"""
from __future__ import annotations

import argparse
import contextlib
import io
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from rez.cli import memcache as cli_memcache
from rez.cli._main import _add_common_args
from rez.config import config
from rez.tests.util import TestBase


class _StopPolling(Exception):
    """Sentinel exception to break out of poll()'s infinite loop."""


class _DummyPackage:
    def __init__(self, qualified_name: str, data: dict) -> None:
        self.qualified_name = qualified_name
        self._data = data
        self.data_accessed = False

    @property
    def data(self) -> dict:
        self.data_accessed = True
        return self._data


class TestCliMemcache(TestBase):
    def _build_parser(self, completions: bool = False) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(prog="rez-memcache")
        cli_memcache.setup_parser(parser, completions=completions)
        _add_common_args(parser)
        return parser

    def test_setup_parser_defaults(self) -> None:
        parser = self._build_parser()
        opts = parser.parse_args([])
        self.assertFalse(opts.flush)
        self.assertFalse(opts.stats)
        self.assertFalse(opts.reset_stats)
        self.assertFalse(opts.poll)
        self.assertEqual(opts.interval, 1.0)
        self.assertFalse(opts.warm)

    def test_setup_parser_flags(self) -> None:
        parser = self._build_parser(completions=True)
        opts = parser.parse_args([
            "--flush",
            "--stats",
            "--reset-stats",
            "--poll",
            "--interval",
            "2.5",
            "--warm",
        ])
        self.assertTrue(opts.flush)
        self.assertTrue(opts.stats)
        self.assertTrue(opts.reset_stats)
        self.assertTrue(opts.poll)
        self.assertEqual(opts.interval, 2.5)
        self.assertTrue(opts.warm)

    def test_command_memcache_disabled(self) -> None:
        self.update_settings({"memcached_uri": []})
        parser = self._build_parser()
        opts = parser.parse_args([])

        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as cm:
                cli_memcache.command(opts, parser)

        self.assertEqual(cm.exception.code, 1)
        self.assertIn("memcaching is not enabled.", stderr.getvalue())

    def test_command_poll(self) -> None:
        self.update_settings({"memcached_uri": ["127.0.0.1:11211"], "debug_memcache": False})
        parser = self._build_parser()
        opts = parser.parse_args(["--poll", "--interval", "0.5"])
        mock_client = MagicMock()

        with patch("rez.utils.memcached.Client", return_value=mock_client) as client_cls:
            with patch("rez.cli.memcache.poll") as mock_poll:
                cli_memcache.command(opts, parser)

        client_cls.assert_called_once_with(servers=["127.0.0.1:11211"], debug=False)
        mock_poll.assert_called_once_with(mock_client, 0.5)

    def test_command_flush(self) -> None:
        self.update_settings({"memcached_uri": ["127.0.0.1:11211"], "debug_memcache": False})
        parser = self._build_parser()
        opts = parser.parse_args(["--flush"])
        mock_client = MagicMock()

        stdout = io.StringIO()
        with patch("rez.utils.memcached.Client", return_value=mock_client):
            with contextlib.redirect_stdout(stdout):
                cli_memcache.command(opts, parser)

        mock_client.flush.assert_called_once_with(hard=True)
        self.assertIn("memcached servers are flushed.", stdout.getvalue())

    def test_command_reset_stats(self) -> None:
        self.update_settings({"memcached_uri": ["127.0.0.1:11211"], "debug_memcache": False})
        parser = self._build_parser()
        opts = parser.parse_args(["--reset-stats"])
        mock_client = MagicMock()

        stdout = io.StringIO()
        with patch("rez.utils.memcached.Client", return_value=mock_client):
            with contextlib.redirect_stdout(stdout):
                cli_memcache.command(opts, parser)

        mock_client.reset_stats.assert_called_once_with()
        self.assertIn("memcached servers are stat reset.", stdout.getvalue())

    def test_command_warm_verbose_and_dedup(self) -> None:
        self.update_settings({
            "memcached_uri": ["127.0.0.1:11211"],
            "debug_memcache": False,
        })
        parser = self._build_parser()
        mock_client = MagicMock()

        fam_foo_1 = SimpleNamespace(name="foo")
        fam_foo_2 = SimpleNamespace(name="foo")
        fam_bar = SimpleNamespace(name="bar")
        pkg_foo = _DummyPackage("foo-1.0", {"name": "foo"})
        pkg_bar = _DummyPackage("bar-2.0", {"name": "bar"})

        def fake_iter_packages(family_name, paths=None):
            if family_name == "foo":
                return [pkg_foo]
            if family_name == "bar":
                return [pkg_bar]
            return []

        stdout = io.StringIO()
        with patch("rez.utils.memcached.Client", return_value=mock_client):
            with patch("rez.packages.iter_package_families", return_value=[fam_foo_1, fam_foo_2, fam_bar]) as it_fam:
                with patch("rez.packages.iter_packages", side_effect=fake_iter_packages) as it_pkg:
                    with contextlib.redirect_stdout(stdout):
                        cli_memcache.command(parser.parse_args(["--warm", "-v"]), parser)

        it_fam.assert_called_once_with(paths=config.nonlocal_packages_path)
        self.assertEqual(it_pkg.call_count, 2)
        self.assertTrue(pkg_foo.data_accessed)
        self.assertTrue(pkg_bar.data_accessed)
        out = stdout.getvalue()
        self.assertIn("warming: foo-1.0", out)
        self.assertIn("warming: bar-2.0", out)
        self.assertIn("memcached servers are warmed.", out)

    def test_command_warm_quiet(self) -> None:
        self.update_settings({
            "memcached_uri": ["127.0.0.1:11211"],
            "debug_memcache": False,
        })
        parser = self._build_parser()
        mock_client = MagicMock()
        pkg_foo = _DummyPackage("foo-1.0", {"name": "foo"})

        stdout = io.StringIO()
        with patch("rez.utils.memcached.Client", return_value=mock_client):
            with patch("rez.packages.iter_package_families", return_value=[SimpleNamespace(name="foo")]):
                with patch("rez.packages.iter_packages", return_value=[pkg_foo]):
                    with contextlib.redirect_stdout(stdout):
                        cli_memcache.command(parser.parse_args(["--warm"]), parser)

        self.assertTrue(pkg_foo.data_accessed)
        out = stdout.getvalue()
        self.assertNotIn("warming:", out)
        self.assertIn("memcached servers are warmed.", out)

    def test_command_stats_yaml(self) -> None:
        self.update_settings({"memcached_uri": ["127.0.0.1:11211"], "debug_memcache": False})
        parser = self._build_parser()
        mock_client = MagicMock()
        mock_client.get_stats.return_value = [("127.0.0.1:11211 (1)", {"uptime": "120", "get_hits": "5"})]

        stdout = io.StringIO()
        with patch("rez.utils.memcached.Client", return_value=mock_client):
            with contextlib.redirect_stdout(stdout):
                cli_memcache.command(parser.parse_args(["--stats"]), parser)

        out = stdout.getvalue()
        self.assertIn("127.0.0.1:11211 (1)", out)
        self.assertIn("uptime", out)

    def test_command_stats_no_response(self) -> None:
        self.update_settings({"memcached_uri": ["127.0.0.1:11211"], "debug_memcache": False})
        parser = self._build_parser()
        mock_client = MagicMock()
        mock_client.get_stats.return_value = []

        stderr = io.StringIO()
        with patch("rez.utils.memcached.Client", return_value=mock_client):
            with contextlib.redirect_stderr(stderr):
                with self.assertRaises(SystemExit) as cm:
                    cli_memcache.command(parser.parse_args(["--stats"]), parser)

        self.assertEqual(cm.exception.code, 1)
        self.assertIn("memcached servers are not responding.", stderr.getvalue())

    def test_command_summary_no_response(self) -> None:
        self.update_settings({"memcached_uri": ["127.0.0.1:11211"], "debug_memcache": False})
        parser = self._build_parser()
        mock_client = MagicMock()
        mock_client.get_stats.return_value = []

        stderr = io.StringIO()
        with patch("rez.utils.memcached.Client", return_value=mock_client):
            with contextlib.redirect_stderr(stderr):
                with self.assertRaises(SystemExit) as cm:
                    cli_memcache.command(parser.parse_args([]), parser)

        self.assertEqual(cm.exception.code, 1)
        self.assertIn("memcached servers are not responding.", stderr.getvalue())

    def test_command_summary_table(self) -> None:
        self.update_settings({"memcached_uri": ["127.0.0.1:11211"], "debug_memcache": False})
        parser = self._build_parser()
        mock_client = MagicMock()
        mock_client.get_stats.return_value = [
            (
                "127.0.0.1:11211 (1)",
                {
                    "uptime": "3661",
                    "get_hits": "75",
                    "get_misses": "25",
                    "limit_maxbytes": str(1024 * 1024),
                    "bytes": str(512 * 1024),
                },
            ),
            (
                "127.0.0.2:11211 (2)",
                {
                    "uptime": "0",
                    "get_hits": "0",
                    "get_misses": "0",
                    "limit_maxbytes": "0",
                    "bytes": "0",
                },
            ),
        ]

        stdout = io.StringIO()
        with patch("rez.utils.memcached.Client", return_value=mock_client):
            with contextlib.redirect_stdout(stdout):
                cli_memcache.command(parser.parse_args([]), parser)

        out = stdout.getvalue()
        self.assertIn("CACHE SERVER", out)
        self.assertIn("127.0.0.1:11211", out)
        self.assertIn("75%", out)
        self.assertIn("(50%)", out)
        self.assertIn("127.0.0.2:11211", out)
        self.assertIn("0%", out)

    def test_poll_prints_rates_and_test_timings(self) -> None:
        mock_client = MagicMock()
        mock_client.get_stats.side_effect = [
            [
                ("127.0.0.1:11211 (1)", {"cmd_get": "100", "cmd_set": "50", "curr_connections": "2"}),
                ("127.0.0.2:11211 (2)", {}),
            ],
            [
                ("127.0.0.1:11211 (1)", {"cmd_get": "120", "cmd_set": "60", "curr_connections": "3"}),
                ("127.0.0.2:11211 (2)", {"cmd_get": "10", "cmd_set": "5", "curr_connections": "1"}),
            ],
        ]
        probe_client = MagicMock()

        timestamps = iter([0.0, 2.0, 2.1, 2.2, 2.4])
        sleep_calls = []

        def fake_sleep(secs: float) -> None:
            sleep_calls.append(secs)
            if len(sleep_calls) >= 2:
                raise _StopPolling

        stdout = io.StringIO()
        with patch("rez.utils.memcached.Client", return_value=probe_client) as client_cls:
            with patch("time.time", side_effect=timestamps):
                with patch("time.sleep", side_effect=fake_sleep):
                    with contextlib.redirect_stdout(stdout):
                        with self.assertRaises(_StopPolling):
                            cli_memcache.poll(mock_client, 0.25)

        self.assertEqual(sleep_calls, [0.25, 0.25])
        client_cls.assert_called_once_with(["127.0.0.1:11211"], debug=True)
        probe_client.set.assert_called_once_with("__TEST__", 1)
        probe_client.get.assert_called_once_with("__TEST__")

        out = stdout.getvalue()
        self.assertIn("SERVER", out)
        self.assertIn("TEST_GET", out)
        self.assertIn("127.0.0.1:11211 (1)", out)
        self.assertIn("10", out)
        self.assertIn("5", out)
        self.assertNotIn("127.0.0.2:11211 (2)", out)
