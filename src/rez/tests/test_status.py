# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
unit tests for the 'status' module
"""
import io
import os
import unittest
from unittest import mock

from rez import __version__
from rez.packages import Package
from rez.status import Status, status
from rez.tests.util import TempdirMixin, TestBase, restore_os_environ
from rez.version import Version


def _make_variant(pkg_name, version_str, uri="/repo/pkg", is_local=False):
    variant = mock.MagicMock()
    variant.qualified_package_name = "%s-%s" % (pkg_name, version_str)
    variant.version = Version(version_str)
    variant.uri = uri
    variant.is_local = is_local
    return variant


def _make_package(pkg_name, version_str, uri="/repo/pkg", is_local=False):
    pkg = mock.MagicMock(spec=Package)
    pkg.qualified_name = "%s-%s" % (pkg_name, version_str)
    pkg.version = Version(version_str)
    pkg.uri = uri
    pkg.is_local = is_local
    return pkg


class TestStatusProperties(TestBase):
    def test_singleton_instance(self):
        self.assertIsInstance(status, Status)

    def test_context_file_unset(self):
        with restore_os_environ():
            os.environ.pop("REZ_RXT_FILE", None)
            s = Status()
            self.assertIsNone(s.context_file)
            self.assertIsNone(s.context)

    def test_context_file_set_and_context_loaded(self):
        mock_ctx = mock.MagicMock()
        with restore_os_environ():
            os.environ["REZ_RXT_FILE"] = "/tmp/example.rxt"
            s = Status()
            self.assertEqual(s.context_file, "/tmp/example.rxt")
            with mock.patch("rez.status.ResolvedContext.load", return_value=mock_ctx) as mock_load:
                ctx = s.context
                self.assertIs(ctx, mock_ctx)
                mock_load.assert_called_once_with("/tmp/example.rxt")

    def test_suites(self):
        fake_suites = [mock.MagicMock(), mock.MagicMock()]
        with mock.patch("rez.status.Suite.load_visible_suites", return_value=fake_suites) as mock_load:
            s = Status()
            self.assertEqual(s.suites, fake_suites)
            mock_load.assert_called_once_with()

    def test_parent_suite_none_without_context(self):
        with restore_os_environ():
            os.environ.pop("REZ_RXT_FILE", None)
            s = Status()
            self.assertIsNone(s.parent_suite)
            self.assertIsNone(s.active_suite_context_name)

    def test_parent_suite_none_without_parent_suite_path(self):
        mock_ctx = mock.MagicMock(parent_suite_path=None, suite_context_name=None)
        s = Status()
        s.context = mock_ctx
        self.assertIsNone(s.parent_suite)
        self.assertIsNone(s.active_suite_context_name)

    def test_parent_suite_and_active_suite_context_name(self):
        mock_ctx = mock.MagicMock(
            parent_suite_path="/suites/my_suite",
            suite_context_name="dev_ctx",
        )
        mock_suite = mock.MagicMock()
        s = Status()
        s.context = mock_ctx
        with mock.patch("rez.status.Suite.load", return_value=mock_suite) as mock_load:
            self.assertIs(s.parent_suite, mock_suite)
            mock_load.assert_called_once_with("/suites/my_suite")
        self.assertEqual(s.active_suite_context_name, "dev_ctx")


class TestStatusPrintInfo(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        TempdirMixin.setUpClass()

    @classmethod
    def tearDownClass(cls):
        TempdirMixin.tearDownClass()
        super().tearDownClass()

    def test_print_info_no_obj_empty_env(self):
        s = Status()
        s.context = None
        s.suites = []
        s.parent_suite = None
        buf = io.StringIO()
        result = s.print_info(buf=buf)
        out = buf.getvalue()
        self.assertTrue(result)
        self.assertIn("Using Rez v%s" % __version__, out)
        self.assertIn("No active context.", out)
        self.assertIn("No visible suites.", out)

    def test_print_info_no_obj_with_context_suites_and_parent_suite(self):
        s = Status()
        s.context = mock.MagicMock(load_path="/tmp/active.rxt")
        suite1 = mock.MagicMock(load_path="/suites/s1")
        suite2 = mock.MagicMock(load_path="/suites/s2")
        s.suites = [suite1, suite2]
        s.parent_suite = mock.MagicMock(load_path="/suites/parent")
        s.active_suite_context_name = "tool_ctx"

        buf = io.StringIO()
        result = s.print_info(buf=buf)
        out = buf.getvalue()
        self.assertTrue(result)
        self.assertIn("Active Context: /tmp/active.rxt", out)
        self.assertIn("2 visible suites:", out)
        self.assertIn("/suites/s1", out)
        self.assertIn("/suites/s2", out)
        self.assertIn("Currently within context 'tool_ctx' in suite at /suites/parent", out)

    def test_print_info_no_obj_context_without_load_path(self):
        s = Status()
        s.context = mock.MagicMock(load_path=None)
        s.suites = []
        s.parent_suite = None

        buf = io.StringIO()
        result = s.print_info(buf=buf)
        out = buf.getvalue()
        self.assertTrue(result)
        self.assertIn("In Active Context.", out)

    def test_print_info_unknown_object(self):
        s = Status()
        s.context = None
        s.suites = []
        buf = io.StringIO()
        with mock.patch("rez.status.which", return_value=None), mock.patch(
            "rez.status.iter_packages", return_value=iter([])
        ):
            result = s.print_info("nonexistent_thing_xyz", buf=buf)
        self.assertFalse(result)
        self.assertIn("Rez does not know what 'nonexistent_thing_xyz' is", buf.getvalue())

    def test_print_info_matching_object_multiple_handlers(self):
        s = Status()
        s.context = None
        s.suites = []
        pkg = _make_package("mytool", "1.0.0")
        tool_path = os.path.join(self.root, "mytool")
        with open(tool_path, "w") as f:
            f.write("#!/bin/sh\n")

        mock_wrapper = mock.MagicMock()
        buf = io.StringIO()
        with mock.patch("rez.status.which", return_value=tool_path), mock.patch(
            "rez.status.Wrapper", return_value=mock_wrapper
        ), mock.patch("rez.status.iter_packages", return_value=iter([pkg])):
            result = s.print_info("mytool", buf=buf)

        out = buf.getvalue()
        self.assertTrue(result)
        self.assertIn("'mytool' is a suite tool:", out)
        self.assertIn("'mytool' is also a package.", out)
        mock_wrapper.print_about.assert_called_once_with()


class TestStatusPrintTools(TestBase):
    def test_print_tools_no_tools(self):
        s = Status()
        s.context = None
        s.suites = []
        buf = io.StringIO()
        result = s.print_tools(buf=buf)
        self.assertFalse(result)
        self.assertIn("No matching tools.", buf.getvalue())

    def test_print_tools_from_context_with_pattern_and_conflicts(self):
        v1 = _make_variant("alpha", "1.0")
        v2 = _make_variant("beta", "2.0")
        mock_ctx = mock.MagicMock()
        mock_ctx.get_tools.return_value = {
            "k1": (v1, ["tool_ok", "tool_conflict"]),
            "k2": (v2, ["other_cmd"]),
        }
        mock_ctx.get_conflicting_tools.return_value = {"tool_conflict": ["a", "b"]}

        s = Status()
        s.context = mock_ctx
        s.suites = []

        buf = io.StringIO()
        result = s.print_tools(buf=buf)
        out = buf.getvalue()
        self.assertTrue(result)
        self.assertIn("TOOL", out)
        self.assertIn("tool_ok", out)
        self.assertIn("tool_conflict", out)
        self.assertIn("(in conflict)", out)
        self.assertIn("other_cmd", out)
        self.assertIn("active context", out)

        buf_filtered = io.StringIO()
        result_filtered = s.print_tools(pattern="tool_*", buf=buf_filtered)
        out_filtered = buf_filtered.getvalue()
        self.assertTrue(result_filtered)
        self.assertIn("tool_ok", out_filtered)
        self.assertIn("tool_conflict", out_filtered)
        self.assertNotIn("other_cmd", out_filtered)

    def test_print_tools_from_suites(self):
        v_ctx = _make_variant("ctxpkg", "1.0")
        mock_ctx = mock.MagicMock()
        mock_ctx.get_tools.return_value = {"k": (v_ctx, ["s_seen"])}
        mock_ctx.get_conflicting_tools.return_value = {}

        v_suite = _make_variant("suitepkg", "3.0")
        mock_suite = mock.MagicMock()
        mock_suite.load_path = "/suites/prod"
        mock_suite.tools_path = "/suites/prod/bin"
        mock_suite.get_tools.return_value = {
            "s_seen": {"variant": v_suite, "tool_name": "s_seen", "context_name": "c1"},
            "skip_me": {"variant": v_suite, "tool_name": "skip_me", "context_name": "c1"},
            "s_normal": {"variant": v_suite, "tool_name": "s_normal", "context_name": "c1"},
            "s_alias": {"variant": v_suite, "tool_name": "orig_bin", "context_name": "c1"},
        }

        def fake_which(name):
            if name == "s_normal":
                return os.path.join("/suites/prod/bin", "s_normal")
            if name == "s_alias":
                return "/usr/local/bin/s_alias"
            return None

        s = Status()
        s.context = mock_ctx
        s.suites = [mock_suite]

        buf = io.StringIO()
        with mock.patch("rez.status.which", side_effect=fake_which):
            result = s.print_tools(pattern="s_*", buf=buf)

        out = buf.getvalue()
        self.assertTrue(result)
        self.assertIn("s_normal", out)
        self.assertIn("s_alias", out)
        self.assertIn("orig_bin", out)
        self.assertIn("(hidden by unknown tool '/usr/local/bin/s_alias')", out)
        self.assertNotIn("skip_me", out)

    @unittest.expectedFailure
    def test_print_tools_from_suites_conflict(self):
        # Known bug at src/rez/status.py:174: `", ".join(variant)` raises
        # TypeError when Suite.get_tools() returns a set[Variant] on conflict.
        mock_suite = mock.MagicMock()
        mock_suite.load_path = "/suites/prod"
        mock_suite.tools_path = "/suites/prod/bin"
        mock_suite.get_tools.return_value = {
            "s_conflict": {
                "variant": {_make_variant("pkgA", "1.0"), _make_variant("pkgB", "1.0")},
                "tool_name": "s_conflict",
                "context_name": "c2",
            },
        }

        s = Status()
        s.context = None
        s.suites = [mock_suite]

        buf = io.StringIO()
        with mock.patch("rez.status.which", return_value=None):
            result = s.print_tools(pattern="s_*", buf=buf)

        out = buf.getvalue()
        self.assertTrue(result)
        self.assertIn("s_conflict", out)
        self.assertIn("(in conflict)", out)
        self.assertIn("pkgA-1.0", out)
        self.assertIn("pkgB-1.0", out)


class TestStatusPrintToolInfo(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        TempdirMixin.setUpClass()

    @classmethod
    def tearDownClass(cls):
        TempdirMixin.tearDownClass()
        super().tearDownClass()

    def test_tool_info_missing_and_directory(self):
        s = Status()
        s.context = None
        s.suites = []
        buf = io.StringIO()

        with mock.patch("rez.status.which", return_value=None):
            self.assertFalse(s._print_tool_info("no_such_tool", buf=buf))
        self.assertFalse(s._print_tool_info(os.path.join(self.root, "missing"), buf=buf))
        self.assertFalse(s._print_tool_info(self.root, buf=buf))

    def test_tool_info_context_single_and_conflicting_variants(self):
        tool_path = os.path.join(self.root, "ctx_tool")
        with open(tool_path, "w") as f:
            f.write("#!/bin/sh\n")

        v1 = _make_variant("pkg_one", "1.0")
        v2 = _make_variant("pkg_two", "2.0")
        mock_ctx = mock.MagicMock(load_path="/tmp/ctx.rxt")
        mock_ctx.get_tool_variants.return_value = [v1]

        s = Status()
        s.context = mock_ctx
        s.suites = []

        buf = io.StringIO()
        with mock.patch("rez.status.Wrapper", side_effect=Exception("not a wrapper")):
            self.assertTrue(s._print_tool_info(tool_path, buf=buf))
        out = buf.getvalue()
        self.assertIn("'ctx_tool' is a tool in the active context:", out)
        self.assertIn("Tool:     ctx_tool", out)
        self.assertIn("Context:  /tmp/ctx.rxt", out)
        self.assertIn("Package:  pkg_one-1.0", out)

        mock_ctx.get_tool_variants.return_value = [v1, v2]
        mock_ctx.load_path = None
        buf2 = io.StringIO()
        with mock.patch("rez.status.Wrapper", side_effect=Exception("not a wrapper")):
            self.assertTrue(s._print_tool_info(tool_path, buf=buf2, b=True))
        out2 = buf2.getvalue()
        self.assertIn("'ctx_tool' is also a tool in the active context:", out2)
        self.assertNotIn("Context:", out2)
        self.assertIn("Packages (in conflict): pkg_one-1.0 pkg_two-2.0", out2)

        # Pathed tool not in context -> returns False (covers 237->254 and 254->265)
        mock_ctx.get_tool_variants.return_value = []
        buf3 = io.StringIO()
        with mock.patch("rez.status.Wrapper", side_effect=Exception("not a wrapper")):
            self.assertFalse(s._print_tool_info(tool_path, buf=buf3))

    def test_tool_info_hidden_suite_wrapper(self):
        unknown_dir = os.path.join(self.root, "unknown_bin")
        suite_dir = os.path.join(self.root, "suite_bin")
        os.makedirs(unknown_dir, exist_ok=True)
        os.makedirs(suite_dir, exist_ok=True)

        unknown_tool = os.path.join(unknown_dir, "hidden_tool")
        suite_tool = os.path.join(suite_dir, "hidden_tool")
        for p in (unknown_tool, suite_tool):
            with open(p, "w") as f:
                f.write("#!/bin/sh\n")

        mock_wrapper = mock.MagicMock()

        def wrapper_factory(path):
            if path == suite_tool:
                return mock_wrapper
            raise RuntimeError("not a wrapper")

        mock_suite = mock.MagicMock(tools_path=suite_dir)
        s = Status()
        s.context = None
        s.suites = [mock_suite]

        buf = io.StringIO()
        with mock.patch("rez.status.which", return_value=unknown_tool), mock.patch(
            "rez.status.Wrapper", side_effect=wrapper_factory
        ):
            result = s._print_tool_info("hidden_tool", buf=buf)

        self.assertTrue(result)
        self.assertIn(
            "'hidden_tool' is a suite tool, but is hidden by an unknown tool '%s':" % unknown_tool,
            buf.getvalue(),
        )
        mock_wrapper.print_about.assert_called_once_with()

    def test_tool_info_unpathed_not_in_any_suite(self):
        unknown_tool = os.path.join(self.root, "plain_tool")
        with open(unknown_tool, "w") as f:
            f.write("#!/bin/sh\n")

        empty_suite_dir = os.path.join(self.root, "empty_suite_bin")
        os.makedirs(empty_suite_dir, exist_ok=True)

        s = Status()
        s.context = None
        s.suites = [mock.MagicMock(tools_path=empty_suite_dir)]
        buf = io.StringIO()
        with mock.patch("rez.status.which", return_value=unknown_tool), mock.patch(
            "rez.status.Wrapper", side_effect=RuntimeError("not a wrapper")
        ):
            self.assertFalse(s._print_tool_info("plain_tool", buf=buf))
        self.assertEqual(buf.getvalue(), "")

    @unittest.expectedFailure
    def test_tool_info_unpathed_non_wrapper_in_suite(self):
        # Known bug at src/rez/status.py:263: `return True` is misindented
        # outside `if w:`, causing non-wrapper files in suite.tools_path to
        # silently return True instead of False.
        unknown_tool = os.path.join(self.root, "plain_tool")
        with open(unknown_tool, "w") as f:
            f.write("#!/bin/sh\n")

        bad_wrapper_suite_dir = os.path.join(self.root, "bad_wrapper_suite_bin")
        os.makedirs(bad_wrapper_suite_dir, exist_ok=True)
        with open(os.path.join(bad_wrapper_suite_dir, "plain_tool"), "w") as f:
            f.write("#!/bin/sh\n")

        s = Status()
        s.context = None
        s.suites = [mock.MagicMock(tools_path=bad_wrapper_suite_dir)]
        buf = io.StringIO()
        with mock.patch("rez.status.which", return_value=unknown_tool), mock.patch(
            "rez.status.Wrapper", side_effect=RuntimeError("not a wrapper")
        ):
            self.assertFalse(s._print_tool_info("plain_tool", buf=buf))

        buf_info = io.StringIO()
        with mock.patch("rez.status.which", return_value=unknown_tool), mock.patch(
            "rez.status.Wrapper", side_effect=RuntimeError("not a wrapper")
        ), mock.patch("rez.status.iter_packages", return_value=iter([])):
            self.assertFalse(s.print_info("plain_tool", buf=buf_info))
        self.assertIn("Rez does not know what 'plain_tool' is", buf_info.getvalue())


class TestStatusPrintPackageInfo(TestBase):
    def test_package_info_invalid_requests(self):
        s = Status()
        s.context = None
        buf = io.StringIO()
        self.assertFalse(s._print_package_info("dir/pkg", buf=buf))
        self.assertFalse(s._print_package_info("!!!invalid", buf=buf))
        self.assertFalse(s._print_package_info("!conflict_pkg", buf=buf))

    def test_package_info_in_active_context(self):
        variant = _make_variant("foo", "1.2.0", uri="/local/foo/1.2.0", is_local=True)
        mock_ctx = mock.MagicMock(load_path="/tmp/ctx.rxt")
        mock_ctx.get_resolved_package.return_value = variant

        s = Status()
        s.context = mock_ctx
        buf = io.StringIO()
        result = s._print_package_info("foo-1+", buf=buf)

        out = buf.getvalue()
        self.assertTrue(result)
        self.assertIn("'foo' is a package in the active context:", out)
        self.assertIn("Package:  foo-1.2.0", out)
        self.assertIn("URI:      /local/foo/1.2.0  (local)", out)
        self.assertIn("Context:  /tmp/ctx.rxt", out)

        # Context without load_path
        mock_ctx.load_path = None
        buf2 = io.StringIO()
        self.assertTrue(s._print_package_info("foo-1+", buf=buf2))
        self.assertNotIn("Context:", buf2.getvalue())

        # Version in context does not match requested range -> falls back to iter_packages
        buf3 = io.StringIO()
        with mock.patch("rez.status.iter_packages", return_value=iter([])):
            self.assertFalse(s._print_package_info("foo-2+", buf=buf3))

    def test_package_info_from_repository(self):
        p1 = _make_package("bar", "1.0.0", uri="/repo/bar/1.0.0", is_local=False)
        p2 = _make_package("bar", "2.0.0", uri="/repo/bar/2.0.0", is_local=False)

        s = Status()
        s.context = None

        buf = io.StringIO()
        with mock.patch("rez.status.iter_packages", return_value=iter([p1, p2])):
            self.assertTrue(s._print_package_info("bar", buf=buf))
        out = buf.getvalue()
        self.assertIn("'bar' is a package. The latest version is:", out)
        self.assertIn("Package:  bar-2.0.0", out)
        self.assertIn("URI:      /repo/bar/2.0.0", out)

        buf2 = io.StringIO()
        with mock.patch("rez.status.iter_packages", return_value=iter([p1])):
            self.assertTrue(s._print_package_info("bar-1+<2", buf=buf2, b=True))
        out2 = buf2.getvalue()
        self.assertIn("'bar' is also a package. The latest version in the range '1+<2' is:", out2)
        self.assertIn("Package:  bar-1.0.0", out2)

    def test_package_info_not_found(self):
        s = Status()
        s.context = None
        buf = io.StringIO()
        with mock.patch("rez.status.iter_packages", return_value=iter([])):
            self.assertFalse(s._print_package_info("nonexistent_pkg", buf=buf))


class TestStatusPrintSuiteAndContextInfo(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        TempdirMixin.setUpClass()

    @classmethod
    def tearDownClass(cls):
        TempdirMixin.tearDownClass()
        super().tearDownClass()

    def test_suite_info(self):
        s = Status()
        buf = io.StringIO()

        # Not a directory
        file_path = os.path.join(self.root, "not_a_suite.txt")
        with open(file_path, "w") as f:
            f.write("x")
        self.assertFalse(s._print_suite_info(file_path, buf=buf))

        # Directory, but Suite.load fails
        with mock.patch("rez.status.Suite.load", side_effect=RuntimeError("bad suite")):
            self.assertFalse(s._print_suite_info(self.root, buf=buf))

        # Valid suite directory
        with mock.patch("rez.status.Suite.load", return_value=mock.MagicMock()):
            self.assertTrue(s._print_suite_info(self.root, buf=buf))
        self.assertIn(
            "'%s' is a suite. Use 'rez-suite' for more information." % os.path.abspath(self.root),
            buf.getvalue(),
        )

    def test_context_info(self):
        s = Status()
        buf = io.StringIO()

        # Not a file
        self.assertFalse(s._print_context_info(self.root, buf=buf))

        # File, but ResolvedContext.load fails
        ctx_file = os.path.join(self.root, "test.rxt")
        with open(ctx_file, "w") as f:
            f.write("{}")
        with mock.patch("rez.status.ResolvedContext.load", side_effect=RuntimeError("bad ctx")):
            self.assertFalse(s._print_context_info(ctx_file, buf=buf))

        # Valid context file
        with mock.patch("rez.status.ResolvedContext.load", return_value=mock.MagicMock()):
            self.assertTrue(s._print_context_info(ctx_file, buf=buf))
        self.assertIn(
            "'%s' is a context. Use 'rez-context' for more information." % os.path.abspath(ctx_file),
            buf.getvalue(),
        )
