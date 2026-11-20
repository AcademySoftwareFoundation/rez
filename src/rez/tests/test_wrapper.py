# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
test rez.wrapper
"""
from rez.tests.util import TestBase, TempdirMixin, restore_os_environ
from rez.config import config
from rez.exceptions import RezSystemError
from rez.resolved_context import ResolvedContext
from rez.suite import Suite
from rez.wrapper import Wrapper
import contextlib
import io
import os
import os.path
import select
import sys
import types
import unittest
from unittest import mock


def _expected_failure_on_windows(func):
    if sys.platform == "win32":
        return unittest.expectedFailure(func)
    return func


class TestWrapper(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        TempdirMixin.setUpClass()

        packages_path = cls.data_path("suites", "packages")
        cls.settings = dict(
            packages_path=[packages_path],
            package_filter=None,
            implicit_packages=[],
            warn_untimestamped=False,
            resolve_caching=False,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        TempdirMixin.tearDownClass()
        super().tearDownClass()

    def _create_saved_suite(self, subdir, pkg_name="pooh", context_name="pooh",
                            prefix_char=None):
        suite_path = os.path.join(self.root, subdir)
        ctx = ResolvedContext([pkg_name])
        suite = Suite()
        suite.add_context(context_name, ctx, prefix_char=prefix_char)
        suite.save(suite_path)
        return suite_path, suite

    def _make_wrapper(self, suite_path="/tmp/suite", context_name="pooh",
                      tool_name="hunny", prefix_char=None, context=None):
        if context is None:
            context = ResolvedContext(["pooh"])
        w = Wrapper.__new__(Wrapper)
        w._init(suite_path, context_name, context, tool_name, prefix_char)
        return w

    @_expected_failure_on_windows
    def test_init_from_saved_suite(self) -> None:
        """Wrapper loads valid yaml executable inside a saved suite."""
        # Bug in src/rez/wrapper.py:37-40: Wrapper.__init__ passes .cmd batch
        # headers created by create_forwarding_script() directly to yaml.load()
        # instead of stripping the 4-line batch preamble like rez.cli.forward.
        suite_path, _ = self._create_saved_suite("init_valid", prefix_char="@")
        ext = ".cmd" if sys.platform == "win32" else ""
        wrapper_file = os.path.join(suite_path, "bin", "hunny" + ext)

        w = Wrapper(wrapper_file)
        self.assertEqual(w.suite_path, suite_path)
        self.assertEqual(w.context_name, "pooh")
        self.assertEqual(w.tool_name, "hunny")
        self.assertEqual(w.prefix_char, "@")
        self.assertIsInstance(w.context, ResolvedContext)
        self.assertIsInstance(w.suite, Suite)
        self.assertIs(w.suite, w.suite)

    def test_init_invalid_yaml(self) -> None:
        """Wrapper raises RezSystemError on malformed YAML."""
        bad_dir = os.path.join(self.root, "init_bad_yaml", "bin")
        os.makedirs(bad_dir, exist_ok=True)
        bad_file = os.path.join(bad_dir, "hunny")
        with open(bad_file, "w") as f:
            f.write(":\n  - [unclosed\n")

        with self.assertRaises(RezSystemError) as cm:
            Wrapper(bad_file)
        self.assertIn("Invalid executable file", str(cm.exception))

    def test_init_missing_suite(self) -> None:
        """Wrapper raises RezSystemError when moved outside a valid suite."""
        orphan_dir = os.path.join(self.root, "init_orphan", "bin")
        os.makedirs(orphan_dir, exist_ok=True)
        orphan_file = os.path.join(orphan_dir, "hunny")
        with open(orphan_file, "w") as f:
            f.write("kwargs:\n  context_name: pooh\n  tool_name: hunny\n")

        with self.assertRaises(RezSystemError) as cm:
            Wrapper(orphan_file)
        self.assertIn("Invalid executable file", str(cm.exception))

    def test_run_no_args_empty_prefix_char(self) -> None:
        """Empty prefix_char bypasses wrapper arg parsing via _run_no_args."""
        w = self._make_wrapper(prefix_char="")
        with mock.patch.object(
            w.context, "execute_shell", return_value=(42, "", "")
        ) as exec_mock:
            ret = w.run("++about", "--flag")

        self.assertEqual(ret, 42)
        exec_mock.assert_called_once_with(
            command=["hunny", "++about", "--flag"],
            block=True,
        )

    def test_run_empty_prefix_char_from_config(self) -> None:
        """prefix_char=None falls back to config.suite_alias_prefix_char."""
        self.update_settings({"suite_alias_prefix_char": ""})
        w = self._make_wrapper(prefix_char=None)
        with mock.patch.object(
            w.context, "execute_shell", return_value=(0, "", "")
        ) as exec_mock:
            ret = w.run("arg1")

        self.assertEqual(ret, 0)
        exec_mock.assert_called_once_with(command=["hunny", "arg1"], block=True)

    def test_run_default_tool_invocation(self) -> None:
        """Standard run forwards non-rez args to the wrapped tool."""
        w = self._make_wrapper()
        with mock.patch.object(
            w.context, "execute_shell", return_value=(7, "", "")
        ) as exec_mock:
            ret = w.run("--foo", "bar")

        self.assertEqual(ret, 7)
        exec_mock.assert_called_once_with(
            command=["hunny", "--foo", "bar"],
            stdin=False,
            quiet=False,
            block=True,
        )

    def test_run_no_rez_args(self) -> None:
        """++no-rez-args passes all other args verbatim to the wrapped tool."""
        w = self._make_wrapper(prefix_char="+")
        with mock.patch.object(
            w.context, "execute_shell", return_value=(0, "", "")
        ) as exec_mock:
            ret = w.run("++no-rez-args", "++about", "--other")

        self.assertEqual(ret, 0)
        exec_mock.assert_called_once_with(
            command=["hunny", "++about", "--other"],
            stdin=False,
            quiet=False,
            block=True,
        )

    def test_run_about_versions_peek_dispatch(self) -> None:
        """++about, ++versions, and ++peek dispatch to their respective methods."""
        w = self._make_wrapper()
        with mock.patch.object(w, "print_about", return_value=0) as about_mock:
            self.assertEqual(w.run("++about"), 0)
            about_mock.assert_called_once_with()

        with mock.patch.object(
            w, "print_package_versions", return_value=1
        ) as versions_mock:
            self.assertEqual(w.run("++versions"), 1)
            versions_mock.assert_called_once_with()

        with mock.patch.object(w, "peek", return_value=0) as peek_mock:
            self.assertEqual(w.run("++peek"), 0)
            peek_mock.assert_called_once_with()

    def test_run_custom_prefix_char(self) -> None:
        """Custom prefix_char (e.g. '@') is used for wrapper flags."""
        w = self._make_wrapper(prefix_char="@")
        with mock.patch.object(w, "print_about", return_value=0) as about_mock:
            self.assertEqual(w.run("@a"), 0)
            about_mock.assert_called_once_with()

    def test_run_command_and_interactive(self) -> None:
        """++command and ++interactive configure execute_shell command and prompt."""
        w = self._make_wrapper(context_name="myctx")
        with mock.patch.object(
            w.context, "execute_shell", return_value=(0, "", "")
        ) as exec_mock:
            ret = w.run("++command", "echo", "hi")

        self.assertEqual(ret, 0)
        exec_mock.assert_called_once_with(
            command=["echo", "hi"],
            stdin=False,
            quiet=False,
            block=True,
        )

        with mock.patch.object(
            w.context, "execute_shell", return_value=(0, "", "")
        ) as exec_mock:
            ret = w.run("++interactive", "++quiet")

        self.assertEqual(ret, 0)
        self.assertEqual(config.overrides["prompt"], "myctx>")
        exec_mock.assert_called_once_with(
            command=None,
            stdin=False,
            quiet=True,
            block=True,
        )

    def test_run_patch_with_and_without_rez_quiet(self) -> None:
        """++patch re-resolves context, handles ++strict/++no-local/++verbose and REZ_QUIET."""
        w = self._make_wrapper(context_name="myctx")
        fake_patched_ctx = mock.MagicMock()
        fake_patched_ctx.execute_shell.return_value = (0, "", "")

        with restore_os_environ():
            os.environ.pop("REZ_QUIET", None)
            with mock.patch.object(
                w.context, "get_patched_request", wraps=w.context.get_patched_request
            ) as patch_req_mock:
                with mock.patch(
                    "rez.wrapper.ResolvedContext", return_value=fake_patched_ctx
                ) as rc_cls:
                    ret = w.run(
                        "++patch", "bah", "++strict", "++no-local",
                        "++verbose", "++interactive",
                    )

        self.assertEqual(ret, 0)
        patch_req_mock.assert_called_once_with(["bah"], strict=True)
        self.assertEqual(config.overrides["prompt"], "myctx*>")
        self.assertTrue(config.quiet)
        rc_cls.assert_called_once()
        _, kwargs = rc_cls.call_args
        self.assertEqual(kwargs["package_paths"], config.nonlocal_packages_path)
        self.assertEqual(kwargs["verbosity"], 1)
        fake_patched_ctx.execute_shell.assert_called_once_with(
            command=None,
            stdin=False,
            quiet=False,
            block=True,
        )

        # With REZ_QUIET set and without ++no-local, package_paths is None
        config.remove_override("quiet")
        with restore_os_environ():
            os.environ["REZ_QUIET"] = "true"
            with mock.patch(
                "rez.wrapper.ResolvedContext", return_value=fake_patched_ctx
            ) as rc_cls:
                ret = w.run("++patch", "bah")

        self.assertEqual(ret, 0)
        _, kwargs = rc_cls.call_args
        self.assertIsNone(kwargs["package_paths"])
        self.assertNotIn("quiet", config.overrides)

    def test_run_stdin_select_branches(self) -> None:
        """++stdin handles ready stdin, empty stdin, and select.error (Windows)."""
        w = self._make_wrapper()

        with mock.patch("select.select", return_value=([sys.stdin], [], [])):
            with mock.patch.object(
                w.context, "execute_shell", return_value=(0, "", "")
            ) as exec_mock:
                w.run("++stdin")
        self.assertTrue(exec_mock.call_args[1]["stdin"])

        with mock.patch("select.select", return_value=([], [], [])):
            with mock.patch.object(
                w.context, "execute_shell", return_value=(0, "", "")
            ) as exec_mock:
                w.run("++stdin")
        self.assertFalse(exec_mock.call_args[1]["stdin"])

        with mock.patch("select.select", side_effect=select.error("unsupported")):
            with mock.patch.object(
                w.context, "execute_shell", return_value=(0, "", "")
            ) as exec_mock:
                w.run("++stdin")
        self.assertTrue(exec_mock.call_args[1]["stdin"])

    def test_print_about_single_conflict_and_none(self) -> None:
        """print_about formats single variant, conflicting variants, and no variants."""
        suite_path = os.path.join(self.root, "about_suite")
        w = self._make_wrapper(suite_path=suite_path)

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ret = w.print_about()
        out = buf.getvalue()
        self.assertEqual(ret, 0)
        self.assertIn("Tool:     hunny", out)
        self.assertIn("Suite:    %s" % suite_path, out)
        self.assertIn("Package:  pooh", out)

        # Conflicting variants
        v1 = types.SimpleNamespace(qualified_package_name="pkgA-1.0")
        v2 = types.SimpleNamespace(qualified_package_name="pkgB-2.0")
        buf = io.StringIO()
        with mock.patch.object(w.context, "get_tool_variants", return_value=[v1, v2]):
            with mock.patch(
                "rez.wrapper.Printer",
                return_value=lambda msg, col=None: print(msg, file=buf),
            ):
                with contextlib.redirect_stdout(buf):
                    ret = w.print_about()
        self.assertEqual(ret, 0)
        self.assertIn("Packages (in conflict): pkgA-1.0 pkgB-2.0", buf.getvalue())

        # No variants
        buf = io.StringIO()
        with mock.patch.object(w.context, "get_tool_variants", return_value=[]):
            with contextlib.redirect_stdout(buf):
                ret = w.print_about()
        self.assertEqual(ret, 0)
        self.assertNotIn("Package:", buf.getvalue())

    def test_print_package_versions(self) -> None:
        """print_package_versions lists versions with current/local markers and handles conflicts."""
        w = self._make_wrapper()

        # Conflict returns 1
        v1 = types.SimpleNamespace(qualified_package_name="pooh-1.0")
        v2 = types.SimpleNamespace(qualified_package_name="pooh-2.0")
        buf = io.StringIO()
        with mock.patch.object(w.context, "get_tool_variants", return_value=[v1, v2]):
            with mock.patch(
                "rez.wrapper.Printer",
                return_value=lambda msg, col=None: print(msg, file=buf),
            ):
                ret = w.print_package_versions()
        self.assertEqual(ret, 1)
        self.assertIn("Packages (in conflict): pooh-1.0 pooh-2.0", buf.getvalue())

        # Empty variants returns 0
        with mock.patch.object(w.context, "get_tool_variants", return_value=[]):
            self.assertEqual(w.print_package_versions(), 0)

        # Single variant with multiple package versions (current, non-local, local)
        variant = types.SimpleNamespace(
            name="pooh",
            version=2,
            qualified_package_name="pooh-2",
        )
        pkgs = [
            types.SimpleNamespace(
                version=1, qualified_name="pooh-1", path="/repo/pooh/1", is_local=False
            ),
            types.SimpleNamespace(
                version=2, qualified_name="pooh-2", path="/repo/pooh/2", is_local=False
            ),
            types.SimpleNamespace(
                version=3, qualified_name="pooh-3", path="/local/pooh/3", is_local=True
            ),
        ]
        buf = io.StringIO()
        with mock.patch.object(w.context, "get_tool_variants", return_value=[variant]):
            with mock.patch("rez.packages.iter_packages", return_value=iter(pkgs)):
                with mock.patch(
                    "rez.wrapper.Printer",
                    return_value=lambda msg, col=None: print(msg, file=buf),
                ):
                    ret = w.print_package_versions()
        out = buf.getvalue()
        self.assertEqual(ret, 0)
        lines = out.splitlines()
        self.assertEqual(len(lines), 3)
        self.assertIn("  pooh-3", lines[0])
        self.assertIn("(local)", lines[0])
        self.assertIn("* pooh-2", lines[1])
        self.assertIn("  pooh-1", lines[2])

    def test_peek(self) -> None:
        """peek re-resolves context, prints diff, and restores quiet override if REZ_QUIET unset."""
        w = self._make_wrapper()
        with restore_os_environ():
            os.environ.pop("REZ_QUIET", None)
            with mock.patch.object(w.context, "print_resolve_diff") as diff_mock:
                ret = w.peek()

        self.assertEqual(ret, 0)
        self.assertTrue(config.quiet)
        diff_mock.assert_called_once()
        new_ctx = diff_mock.call_args[0][0]
        self.assertIsInstance(new_ctx, ResolvedContext)

        config.remove_override("quiet")
        with restore_os_environ():
            os.environ["REZ_QUIET"] = "true"
            with mock.patch.object(w.context, "print_resolve_diff") as diff_mock:
                ret = w.peek()

        self.assertEqual(ret, 0)
        self.assertNotIn("quiet", config.overrides)
        diff_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
