# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
In-process unit tests for CLI modules: release, rm, _util, pkg-ignore,
build, _complete_util, test, and env.
"""
from __future__ import annotations

import argparse
import contextlib
import importlib
import io
import os
import select
import signal
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

from rez.tests.util import TestBase, TempdirMixin, restore_os_environ
from rez.utils.platform_ import platform_


def _make_parser(setup_fn, completions=False):
    parser = argparse.ArgumentParser(prog="rez-test")
    parser.add_argument("-v", "--verbose", action="count", default=0)
    setup_fn(parser, completions=completions)
    return parser


class TestCliRelease(TestBase):
    """Tests for rez.cli.release."""

    def setUp(self):
        super().setUp()
        import rez.cli.build as build_cli
        self._orig_pkg = build_cli._package
        build_cli._package = None

    def tearDown(self):
        import rez.cli.build as build_cli
        build_cli._package = self._orig_pkg
        super().tearDown()

    def test_setup_parser(self):
        from rez.cli.release import setup_parser

        with patch("rez.cli.build.get_current_developer_package", return_value=None), \
                patch("rez.build_system.get_valid_build_systems", return_value=[]):
            parser = _make_parser(setup_parser)
            opts = parser.parse_args([
                "-m", "rel msg", "--no-latest",
                "--ignore-existing-tag", "--skip-repo-errors", "--no-message",
            ])
        self.assertEqual(opts.message, "rel msg")
        self.assertTrue(opts.no_latest)
        self.assertTrue(opts.ignore_existing_tag)
        self.assertTrue(opts.skip_repo_errors)
        self.assertTrue(opts.no_message)

    def test_command_with_message_flag(self):
        from rez.cli.release import command, setup_parser

        mock_pkg = MagicMock()
        mock_vcs = MagicMock()
        mock_buildsys = MagicMock()
        mock_builder = MagicMock()

        with patch("rez.cli.build.get_current_developer_package", return_value=mock_pkg), \
                patch("rez.build_system.get_valid_build_systems", return_value=[]):
            parser = _make_parser(setup_parser)
            opts = parser.parse_args(["-m", "v1.0 release"])

        with patch("rez.cli.build.get_current_developer_package", return_value=mock_pkg), \
                patch("rez.release_vcs.create_release_vcs", return_value=mock_vcs), \
                patch("rez.build_system.create_build_system", return_value=mock_buildsys), \
                patch("rez.build_process.create_build_process", return_value=mock_builder) as mock_create_bp:
            command(opts, parser)

        self.assertTrue(mock_create_bp.call_args[1]["ensure_latest"])
        mock_builder.release.assert_called_once_with(
            release_message="v1.0 release",
            variants=None,
        )

        # --no-latest sets ensure_latest=False
        mock_builder.reset_mock()
        with patch("rez.cli.build.get_current_developer_package", return_value=mock_pkg), \
                patch("rez.build_system.get_valid_build_systems", return_value=[]):
            opts_nl = parser.parse_args(["-m", "v1.0 release", "--no-latest"])
        with patch("rez.cli.build.get_current_developer_package", return_value=mock_pkg), \
                patch("rez.release_vcs.create_release_vcs", return_value=mock_vcs), \
                patch("rez.build_system.create_build_system", return_value=mock_buildsys), \
                patch("rez.build_process.create_build_process", return_value=mock_builder) as mock_create_bp:
            command(opts_nl, parser)

        self.assertFalse(mock_create_bp.call_args[1]["ensure_latest"])

    def test_command_prompt_release_message_with_changelog(self):
        from rez.cli.release import command, setup_parser
        from rez.config import config
        from hashlib import sha1

        self.update_settings({"prompt_release_message": True, "editor": "true"})
        h = sha1(os.getcwd().encode("utf8")).hexdigest()
        filepath = os.path.join(config.tmpdir, "rez-release-message-%s.txt" % h)
        if os.path.exists(filepath):
            os.remove(filepath)
        mock_pkg = MagicMock()
        mock_builder = MagicMock()
        mock_builder.get_changelog.return_value = "commit 1: fix bug"

        with patch("rez.cli.build.get_current_developer_package", return_value=mock_pkg), \
                patch("rez.build_system.get_valid_build_systems", return_value=[]):
            parser = _make_parser(setup_parser)
            opts = parser.parse_args([])

        def fake_editor(cmd):
            filepath = cmd[1]
            with open(filepath, "r+") as f:
                content = f.read()
                f.seek(0)
                f.write("My release notes\n" + content)
                f.truncate()
            return 0

        with patch("rez.cli.build.get_current_developer_package", return_value=mock_pkg), \
                patch("rez.release_vcs.create_release_vcs", return_value=MagicMock()), \
                patch("rez.build_system.create_build_system", return_value=MagicMock()), \
                patch("rez.build_process.create_build_process", return_value=mock_builder), \
                patch("rez.cli.release.call", side_effect=fake_editor):
            command(opts, parser)

        mock_builder.release.assert_called_once_with(
            release_message="My release notes",
            variants=None,
        )

    def test_command_prompt_empty_message_abort_and_continue(self):
        from rez.cli.release import command, setup_parser

        self.update_settings({"prompt_release_message": True, "editor": "true"})
        mock_pkg = MagicMock()
        mock_builder = MagicMock()
        mock_builder.get_changelog.side_effect = RuntimeError("no changelog")

        with patch("rez.cli.build.get_current_developer_package", return_value=mock_pkg), \
                patch("rez.build_system.get_valid_build_systems", return_value=[]):
            parser = _make_parser(setup_parser)
            opts = parser.parse_args([])

        def fake_editor_empty(cmd):
            with open(cmd[1], "w") as f:
                f.write("<Enter your release notes here>\n")
            return 0

        # Abort path: invalid input 'x', then 'a'
        buf = io.StringIO()
        with patch("rez.cli.build.get_current_developer_package", return_value=mock_pkg), \
                patch("rez.release_vcs.create_release_vcs", return_value=MagicMock()), \
                patch("rez.build_system.create_build_system", return_value=MagicMock()), \
                patch("rez.build_process.create_build_process", return_value=mock_builder), \
                patch("rez.cli.release.call", side_effect=fake_editor_empty), \
                patch("builtins.input", side_effect=["x", "a"]), \
                contextlib.redirect_stdout(buf):
            with self.assertRaises(SystemExit) as cm:
                command(opts, parser)
        self.assertEqual(cm.exception.code, 1)
        self.assertIn("Release aborted.", buf.getvalue())

        # Continue path: 'c', and os.remove raises (swallowed)
        with patch("rez.cli.build.get_current_developer_package", return_value=mock_pkg), \
                patch("rez.release_vcs.create_release_vcs", return_value=MagicMock()), \
                patch("rez.build_system.create_build_system", return_value=MagicMock()), \
                patch("rez.build_process.create_build_process", return_value=mock_builder), \
                patch("rez.cli.release.call", side_effect=fake_editor_empty), \
                patch("builtins.input", return_value="c"), \
                patch("os.remove", side_effect=OSError("perm")):
            command(opts, parser)
        mock_builder.release.assert_called_with(release_message=None, variants=None)


class TestCliRm(TestBase):
    """Tests for rez.cli.rm."""

    def test_command_no_action_errors(self):
        from rez.cli.rm import command, setup_parser

        parser = _make_parser(setup_parser)
        opts = parser.parse_args([])
        with self.assertRaises(SystemExit) as cm:
            with contextlib.redirect_stderr(io.StringIO()):
                command(opts, parser)
        self.assertEqual(cm.exception.code, 2)

    def test_remove_package_paths(self):
        from rez.cli.rm import command, setup_parser

        parser = _make_parser(setup_parser)

        # --dry-run not supported with --package
        opts = parser.parse_args(["-p", "foo-1.0", "--dry-run", "/repo"])
        with self.assertRaises(SystemExit) as cm:
            with contextlib.redirect_stderr(io.StringIO()):
                command(opts, parser)
        self.assertEqual(cm.exception.code, 2)

        # Missing PATH
        opts = parser.parse_args(["-p", "foo-1.0"])
        with self.assertRaises(SystemExit) as cm:
            with contextlib.redirect_stderr(io.StringIO()):
                command(opts, parser)
        self.assertEqual(cm.exception.code, 2)

        # Found -> prints Package removed.
        opts = parser.parse_args(["-p", "foo-1.0", "/repo"])
        out = io.StringIO()
        with patch("rez.package_remove.remove_package", return_value=True) as mock_rm, \
                contextlib.redirect_stdout(out):
            command(opts, parser)
        self.assertIn("Package removed.", out.getvalue())
        mock_rm.assert_called_once()

        # Not found -> prints to stderr and exits 1
        err = io.StringIO()
        with patch("rez.package_remove.remove_package", return_value=False), \
                contextlib.redirect_stderr(err):
            with self.assertRaises(SystemExit) as cm:
                command(opts, parser)
        self.assertEqual(cm.exception.code, 1)
        self.assertIn("Package not found.", err.getvalue())

    def test_remove_package_family_paths(self):
        from rez.cli.rm import command, setup_parser
        from rez.exceptions import PackageRepositoryError

        parser = _make_parser(setup_parser)

        # --dry-run not supported
        opts = parser.parse_args(["-f", "foo", "--dry-run", "/repo"])
        with self.assertRaises(SystemExit) as cm:
            with contextlib.redirect_stderr(io.StringIO()):
                command(opts, parser)
        self.assertEqual(cm.exception.code, 2)

        # Missing PATH
        opts = parser.parse_args(["-f", "foo"])
        with self.assertRaises(SystemExit) as cm:
            with contextlib.redirect_stderr(io.StringIO()):
                command(opts, parser)
        self.assertEqual(cm.exception.code, 2)

        # Version provided -> error
        opts = parser.parse_args(["-f", "foo-1.0", "/repo"])
        with self.assertRaises(SystemExit) as cm:
            with contextlib.redirect_stderr(io.StringIO()):
                command(opts, parser)
        self.assertEqual(cm.exception.code, 2)

        # PackageRepositoryError -> stderr + exit 1
        opts = parser.parse_args(["-f", "foo", "/repo"])
        err = io.StringIO()
        with patch("rez.package_remove.remove_package_family", side_effect=PackageRepositoryError("not empty")), \
                contextlib.redirect_stderr(err):
            with self.assertRaises(SystemExit) as cm:
                command(opts, parser)
        self.assertEqual(cm.exception.code, 1)
        self.assertIn("not empty", err.getvalue())

        # Success
        out = io.StringIO()
        with patch("rez.package_remove.remove_package_family", return_value=True) as mock_rm_fam, \
                contextlib.redirect_stdout(out):
            command(opts, parser)
        self.assertIn("Package family removed.", out.getvalue())
        mock_rm_fam.assert_called_once_with("foo", "/repo", force=False)

        # --force-family passes force=True
        opts_force = parser.parse_args(["--force-family", "/repo"])
        out = io.StringIO()
        with patch("rez.package_remove.remove_package_family", return_value=True) as mock_rm_fam, \
                contextlib.redirect_stdout(out):
            command(opts_force, parser)
        self.assertIn("Package family removed.", out.getvalue())
        mock_rm_fam.assert_called_once_with(None, "/repo", force=True)

        # Not found
        err = io.StringIO()
        with patch("rez.package_remove.remove_package_family", return_value=False), \
                contextlib.redirect_stderr(err):
            with self.assertRaises(SystemExit) as cm:
                command(opts, parser)
        self.assertEqual(cm.exception.code, 1)
        self.assertIn("Package family not found.", err.getvalue())

    def test_remove_ignored_since_paths(self):
        from rez.cli.rm import command, setup_parser

        parser = _make_parser(setup_parser)

        # Dry run with PATH and count > 0
        opts = parser.parse_args(["-i", "7", "--dry-run", "/repo"])
        out = io.StringIO()
        with patch("rez.package_remove.remove_packages_ignored_since", return_value=3) as mock_fn, \
                contextlib.redirect_stdout(out):
            command(opts, parser)
        self.assertIn("3 packages would be removed.", out.getvalue())
        mock_fn.assert_called_once_with(days=7, paths=["/repo"], dry_run=True, verbose=0)

        # Real run without PATH and count > 0
        opts = parser.parse_args(["-i", "7"])
        out = io.StringIO()
        with patch("rez.package_remove.remove_packages_ignored_since", return_value=2) as mock_fn, \
                contextlib.redirect_stdout(out):
            command(opts, parser)
        self.assertIn("2 packages were removed.", out.getvalue())
        mock_fn.assert_called_once_with(days=7, paths=None, dry_run=False, verbose=0)

        # Zero removed
        out = io.StringIO()
        with patch("rez.package_remove.remove_packages_ignored_since", return_value=0), \
                contextlib.redirect_stdout(out):
            command(opts, parser)
        self.assertIn("No packages were removed.", out.getvalue())


class TestCliUtil(TestBase):
    """Tests for rez.cli._util."""

    def test_env_var_true(self):
        from rez.cli._util import _env_var_true

        with restore_os_environ():
            for val in ("1", "true", "TRUE", "on", "yes"):
                os.environ["_REZ_TEST_FLAG"] = val
                self.assertTrue(_env_var_true("_REZ_TEST_FLAG"))
            for val in ("0", "false", "", "no"):
                os.environ["_REZ_TEST_FLAG"] = val
                self.assertFalse(_env_var_true("_REZ_TEST_FLAG"))

    def test_print_items(self):
        from rez.cli._util import print_items

        # Non-tty stream -> one item per line
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            print_items(["a", "b"], stream=buf)
        self.assertEqual(buf.getvalue().splitlines(), ["a", "b"])

        # TTY stream -> space-separated
        tty_stream = MagicMock()
        tty_stream.isatty.return_value = True
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            print_items(["a", "b"], stream=tty_stream)
        self.assertEqual(buf.getvalue().strip(), "a b")

        # isatty raises -> falls back to one item per line
        bad_stream = MagicMock()
        bad_stream.isatty.side_effect = RuntimeError("broken")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            print_items(["x", "y"], stream=bad_stream)
        self.assertEqual(buf.getvalue().splitlines(), ["x", "y"])

    def test_lazy_argument_parser_and_subparsers(self):
        from rez.cli._util import LazyArgumentParser

        root = LazyArgumentParser(prog="rez")
        subs = root.add_subparsers(dest="cmd")

        def setup_foo(name, parser):
            parser.add_argument("--flag", action="store_true")
            return "foo help text"

        def setup_hidden(name, parser):
            return argparse.SUPPRESS

        subs.add_parser("foo", help="placeholder", setup_subparser=setup_foo)
        subs.add_parser("hidden", help="placeholder", setup_subparser=setup_hidden)

        # Unknown parser raises ArgumentError
        with self.assertRaises(argparse.ArgumentError):
            subs(root, argparse.Namespace(), ["nonexistent"])

        # format_help triggers _setup_all_subparsers and sets help / suppresses hidden
        help_text = root.format_help()
        self.assertIn("foo help text", help_text)
        self.assertEqual([a.dest for a in subs._choices_actions], ["foo"])

        # Parsing foo works
        ns = root.parse_args(["foo", "--flag"])
        self.assertTrue(ns.flag)

    def test_load_plugin_cmd(self):
        from rez.cli._util import load_plugin_cmd

        mod_ok = types.SimpleNamespace(__name__="plugin_ok")
        mod_bad = types.SimpleNamespace(__name__="plugin_bad", command_behavior="not_a_dict")

        fake_pm = MagicMock()
        fake_pm.get_plugins.return_value = ["ok", "bad"]
        fake_pm.get_plugin_module.side_effect = lambda _t, name: mod_ok if name == "ok" else mod_bad

        self.update_settings({"debug_plugins": True})
        with patch("rez.plugin_managers.plugin_manager", fake_pm), \
                patch("rez.utils.logging_.print_debug"):
            result = load_plugin_cmd()

        self.assertEqual(result, {"ok": {"module_name": "plugin_ok"}})

    def test_signal_handlers(self):
        import rez.cli._util as cli_util

        orig_int = cli_util._handled_int
        orig_term = cli_util._handled_term
        try:
            with restore_os_environ():
                os.environ.pop("_REZ_NO_KILLPG", None)
                os.environ.pop("_REZ_QUIET_ON_SIG", None)

                # sigint_handler (posix)
                cli_util._handled_int = False
                err = io.StringIO()
                out = io.StringIO()
                with patch("os.name", "posix"), \
                        patch("os.getpgid", return_value=123, create=True), \
                        patch("os.killpg", create=True) as mock_killpg, \
                        contextlib.redirect_stderr(err), \
                        contextlib.redirect_stdout(out):
                    with self.assertRaises(SystemExit) as cm:
                        cli_util.sigint_handler(signal.SIGINT, None)
                self.assertEqual(cm.exception.code, 1)
                self.assertIn("Interrupted by user", err.getvalue())
                mock_killpg.assert_called_once_with(123, signal.SIGINT)

                # Second call when _handled_int is already True is a no-op
                cli_util.sigint_handler(signal.SIGINT, None)

                # sigterm_handler with _REZ_NO_KILLPG=1 and _REZ_QUIET_ON_SIG=1
                os.environ["_REZ_NO_KILLPG"] = "1"
                os.environ["_REZ_QUIET_ON_SIG"] = "1"
                cli_util._handled_term = False
                err = io.StringIO()
                with contextlib.redirect_stderr(err), \
                        contextlib.redirect_stdout(io.StringIO()):
                    with self.assertRaises(SystemExit) as cm:
                        cli_util.sigterm_handler(signal.SIGTERM, None)
                self.assertEqual(cm.exception.code, 1)
                self.assertEqual(err.getvalue(), "")

                # sigbase_handler Windows branch
                os.environ.pop("_REZ_NO_KILLPG", None)
                with patch("os.name", "nt"), \
                        patch("os.kill") as mock_kill, \
                        patch.object(signal, "CTRL_C_EVENT", 0, create=True), \
                        contextlib.redirect_stdout(io.StringIO()):
                    with self.assertRaises(SystemExit) as cm:
                        cli_util.sigbase_handler(signal.SIGINT, None)
                self.assertEqual(cm.exception.code, 1)
                mock_kill.assert_called_once()
        finally:
            cli_util._handled_int = orig_int
            cli_util._handled_term = orig_term


class TestCliPkgIgnore(TestBase):
    """Tests for rez.cli.pkg-ignore."""

    def test_setup_parser_with_completions(self):
        pkg_ignore = importlib.import_module("rez.cli.pkg-ignore")
        parser = _make_parser(pkg_ignore.setup_parser, completions=True)
        opts = parser.parse_args(["-u", "-a", "foo-1.0", "/repo"])
        self.assertTrue(opts.unignore)
        self.assertTrue(opts.allow_missing)
        self.assertEqual(opts.PKG, "foo-1.0")
        self.assertEqual(opts.PATH, "/repo")

    def test_command_no_path_allow_missing(self):
        pkg_ignore = importlib.import_module("rez.cli.pkg-ignore")
        self.update_settings({"packages_path": ["/repo1", "/repo2"]})

        parser = _make_parser(pkg_ignore.setup_parser)
        opts = parser.parse_args(["-a", "foo-1.0"])

        out = io.StringIO()
        with patch("rez.package_repository.package_repository_manager.get_repository",
                   side_effect=lambda p: "repo:" + p), \
                contextlib.redirect_stdout(out):
            with self.assertRaises(SystemExit) as cm:
                pkg_ignore.command(opts, parser)
        self.assertEqual(cm.exception.code, 0)
        self.assertIn("repo:/repo1", out.getvalue())
        self.assertIn("repo:/repo2", out.getvalue())

    def test_command_no_path_finds_and_missing(self):
        pkg_ignore = importlib.import_module("rez.cli.pkg-ignore")
        self.update_settings({"packages_path": ["/repo1"]})

        parser = _make_parser(pkg_ignore.setup_parser)
        opts = parser.parse_args(["foo-1.0"])

        # Found in repo1
        repo_hit = MagicMock()
        repo_hit.__str__ = lambda self: "repo1"
        repo_hit.get_package.return_value = MagicMock()
        out = io.StringIO()
        with patch("rez.package_repository.package_repository_manager.get_repository", return_value=repo_hit), \
                contextlib.redirect_stdout(out):
            with self.assertRaises(SystemExit) as cm:
                pkg_ignore.command(opts, parser)
        self.assertEqual(cm.exception.code, 0)
        self.assertIn("repo1", out.getvalue())

        # Not found in any repo
        repo_miss = MagicMock()
        repo_miss.get_package.return_value = None
        err = io.StringIO()
        with patch("rez.package_repository.package_repository_manager.get_repository", return_value=repo_miss), \
                contextlib.redirect_stderr(err):
            with self.assertRaises(SystemExit) as cm:
                pkg_ignore.command(opts, parser)
        self.assertEqual(cm.exception.code, 1)
        self.assertIn("Package not found.", err.getvalue())

    def test_command_ignore_and_unignore_outcomes(self):
        pkg_ignore = importlib.import_module("rez.cli.pkg-ignore")
        parser = _make_parser(pkg_ignore.setup_parser)

        cases = [
            (["foo-1.0", "/repo"], "ignore_package", 1, "now ignored", None),
            (["-a", "foo-1.0", "/repo"], "ignore_package", 1, "now ignored", None),
            (["foo-1.0", "/repo"], "ignore_package", 0, "already ignored", None),
            (["foo-1.0", "/repo"], "ignore_package", -1, "Package not found", 1),
            (["-u", "foo-1.0", "/repo"], "unignore_package", 1, "now visible", None),
            (["-u", "foo-1.0", "/repo"], "unignore_package", 0, "already visible", None),
            (["-u", "foo-1.0", "/repo"], "unignore_package", -1, "Package not found", 1),
        ]
        for args, method_name, ret_val, expected_msg, exit_code in cases:
            opts = parser.parse_args(args)
            repo = MagicMock()
            getattr(repo, method_name).return_value = ret_val
            out = io.StringIO()
            err = io.StringIO()
            with patch("rez.package_repository.package_repository_manager.get_repository", return_value=repo), \
                    contextlib.redirect_stdout(out), \
                    contextlib.redirect_stderr(err):
                if exit_code is not None:
                    with self.assertRaises(SystemExit) as cm:
                        pkg_ignore.command(opts, parser)
                    self.assertEqual(cm.exception.code, exit_code)
                    self.assertIn(expected_msg, err.getvalue())
                else:
                    pkg_ignore.command(opts, parser)
                    self.assertIn(expected_msg, out.getvalue())
            if method_name == "ignore_package":
                self.assertEqual(
                    repo.ignore_package.call_args[1]["allow_missing"],
                    "-a" in args,
                )


class TestCliBuild(TestBase):
    """Tests for rez.cli.build."""

    def setUp(self):
        super().setUp()
        import rez.cli.build as build_cli
        self._orig_pkg = build_cli._package
        build_cli._package = None

    def tearDown(self):
        import rez.cli.build as build_cli
        build_cli._package = self._orig_pkg
        super().tearDown()

    def test_get_current_developer_package_caches(self):
        import rez.cli.build as build_cli

        mock_pkg = MagicMock()
        with patch("rez.packages.get_developer_package", return_value=mock_pkg) as mock_get:
            p1 = build_cli.get_current_developer_package()
            p2 = build_cli.get_current_developer_package()
        self.assertIs(p1, mock_pkg)
        self.assertIs(p2, mock_pkg)
        mock_get.assert_called_once()

    def test_setup_parser_variants(self):
        from rez.cli.build import setup_parser
        from rez.exceptions import PackageMetadataError

        # PackageMetadataError + single build system binds CLI
        cls1 = MagicMock()
        cls1.name.return_value = "cmake"
        with patch("rez.cli.build.get_current_developer_package", side_effect=PackageMetadataError("bad")), \
                patch("rez.build_system.get_valid_build_systems", return_value=[cls1]):
            parser = _make_parser(setup_parser)
        cls1.bind_cli.assert_called_once()
        opts = parser.parse_args(["-c", "-i", "-p", "/dst", "--fail-graph", "-s"])
        self.assertTrue(opts.clean)
        self.assertTrue(opts.install)
        self.assertEqual(opts.prefix, "/dst")
        self.assertTrue(opts.fail_graph)
        self.assertTrue(opts.scripts)

        # Multiple build systems -> choices list
        cls2 = MagicMock()
        cls2.name.return_value = "make"
        with patch("rez.cli.build.get_current_developer_package", return_value=MagicMock()), \
                patch("rez.build_system.get_valid_build_systems", return_value=[cls1, cls2]):
            parser2 = _make_parser(setup_parser)
        opts2 = parser2.parse_args(["-b", "make"])
        self.assertEqual(opts2.buildsys, "make")

    def test_get_build_args(self):
        from rez.cli.build import get_build_args, setup_parser

        with patch("rez.cli.build.get_current_developer_package", return_value=None), \
                patch("rez.build_system.get_valid_build_systems", return_value=[]):
            parser = _make_parser(setup_parser)

        # Option strings split into args
        opts = parser.parse_args(["--ba", "-j4 -v", "--cba", "--target foo"])
        ba, cba = get_build_args(opts, parser, None)
        self.assertEqual(ba, ["-j4", "-v"])
        self.assertEqual(cba, ["--target", "foo"])

        # Conflict with extra_arg_groups triggers parser.error
        opts = parser.parse_args(["--ba=-j4"])
        with self.assertRaises(SystemExit) as cm:
            with contextlib.redirect_stderr(io.StringIO()):
                get_build_args(opts, parser, [["-k"]])
        self.assertEqual(cm.exception.code, 2)

    def test_command_view_pre_build_and_resolve_error(self):
        from rez.cli.build import command, setup_parser
        from rez.exceptions import BuildContextResolveError

        mock_pkg = MagicMock()
        with patch("rez.cli.build.get_current_developer_package", return_value=mock_pkg), \
                patch("rez.build_system.get_valid_build_systems", return_value=[]):
            parser = _make_parser(setup_parser)

        # --view-pre exits 0
        opts = parser.parse_args(["--view-pre"])
        with patch("rez.cli.build.get_current_developer_package", return_value=mock_pkg):
            with self.assertRaises(SystemExit) as cm:
                command(opts, parser)
        self.assertEqual(cm.exception.code, 0)
        mock_pkg.print_info.assert_called_once()

        # Normal build
        mock_builder = MagicMock()
        opts = parser.parse_args(["-c", "-i", "-p", "/out"])
        with patch("rez.cli.build.get_current_developer_package", return_value=mock_pkg), \
                patch("rez.build_system.create_build_system", return_value=MagicMock()) as mock_create_bs, \
                patch("rez.build_process.create_build_process", return_value=mock_builder):
            command(opts, parser)
        self.assertFalse(mock_create_bs.call_args[1]["write_build_scripts"])
        mock_builder.build.assert_called_once_with(
            install_path="/out", clean=True, install=True, variants=None
        )

        # Build with -s/--scripts passes write_build_scripts=True
        opts_scripts = parser.parse_args(["-s"])
        with patch("rez.cli.build.get_current_developer_package", return_value=mock_pkg), \
                patch("rez.build_system.create_build_system", return_value=MagicMock()) as mock_create_bs, \
                patch("rez.build_process.create_build_process", return_value=mock_builder):
            command(opts_scripts, parser)
        self.assertTrue(mock_create_bs.call_args[1]["write_build_scripts"])

        # BuildContextResolveError with --fail-graph and graph present
        ctx_with_graph = MagicMock()
        ctx_with_graph.graph.return_value = "digraph {}"
        err_with_graph = BuildContextResolveError(ctx_with_graph)
        mock_builder.build.side_effect = err_with_graph
        opts = parser.parse_args(["--fail-graph"])
        with patch("rez.cli.build.get_current_developer_package", return_value=mock_pkg), \
                patch("rez.build_system.create_build_system", return_value=MagicMock()), \
                patch("rez.build_process.create_build_process", return_value=mock_builder), \
                patch("rez.utils.graph_utils.view_graph") as mock_view, \
                contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as cm:
                command(opts, parser)
        self.assertEqual(cm.exception.code, 1)
        mock_view.assert_called_once_with("digraph {}")

    @unittest.expectedFailure
    def test_command_resolve_error_fail_graph_no_graph(self):
        # Bug at src/rez/cli/build.py:173: checks `if e.context.graph:` (bound
        # method, always truthy) instead of `if e.context.has_graph:`.
        from rez.cli.build import command, setup_parser
        from rez.exceptions import BuildContextResolveError
        from rez.resolved_context import ResolvedContext

        mock_pkg = MagicMock()
        with patch("rez.cli.build.get_current_developer_package", return_value=mock_pkg), \
                patch("rez.build_system.get_valid_build_systems", return_value=[]):
            parser = _make_parser(setup_parser)

        ctx_no_graph = MagicMock(spec=ResolvedContext)
        ctx_no_graph.has_graph = False
        ctx_no_graph.graph.return_value = None
        mock_builder = MagicMock()
        mock_builder.build.side_effect = BuildContextResolveError(ctx_no_graph)
        opts = parser.parse_args(["--fail-graph"])
        stderr = io.StringIO()
        with patch("rez.cli.build.get_current_developer_package", return_value=mock_pkg), \
                patch("rez.build_system.create_build_system", return_value=MagicMock()), \
                patch("rez.build_process.create_build_process", return_value=mock_builder), \
                patch("rez.utils.graph_utils.view_graph") as mock_view, \
                contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as cm:
                command(opts, parser)
        self.assertEqual(cm.exception.code, 1)
        mock_view.assert_not_called()
        self.assertIn("did not generate a graph", stderr.getvalue())


class TestCliCompleteUtil(TestBase, TempdirMixin):
    """Tests for rez.cli._complete_util."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        TempdirMixin.setUpClass()

    @classmethod
    def tearDownClass(cls):
        TempdirMixin.tearDownClass()
        super().tearDownClass()

    def test_config_and_package_completers(self):
        from rez.cli._complete_util import (
            ConfigCompleter,
            PackageCompleter,
            PackageFamilyCompleter,
        )

        with patch("rez.config.config.get_completions", return_value=["packages_path"]) as mock_cfg:
            self.assertEqual(ConfigCompleter("pack"), ["packages_path"])
        mock_cfg.assert_called_once_with("pack")

        with patch("rez.packages.get_completions", return_value=["foo-1.0"]) as mock_pkg:
            self.assertEqual(PackageCompleter("foo"), ["foo-1.0"])
        mock_pkg.assert_called_once_with("foo")

        with patch("rez.packages.get_completions", return_value=["foo"]) as mock_fam:
            self.assertEqual(PackageFamilyCompleter("fo"), ["foo"])
        mock_fam.assert_called_once_with("fo", family_only=True)

    @unittest.skipIf(platform_.name == "windows", "POSIX execute bits not supported on Windows")
    def test_executables_completer(self):
        from rez.cli._complete_util import ExecutablesCompleter

        bindir = os.path.join(self.root, "bin")
        os.makedirs(bindir, exist_ok=True)
        exe_path = os.path.join(bindir, "mytool")
        non_exe_path = os.path.join(bindir, "mydoc")
        with open(exe_path, "w") as f:
            f.write("#!/bin/sh\n")
        os.chmod(exe_path, 0o755)
        with open(non_exe_path, "w") as f:
            f.write("text\n")
        os.chmod(non_exe_path, 0o644)

        with restore_os_environ():
            os.environ["PATH"] = bindir + os.pathsep + os.path.join(self.root, "missing")
            res = ExecutablesCompleter("my")
        self.assertEqual(res, {"mytool"})

    def test_files_completer(self):
        from rez.cli._complete_util import FilesCompleter

        fdir = os.path.join(self.root, "files")
        sub = os.path.join(fdir, "subdir")
        os.makedirs(sub, exist_ok=True)
        with open(os.path.join(fdir, "alpha.rxt"), "w") as f:
            f.write("")
        with open(os.path.join(fdir, "alpha.txt"), "w") as f:
            f.write("")

        # Relative path with file_patterns and dirs=False
        with patch("os.getcwd", return_value=fdir):
            res = list(FilesCompleter(files=True, dirs=False, file_patterns=["*.rxt"])("a"))
        self.assertEqual(res, ["alpha.rxt"])

        # files=False, dirs=True (with empty prefix so files are skipped too)
        with patch("os.getcwd", return_value=fdir):
            res_dirs = list(FilesCompleter(files=False, dirs=True)(""))
        self.assertIn("subdir" + os.path.sep, res_dirs)
        self.assertIn("subdir", res_dirs)

        # Absolute prefix
        res_abs = list(FilesCompleter()(os.path.join(fdir, "alpha.r")))
        self.assertEqual(res_abs, [os.path.join(fdir, "alpha.rxt")])

        # Nonexistent path -> []
        self.assertEqual(list(FilesCompleter()("/nonexistent_dir_xyz/foo")), [])

    def test_and_and_sequenced_completers(self):
        from rez.cli._complete_util import AndCompleter, SequencedCompleter

        def c1(p, **kw):
            return [p + "1"]

        def c2(p, **kw):
            return [p + "2"]

        and_c = AndCompleter(c1, c2)
        self.assertEqual(and_c("x"), {"x1", "x2"})

        seq = SequencedCompleter("extra_0", c1, c2)
        self.assertEqual(seq("p", parsed_args=argparse.Namespace(extra_0=[])), ["p1"])
        self.assertEqual(seq("p", parsed_args=argparse.Namespace(extra_0=["a"])), ["p2"])
        self.assertEqual(seq("p", parsed_args=argparse.Namespace(extra_0=["a", "b", "c"])), ["p2"])
        self.assertEqual(seq("p", parsed_args=argparse.Namespace()), [])


class TestCliTest(TestBase):
    """Tests for rez.cli.test."""

    def test_setup_parser_completions(self):
        from rez.cli.test import setup_parser

        parser = _make_parser(setup_parser, completions=True)
        opts = parser.parse_args(["-l", "--dry-run", "-s", "foo-1.0", "unit"])
        self.assertTrue(opts.list)
        self.assertTrue(opts.dry_run)
        self.assertTrue(opts.stop_on_fail)
        self.assertEqual(opts.PKG, "foo-1.0")
        self.assertEqual(opts.TEST, ["unit"])

    def test_command_validation_errors(self):
        from rez.cli.test import command, setup_parser

        parser = _make_parser(setup_parser)

        # --inplace with --no-local
        opts = parser.parse_args(["--inplace", "--nl", "foo"])
        with self.assertRaises(SystemExit) as cm:
            with contextlib.redirect_stderr(io.StringIO()):
                command(opts, parser)
        self.assertEqual(cm.exception.code, 2)

        # extra_arg_groups with multiple tests
        opts = parser.parse_args(["foo", "t1", "t2"])
        with self.assertRaises(SystemExit) as cm:
            with contextlib.redirect_stderr(io.StringIO()):
                command(opts, parser, extra_arg_groups=[["--flag"]])
        self.assertEqual(cm.exception.code, 2)

    def test_command_no_tests_list_and_no_default_tests(self):
        from rez.cli.test import command, setup_parser

        parser = _make_parser(setup_parser)
        runner = MagicMock()
        runner.get_package.return_value = MagicMock(uri="/pkg")

        # No tests found
        runner.get_test_names.return_value = []
        opts = parser.parse_args(["foo"])
        err = io.StringIO()
        with patch("rez.package_test.PackageTestRunner", return_value=runner), \
                contextlib.redirect_stderr(err):
            with self.assertRaises(SystemExit) as cm:
                command(opts, parser)
        self.assertEqual(cm.exception.code, 0)
        self.assertIn("No tests found", err.getvalue())

        # --list with tty stdout
        runner.get_test_names.return_value = ["unit", "lint"]
        opts = parser.parse_args(["-l", "foo"])
        out = io.StringIO()
        with patch("rez.package_test.PackageTestRunner", return_value=runner), \
                patch("sys.stdout", out), \
                patch.object(out, "isatty", return_value=True):
            with self.assertRaises(SystemExit) as cm:
                command(opts, parser)
        self.assertEqual(cm.exception.code, 0)
        self.assertIn("Tests defined in /pkg:", out.getvalue())
        self.assertIn("unit\nlint", out.getvalue())

        # No tests with default run_on tag
        runner.find_requested_test_names.return_value = []
        opts = parser.parse_args(["--paths", "/p1" + os.pathsep, "foo"])
        err = io.StringIO()
        with patch("rez.package_test.PackageTestRunner", return_value=runner), \
                contextlib.redirect_stderr(err):
            with self.assertRaises(SystemExit) as cm:
                command(opts, parser)
        self.assertEqual(cm.exception.code, 0)
        self.assertIn("default", err.getvalue())

    def test_command_runs_tests_and_returns_exitcode(self):
        from rez.cli.test import command, setup_parser

        parser = _make_parser(setup_parser)
        runner = MagicMock()
        runner.get_package.return_value = MagicMock(uri="/pkg")
        runner.get_test_names.return_value = ["unit"]
        runner.find_requested_test_names.return_value = ["unit"]
        runner.stopped_on_fail = False
        runner.run_test.return_value = 3

        opts = parser.parse_args(["--nl", "foo", "unit"])
        with patch("rez.package_test.PackageTestRunner", return_value=runner) as mock_runner_cls, \
                contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as cm:
                command(opts, parser, extra_arg_groups=[["-k", "fast"]])
        self.assertEqual(cm.exception.code, 3)
        self.assertFalse(mock_runner_cls.call_args[1]["dry_run"])
        runner.run_test.assert_called_once_with("unit", extra_test_args=["-k", "fast"])
        runner.print_summary.assert_called_once()

        # --dry-run passes dry_run=True
        runner.reset_mock()
        opts_dry = parser.parse_args(["--dry-run", "foo", "unit"])
        with patch("rez.package_test.PackageTestRunner", return_value=runner) as mock_runner_cls, \
                contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as cm:
                command(opts_dry, parser)
        self.assertEqual(cm.exception.code, 3)
        self.assertTrue(mock_runner_cls.call_args[1]["dry_run"])


class TestCliEnv(TestBase):
    """Tests for rez.cli.env."""

    def test_command_arg_validation_errors(self):
        from rez.cli.env import command, setup_parser

        parser = _make_parser(setup_parser, completions=True)

        # -c and extra_arg_groups together
        opts = parser.parse_args(["-c", "echo hi"])
        with self.assertRaises(SystemExit) as cm:
            with contextlib.redirect_stderr(io.StringIO()):
                command(opts, parser, extra_arg_groups=[["ls"]])
        self.assertEqual(cm.exception.code, 2)

        # --input and PKG without --patch
        opts = parser.parse_args(["-i", "ctx.rxt", "foo"])
        with self.assertRaises(SystemExit) as cm:
            with contextlib.redirect_stderr(io.StringIO()):
                command(opts, parser)
        self.assertEqual(cm.exception.code, 2)

    def test_command_patch_outside_context_fails(self):
        from rez.cli.env import command, setup_parser

        parser = _make_parser(setup_parser)
        opts = parser.parse_args(["-p", "foo"])
        err = io.StringIO()
        with patch("rez.status.status") as mock_status, \
                contextlib.redirect_stderr(err):
            mock_status.context = None
            with self.assertRaises(SystemExit) as cm:
                command(opts, parser)
        self.assertEqual(cm.exception.code, 1)
        self.assertIn("cannot patch", err.getvalue())

    def test_command_output_success_and_failure(self):
        from rez.cli.env import command, setup_parser
        from rez.package_filter import PackageFilterList
        from rez.resolver import ResolverStatus

        parser = _make_parser(setup_parser)
        fake_copy = PackageFilterList()
        fake_singleton = MagicMock()
        fake_singleton.copy.return_value = fake_copy

        # Solved context written to stdout ('-') with --no-filters
        mock_ctx = MagicMock()
        mock_ctx.status = ResolverStatus.solved
        opts = parser.parse_args(["-o", "-", "--no-filters", "--exclude", "*.beta",
                                  "--include", "foo", "--pkg-cache-mode", "async", "foo"])
        with patch.object(PackageFilterList, "singleton", fake_singleton), \
                patch("rez.resolved_context.ResolvedContext", return_value=mock_ctx) as mock_rc:
            with self.assertRaises(SystemExit) as cm:
                command(opts, parser)
        self.assertEqual(cm.exception.code, 0)
        fake_singleton.copy.assert_not_called()
        self.assertIsNot(mock_rc.call_args[1]["package_filter"], fake_copy)
        self.assertTrue(mock_rc.call_args[1]["add_implicit_packages"])
        mock_ctx.write_to_buffer.assert_called_once_with(sys.stdout)

        # Failed context with --fail-graph and output file (default filters, --ni)
        mock_fail_ctx = MagicMock()
        mock_fail_ctx.status = ResolverStatus.failed
        mock_fail_ctx.graph.return_value = "digraph {}"
        opts = parser.parse_args(["-o", "/tmp/out.rxt", "--fail-graph", "--ni",
                                  "--pkg-cache-mode", "sync", "--nl", "foo"])
        with patch.object(PackageFilterList, "singleton", fake_singleton), \
                patch("rez.resolved_context.ResolvedContext", return_value=mock_fail_ctx) as mock_rc, \
                patch("rez.utils.graph_utils.view_graph") as mock_view, \
                contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as cm:
                command(opts, parser)
        self.assertEqual(cm.exception.code, 1)
        fake_singleton.copy.assert_called_once()
        self.assertIs(mock_rc.call_args[1]["package_filter"], fake_copy)
        self.assertFalse(mock_rc.call_args[1]["add_implicit_packages"])
        mock_view.assert_called_once_with("digraph {}")
        mock_fail_ctx.save.assert_called_once_with("/tmp/out.rxt")

    @unittest.expectedFailure
    def test_command_fail_graph_no_graph(self):
        # Bug at src/rez/cli/env.py:240: checks `if context.graph:` (bound
        # method, always truthy) instead of `if context.has_graph:`.
        from rez.cli.env import command, setup_parser
        from rez.resolved_context import ResolvedContext
        from rez.resolver import ResolverStatus

        parser = _make_parser(setup_parser)
        mock_fail_no_graph = MagicMock(spec=ResolvedContext)
        mock_fail_no_graph.status = ResolverStatus.failed
        mock_fail_no_graph.has_graph = False
        mock_fail_no_graph.graph.return_value = None
        opts = parser.parse_args(["--fail-graph", "foo"])
        err = io.StringIO()
        with patch("rez.resolved_context.ResolvedContext", return_value=mock_fail_no_graph), \
                patch("rez.utils.graph_utils.view_graph") as mock_view, \
                contextlib.redirect_stderr(err):
            with self.assertRaises(SystemExit) as cm:
                command(opts, parser)
        self.assertEqual(cm.exception.code, 1)
        mock_view.assert_not_called()
        self.assertIn("did not generate a graph", err.getvalue())

    def test_command_input_patch_and_execute_shell(self):
        from rez.cli.env import command, setup_parser
        from rez.resolver import ResolverStatus

        parser = _make_parser(setup_parser)
        loaded_ctx = MagicMock()
        loaded_ctx.get_patched_request.return_value = ["foo-1.0", "bar"]
        solved_ctx = MagicMock()
        solved_ctx.status = ResolverStatus.solved
        solved_ctx.execute_shell.return_value = (7, None, None)

        opts = parser.parse_args([
            "-i", "in.rxt", "-p", "-s", "-t", "1000", "--paths", "/p1" + os.pathsep, "bar",
        ])
        with patch("rez.resolved_context.ResolvedContext.load", return_value=loaded_ctx), \
                patch("rez.resolved_context.ResolvedContext", return_value=solved_ctx), \
                patch("select.select", return_value=([], [], [])):
            with self.assertRaises(SystemExit) as cm:
                command(opts, parser, extra_arg_groups=[["echo", "ok"]])
        self.assertEqual(cm.exception.code, 7)
        solved_ctx.execute_shell.assert_called_once()
        self.assertFalse(solved_ctx.execute_shell.call_args[1]["stdin"])
        self.assertEqual(solved_ctx.execute_shell.call_args[1]["command"], ["echo", "ok"])
        self.assertTrue(solved_ctx.execute_shell.call_args[1]["quiet"])

        # select.error is swallowed cleanly
        opts2 = parser.parse_args(["-i", "in.rxt", "-s"])
        loaded_ctx.status = ResolverStatus.solved
        loaded_ctx.execute_shell.return_value = (0, None, None)
        with patch("rez.resolved_context.ResolvedContext.load", return_value=loaded_ctx), \
                patch("select.select", side_effect=select.error("win")):
            with self.assertRaises(SystemExit) as cm:
                command(opts2, parser)
        self.assertEqual(cm.exception.code, 0)
        self.assertFalse(loaded_ctx.execute_shell.call_args[1]["quiet"])


if __name__ == "__main__":
    unittest.main()
