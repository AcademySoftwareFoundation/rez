# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
extra unit tests for rez.suite
"""
from io import StringIO
import os
import os.path
import unittest
from unittest import mock

from rez.exceptions import ResolvedContextError, SuiteError
from rez.resolved_context import ResolvedContext
from rez.suite import Suite, _FWD__invoke_suite_tool_alias
from rez.tests.util import TempdirMixin, TestBase, restore_os_environ
from rez.utils.filesystem import canonical_path, real_path
from rez.utils.formatting import PackageRequest


class TestSuiteExtra(TestBase, TempdirMixin):
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

    def _make_suite_dir(self, name: str) -> str:
        return os.path.join(self.root, self._testMethodName, name)

    def test_str_and_tools_path(self) -> None:
        s = Suite()
        self.assertEqual(str(s), "Suite()")
        self.assertIsNone(s.tools_path)

        s.add_context("foo", ResolvedContext(["foo"]))
        self.assertEqual(str(s), "Suite(foo)")

        suite_dir = self._make_suite_dir("suite_str")
        s.save(suite_dir)
        s2 = Suite.load(suite_dir)
        self.assertEqual(s2.tools_path, os.path.join(s2.load_path, "bin"))

    def test_activation_shell_code(self) -> None:
        s = Suite()
        s.add_context("foo", ResolvedContext(["foo"]))
        suite_dir = self._make_suite_dir("suite_activate")
        s.save(suite_dir)
        s2 = Suite.load(suite_dir)

        code = s2.activation_shell_code()
        self.assertIn(s2.tools_path, code)

    def test_add_context_errors(self) -> None:
        s = Suite()
        c_foo = ResolvedContext(["foo"])
        s.add_context("foo", c_foo)

        with self.assertRaisesRegex(SuiteError, "Context already in suite"):
            s.add_context("foo", c_foo)

        c_bad = ResolvedContext(["foo", "!foo"])
        self.assertFalse(c_bad.success)
        with self.assertRaisesRegex(SuiteError, "Context is not resolved"):
            s.add_context("bad", c_bad)

    def test_find_contexts(self) -> None:
        pkg_repo = self._make_suite_dir("versioned_repo")
        for ver in ("1.0", "2.0"):
            ver_dir = os.path.join(pkg_repo, "vpkg", ver)
            os.makedirs(ver_dir)
            with open(os.path.join(ver_dir, "package.yaml"), "w") as f:
                f.write("name: vpkg\nversion: '%s'\ntools:\n- vtool\n" % ver)

        self.update_settings({
            "packages_path": [self.data_path("suites", "packages"), pkg_repo]
        })

        s = Suite()
        s.add_context("foo", ResolvedContext(["foo"]))
        s.add_context("bah", ResolvedContext(["bah"]))
        s.add_context("eek", ResolvedContext(["eek"]))
        s.add_context("v2", ResolvedContext(["vpkg==2.0"]))

        self.assertEqual(s.find_contexts(), ["foo", "bah", "eek", "v2"])
        self.assertEqual(s.find_contexts(in_request="foo"), ["foo"])
        self.assertEqual(s.find_contexts(in_request="eek"), ["eek"])
        self.assertEqual(s.find_contexts(in_resolve="eek"), ["bah", "eek"])
        self.assertEqual(
            s.find_contexts(in_resolve=PackageRequest("foo")), ["foo"]
        )
        self.assertEqual(s.find_contexts(in_resolve="!eek"), ["foo", "v2"])
        self.assertEqual(
            s.find_contexts(in_request="bah", in_resolve="eek"), ["bah"]
        )
        self.assertEqual(
            s.find_contexts(in_resolve="!vpkg==1.0"),
            ["foo", "bah", "eek", "v2"],
        )
        self.assertEqual(
            s.find_contexts(in_resolve="!vpkg==2.0"),
            ["foo", "bah", "eek"],
        )

    def test_suffix_and_tool_management_edge_cases(self) -> None:
        s = Suite()
        s.add_context("foo", ResolvedContext(["foo"]))

        s.set_context_suffix("foo", "_sfx")
        self.assertIn("fooer_sfx", s.get_tools())
        s.remove_context_suffix("foo")
        self.assertIn("fooer", s.get_tools())

        # hide_tool twice (second is a no-op)
        s.hide_tool("foo", "fooer")
        s.hide_tool("foo", "fooer")
        self.assertEqual(s.get_tools(), {})

        # unhide_tool when hidden, then again when not hidden
        s.unhide_tool("foo", "fooer")
        s.unhide_tool("foo", "fooer")
        self.assertIn("fooer", s.get_tools())

        # alias_tool twice raises SuiteError
        s.alias_tool("foo", "fooer", "f1")
        with self.assertRaisesRegex(SuiteError, "already aliased"):
            s.alias_tool("foo", "fooer", "f2")

        # unalias_tool on non-aliased tool is a no-op
        s.unalias_tool("foo", "nonexistent")

        # invalid context / tool
        with self.assertRaisesRegex(SuiteError, "No such context"):
            s.context("missing")
        with self.assertRaisesRegex(SuiteError, "No such tool"):
            s.hide_tool("foo", "no_such_tool")

    def test_tool_queries_filepath_context_hidden_conflicts(self) -> None:
        s = Suite()
        c_bah = ResolvedContext(["bah"])
        s.add_context("foo", ResolvedContext(["foo"]))
        s.add_context("bah1", c_bah)
        s.add_context("bah2", c_bah)

        # Unsaved suite returns None for tool filepath
        self.assertIsNone(s.get_tool_filepath("fooer"))
        self.assertIsNone(s.get_tool_filepath("missing_tool"))
        self.assertEqual(s.get_tool_context("fooer"), "foo")
        self.assertIsNone(s.get_tool_context("missing_tool"))

        # Hidden tools
        s.hide_tool("foo", "fooer")
        hidden = s.get_hidden_tools()
        self.assertEqual(len(hidden), 1)
        self.assertEqual(hidden[0]["tool_name"], "fooer")

        # Alias conflicts
        self.assertIsNone(s.get_alias_conflicts("eeker"))
        conflicts = s.get_alias_conflicts("bahbah")
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["context_name"], "bah1")

        # Saved/loaded suite returns filepath in bin dir
        suite_dir = self._make_suite_dir("suite_queries")
        s.save(suite_dir)
        s2 = Suite.load(suite_dir)
        self.assertEqual(
            s2.get_tool_filepath("bahbah"),
            os.path.join(s2.tools_path, "bahbah"),
        )
        self.assertIsNone(s2.get_tool_filepath("missing_tool"))

    def test_validate(self) -> None:
        s = Suite()
        s.add_context("foo", ResolvedContext(["foo"]))
        s.validate()

        ctx = s.context("foo")
        with mock.patch.object(
            ctx, "validate", side_effect=ResolvedContextError("broken ctx")
        ):
            with self.assertRaisesRegex(
                SuiteError, "Error in context 'foo': broken ctx"
            ):
                s.validate()

    def test_to_dict_loaded_flag(self) -> None:
        s = Suite()
        s.add_context("foo", ResolvedContext(["foo"]))
        suite_dir = self._make_suite_dir("suite_todict")
        s.save(suite_dir)

        s2 = Suite.load(suite_dir)
        d1 = s2.to_dict()
        self.assertNotIn("context", d1["contexts"]["foo"])
        self.assertNotIn("loaded", d1["contexts"]["foo"])

        s2.context("foo")
        self.assertTrue(s2.contexts["foo"].get("loaded"))
        d2 = s2.to_dict()
        self.assertNotIn("context", d2["contexts"]["foo"])
        self.assertNotIn("loaded", d2["contexts"]["foo"])

        empty_suite = Suite.from_dict({"contexts": {}})
        self.assertEqual(empty_suite.next_priority, 1)

    def test_save_errors_verbose_and_samefile_fallback(self) -> None:
        existing_dir = self._make_suite_dir("existing_dir")
        os.makedirs(existing_dir)

        # Unsaved suite cannot overwrite existing directory
        s = Suite()
        s.add_context("foo", ResolvedContext(["foo"]))
        with self.assertRaisesRegex(SuiteError, "Cannot save, path exists"):
            s.save(existing_dir)

        # Save to fresh path with verbose=True
        suite_dir = self._make_suite_dir("suite_verbose")
        buf = StringIO()
        with mock.patch("sys.stdout", buf):
            s.save(suite_dir, verbose=True)
        out = buf.getvalue()
        self.assertIn("writing", out)
        self.assertIn("creating alias wrappers", out)
        self.assertIn("creating 'fooer'", out)

        # Loaded suite overwriting itself with verbose=True (loads context first)
        s2 = Suite.load(suite_dir)
        buf2 = StringIO()
        with mock.patch("sys.stdout", buf2):
            s2.save(suite_dir, verbose=True)
        self.assertIn("saving over previous suite...", buf2.getvalue())

        # samefile OSError fallback
        s3 = Suite.load(suite_dir)
        with mock.patch("os.path.samefile", side_effect=OSError("boom")):
            s3.save(real_path(suite_dir))

        # Loaded suite cannot overwrite a different existing directory
        with self.assertRaisesRegex(SuiteError, "Cannot save, path exists"):
            s3.save(existing_dir)

    def test_load_errors(self) -> None:
        missing_dir = self._make_suite_dir("does_not_exist")
        with self.assertRaises(FileNotFoundError):
            Suite.load(missing_dir)

        not_a_suite = self._make_suite_dir("not_a_suite")
        os.makedirs(not_a_suite)
        with self.assertRaisesRegex(SuiteError, "Not a suite"):
            Suite.load(not_a_suite)

        bad_yaml_dir = self._make_suite_dir("bad_yaml")
        os.makedirs(bad_yaml_dir)
        with open(os.path.join(bad_yaml_dir, "suite.yaml"), "w") as f:
            f.write(":\n  - [unclosed\n")
        with self.assertRaisesRegex(SuiteError, "Failed loading suite"):
            Suite.load(bad_yaml_dir)

    def test_visible_suite_paths_and_load_visible_suites(self) -> None:
        s = Suite()
        s.add_context("foo", ResolvedContext(["foo"]))
        suite_dir = self._make_suite_dir("visible_suite")
        s.save(suite_dir)

        other_dir = self._make_suite_dir("other_dir")
        os.makedirs(other_dir)

        bin_dir = os.path.join(suite_dir, "bin")
        paths = [bin_dir, other_dir, os.path.join(self.root, "nonexistent")]
        found = Suite.visible_suite_paths(paths=paths)
        self.assertEqual(found, [suite_dir])

        loaded = Suite.load_visible_suites(paths=paths)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].load_path, real_path(suite_dir))

        with restore_os_environ():
            os.environ["PATH"] = os.pathsep.join([bin_dir, other_dir])
            self.assertEqual(Suite.visible_suite_paths(), [suite_dir])

    def test_print_info(self) -> None:
        s = Suite()
        buf = StringIO()
        s.print_info(buf=buf)
        self.assertEqual(buf.getvalue().strip(), "Suite is empty.")

        s.add_context("foo", ResolvedContext(["foo"]))
        s.add_context("empty_ctx", ResolvedContext([]))

        buf_short = StringIO()
        s.print_info(buf=buf_short, verbose=False)
        self.assertIn("Suite contains 2 contexts:", buf_short.getvalue())
        self.assertIn("empty_ctx foo", buf_short.getvalue())

        buf_verbose = StringIO()
        s.print_info(buf=buf_verbose, verbose=True)
        out = buf_verbose.getvalue()
        self.assertIn("VISIBLE TOOLS", out)
        self.assertIn("1 tools from 1 packages", out)
        self.assertIn("no tools", out)

    def test_print_tools_and_same_context_conflicts(self) -> None:
        repo_dir = self._make_suite_dir("conflict_repo")
        for pkg_name in ("pa", "pb", "pc"):
            pkg_dir = os.path.join(repo_dir, pkg_name)
            os.makedirs(pkg_dir)
            with open(os.path.join(pkg_dir, "package.yaml"), "w") as f:
                f.write("name: %s\ntools:\n- shared_tool\n" % pkg_name)

        self.update_settings({
            "packages_path": [self.data_path("suites", "packages"), repo_dir]
        })

        s = Suite()
        s.add_context("conflict_ctx", ResolvedContext(["pa", "pb", "pc"]))
        s.add_context("empty_ctx", ResolvedContext([]))
        s.add_context("foo", ResolvedContext(["foo"]))
        s.add_context("bah1", ResolvedContext(["bah"]))
        s.add_context("bah2", ResolvedContext(["bah"]))

        tools = s.get_tools()
        self.assertIsInstance(tools["shared_tool"]["variant"], set)
        self.assertEqual(len(tools["shared_tool"]["variant"]), 3)

        s.alias_tool("foo", "fooer", "fooer_alias")
        s.alias_tool("conflict_ctx", "shared_tool", "shared_alias")
        s.hide_tool("bah2", "blacksheep")

        buf_non_verbose = StringIO()
        s.print_tools(buf=buf_non_verbose, verbose=False)
        out_nv = buf_non_verbose.getvalue()
        self.assertIn("(+2 more)", out_nv)
        self.assertIn("fooer_alias", out_nv)
        self.assertIn("shared_alias", out_nv)

        buf_verbose = StringIO()
        s.print_tools(buf=buf_verbose, verbose=True)
        out_v = buf_verbose.getvalue()
        self.assertIn("pa", out_v)
        self.assertIn("pb", out_v)
        self.assertIn("pc", out_v)
        self.assertIn("blacksheep", out_v)

        buf_ctx = StringIO()
        s.print_tools(buf=buf_ctx, context_name="foo")
        self.assertIn("fooer_alias", buf_ctx.getvalue())
        self.assertNotIn("bahbah", buf_ctx.getvalue())

        with self.assertRaisesRegex(SuiteError, "No such context"):
            s.print_tools(buf=StringIO(), context_name="missing")

    @unittest.expectedFailure
    def test_print_tools_empty_suite(self) -> None:
        # Masked bug at src/rez/suite.py:710-714: `rows` is initialized with 2
        # header rows, so `if rows:` is always True and the
        # `else: _pr("No tools available.")` branch is unreachable dead code.
        s = Suite()
        buf_empty = StringIO()
        s.print_tools(buf=buf_empty)
        self.assertIn("No tools available.", buf_empty.getvalue())

    @unittest.expectedFailure
    def test_print_tools_status_labels(self) -> None:
        # Masked bug at src/rez/suite.py:696-706 (with :781-782): print_tools()
        # checks `"hidden" in entry` / `"conflicting" in entry` by key presence
        # instead of truthiness, labeling every tool `(hidden)` and leaving
        # `(not visible)`, `(aliased)`, and `(in conflict)` rows unreachable.
        repo_dir = self._make_suite_dir("status_labels_repo")
        for pkg_name in ("pa", "pb", "pc"):
            pkg_dir = os.path.join(repo_dir, pkg_name)
            os.makedirs(pkg_dir)
            with open(os.path.join(pkg_dir, "package.yaml"), "w") as f:
                f.write("name: %s\ntools:\n- shared_tool\n" % pkg_name)

        self.update_settings({
            "packages_path": [self.data_path("suites", "packages"), repo_dir]
        })

        s = Suite()
        s.add_context("conflict_ctx", ResolvedContext(["pa", "pb", "pc"]))
        s.add_context("foo", ResolvedContext(["foo"]))
        s.add_context("bah1", ResolvedContext(["bah"]))
        s.add_context("bah2", ResolvedContext(["bah"]))

        s.alias_tool("foo", "fooer", "fooer_alias")
        s.alias_tool("conflict_ctx", "shared_tool", "shared_alias")
        s.hide_tool("bah2", "blacksheep")

        buf_verbose = StringIO()
        s.print_tools(buf=buf_verbose, verbose=True)
        lines = buf_verbose.getvalue().splitlines()

        fooer_lines = [ln for ln in lines if "fooer_alias" in ln]
        self.assertEqual(len(fooer_lines), 1)
        self.assertIn("(aliased)", fooer_lines[0])
        self.assertNotIn("(hidden)", fooer_lines[0])

        shared_lines = [ln for ln in lines if "shared_alias" in ln]
        self.assertEqual(len(shared_lines), 1)
        self.assertIn("(in conflict) (aliased)", shared_lines[0])
        self.assertNotIn("(hidden)", shared_lines[0])

        bah1_bahbah_lines = [ln for ln in lines if "bahbah" in ln and "bah1" in ln]
        self.assertEqual(len(bah1_bahbah_lines), 1)
        self.assertIn("(not visible)", bah1_bahbah_lines[0])
        self.assertNotIn("(hidden)", bah1_bahbah_lines[0])

        bah2_blacksheep_lines = [
            ln for ln in lines if "blacksheep" in ln and "bah2" in ln
        ]
        self.assertEqual(len(bah2_blacksheep_lines), 1)
        self.assertIn("(hidden)", bah2_blacksheep_lines[0])

    def test_fwd_invoke_suite_tool_alias(self) -> None:
        s = Suite()
        s.add_context("foo", ResolvedContext(["foo"]))
        suite_dir = self._make_suite_dir("fwd_suite")
        s.save(suite_dir)

        script = os.path.join(suite_dir, "bin", "fooer")
        mock_wrapper = mock.MagicMock()
        mock_wrapper.run.return_value = 7

        class _FakeWrapper:
            def __new__(cls):
                return mock_wrapper

        with mock.patch("rez.wrapper.Wrapper", _FakeWrapper):
            with self.assertRaises(SystemExit) as cm:
                _FWD__invoke_suite_tool_alias(
                    "foo",
                    "fooer",
                    prefix_char="-",
                    _script=script,
                    _cli_args=["--flag"],
                )

        self.assertEqual(cm.exception.code, 7)
        mock_wrapper._init.assert_called_once()
        init_args = mock_wrapper._init.call_args[0]
        self.assertEqual(canonical_path(init_args[0]), canonical_path(suite_dir))
        self.assertEqual(init_args[1], "foo")
        self.assertIsInstance(init_args[2], ResolvedContext)
        self.assertEqual(init_args[3], "fooer")
        self.assertEqual(init_args[4], "-")
        mock_wrapper.run.assert_called_once_with("--flag")


if __name__ == "__main__":
    unittest.main()
