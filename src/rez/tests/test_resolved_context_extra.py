# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Additional unit tests for rez.resolved_context covering serialization,
diffing, printing, patching, retargeting, graphs, bundling, package caching,
context tracking, and shell execution paths.
"""

from io import StringIO
import os
import shutil
import subprocess
import sys
import types
import unittest
from unittest import mock

from rez.exceptions import (
    PackageCommandError,
    PackageNotFoundError,
    ResolvedContextError,
    RezError,
)
from rez.package_filter import PackageFilterList
from rez.package_order import SortedOrder
from rez.package_repository import package_repository_manager
from rez.packages import Package
from rez.plugin_managers import plugin_manager
from rez.resolved_context import (
    PatchLock,
    ResolvedContext,
    get_lock_request,
)
from rez.rex import Action, Setenv
from rez.solver import SolverCallbackReturn
from rez.system import system
from rez.tests.util import TempdirMixin, TestBase, restore_os_environ, restore_sys_path
from rez.utils.filesystem import canonical_path
from rez.utils.formatting import PackageRequest
from rez.version import Version


def _make_memory_repo(packages_data: dict) -> str:
    """Create a memory package repository URI populated with ``packages_data``."""
    mem_path = "memory@%s" % hex(id(packages_data))
    repo = package_repository_manager.get_repository(mem_path)
    repo.data = packages_data
    return mem_path


def _write_fs_package(repo_path: str, name: str, version: str, extra: str = "") -> None:
    """Write a minimal filesystem package.py under ``repo_path/name/version``."""
    pkg_dir = os.path.join(repo_path, name, version)
    os.makedirs(pkg_dir, exist_ok=True)
    content = (
        f"name = {name!r}\n"
        f"version = {version!r}\n"
        f"{extra}\n"
    )
    with open(os.path.join(pkg_dir, "package.py"), "w", encoding="utf-8") as f:
        f.write(content)


class TestGetLockRequest(TestBase):
    """Tests for get_lock_request()."""

    def test_lock_exact_weak_and_strong(self) -> None:
        v = Version("1.2.3.4")
        self.assertEqual(
            str(get_lock_request("foo", v, PatchLock.lock, weak=True)),
            "~foo==1.2.3.4",
        )
        self.assertEqual(
            str(get_lock_request("foo", v, PatchLock.lock, weak=False)),
            "foo==1.2.3.4",
        )

    def test_no_lock_and_empty_version(self) -> None:
        self.assertIsNone(get_lock_request("foo", Version("1.2.3"), PatchLock.no_lock))
        self.assertIsNone(get_lock_request("foo", Version(""), PatchLock.lock_2))

    def test_rank_locks(self) -> None:
        v = Version("1.2.3.4")
        self.assertEqual(
            str(get_lock_request("foo", v, PatchLock.lock_2)),
            "~foo-1",
        )
        self.assertEqual(
            str(get_lock_request("foo", v, PatchLock.lock_3)),
            "~foo-1.2",
        )
        self.assertEqual(
            str(get_lock_request("foo", v, PatchLock.lock_4, weak=False)),
            "foo-1.2.3",
        )


class TestResolvedContextMemory(TestBase):
    """Tests for ResolvedContext using fast in-memory package repositories."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.pkg_data = {
            "pkg_a": {
                "1.0.0": {
                    "name": "pkg_a",
                    "version": "1.0.0",
                    "tools": ["tool_a", "shared_tool"],
                    "requires": ["pkg_b-1+", "!conflict_pkg"],
                },
                "2.0.0": {
                    "name": "pkg_a",
                    "version": "2.0.0",
                    "tools": ["tool_a", "shared_tool"],
                    "requires": ["pkg_b-1+"],
                },
            },
            "pkg_b": {
                "1.0.0": {
                    "name": "pkg_b",
                    "version": "1.0.0",
                    "tools": ["tool_b", "shared_tool"],
                },
                "1.5.0": {
                    "name": "pkg_b",
                    "version": "1.5.0",
                    "tools": ["tool_b", "shared_tool"],
                },
                "2.0.0": {
                    "name": "pkg_b",
                    "version": "2.0.0",
                    "tools": ["tool_b", "shared_tool"],
                },
            },
            "pkg_c": {
                "1.0.0": {
                    "name": "pkg_c",
                    "version": "1.0.0",
                },
            },
            "pkg_no_tools": {
                "1.0.0": {
                    "name": "pkg_no_tools",
                    "version": "1.0.0",
                },
            },
            "imp_pkg": {
                "1.0.0": {
                    "name": "imp_pkg",
                    "version": "1.0.0",
                },
            },
        }
        cls.mem_path = "memory@%s" % hex(id(cls.pkg_data))
        cls.settings = dict(
            packages_path=[cls.mem_path],
            package_filter=None,
            implicit_packages=[],
            warn_untimestamped=False,
            resolve_caching=False,
        )

    def setUp(self) -> None:
        super().setUp()
        repo = package_repository_manager.get_repository(self.mem_path)
        repo.data = self.pkg_data

    def test_callback_max_fails_time_limit_and_custom(self) -> None:
        state = types.SimpleNamespace(num_fails=3)
        cb_fails = ResolvedContext.Callback(max_fails=3, time_limit=-1, callback=None)
        status, reason = cb_fails(state)
        self.assertEqual(status, SolverCallbackReturn.fail)
        self.assertIn("fail limit reached", reason)

        with mock.patch("rez.resolved_context.time.time", side_effect=[100.0, 105.0]):
            cb_time = ResolvedContext.Callback(max_fails=-1, time_limit=2, callback=None)
            status, reason = cb_time(types.SimpleNamespace(num_fails=0))
        self.assertEqual(status, SolverCallbackReturn.abort)
        self.assertEqual(reason, "time limit exceeded")

        custom = mock.Mock(return_value=(SolverCallbackReturn.keep_going, "ok"))
        cb_custom = ResolvedContext.Callback(max_fails=-1, time_limit=-1, callback=custom)
        self.assertEqual(
            cb_custom(types.SimpleNamespace(num_fails=0)),
            (SolverCallbackReturn.keep_going, "ok"),
        )
        custom.assert_called_once()

    def test_package_load_callback_and_on_success_guard(self) -> None:
        loaded = []

        def on_load(pkg: Package) -> None:
            loaded.append(pkg.name)

        ctx = ResolvedContext(["pkg_a-1.0.0"], package_load_callback=on_load)
        self.assertTrue(ctx.success)
        self.assertIn("pkg_a", loaded)
        self.assertGreater(ctx.num_loaded_packages, 0)

        failed = ResolvedContext(["pkg_a-1.0.0", "!pkg_b-1+"])
        self.assertFalse(failed.success)
        with self.assertRaises(ResolvedContextError):
            failed.get_environ()

        # copy() and get_actions() and apply()
        ctx_copy = ctx.copy()
        self.assertEqual(ctx_copy, ctx)
        actions = ctx.get_actions()
        self.assertTrue(actions)
        self.assertTrue(all(isinstance(a, Action) for a in actions))
        setenv_actions = {a.key: str(a.value) for a in actions if isinstance(a, Setenv)}
        self.assertEqual(setenv_actions.get("REZ_PKG_A_VERSION"), "1.0.0")
        self.assertEqual(setenv_actions.get("REZ_PKG_B_VERSION"), "2.0.0")
        self.assertIn("pkg_a-1.0.0", setenv_actions.get("REZ_USED_RESOLVE", ""))

        with restore_os_environ(), restore_sys_path():
            for key in ("REZ_USED_RESOLVE", "REZ_PKG_A_VERSION", "REZ_PKG_B_VERSION"):
                os.environ.pop(key, None)
            ctx.apply()
            self.assertIn("pkg_a-1.0.0", os.environ.get("REZ_USED_RESOLVE", ""))
            self.assertEqual(os.environ.get("REZ_PKG_A_VERSION"), "1.0.0")
            self.assertEqual(os.environ.get("REZ_PKG_B_VERSION"), "2.0.0")

    def test_str_hash_and_requested_packages(self) -> None:
        self.update_settings({"implicit_packages": ["~imp_pkg"]})
        ctx = ResolvedContext(["pkg_a-1.0.0"])
        s = str(ctx)
        self.assertIn("solved(", s)
        self.assertIn("pkg_a-1.0.0", s)
        self.assertEqual([str(x) for x in ctx.requested_packages(include_implicit=False)], ["pkg_a-1.0.0"])
        self.assertEqual(
            [str(x) for x in ctx.requested_packages(include_implicit=True)],
            ["pkg_a-1.0.0", "~imp_pkg"],
        )

        ctx2 = ResolvedContext(["pkg_a-1.0.0"])
        self.assertEqual(hash(ctx), hash(ctx2))

        failed = ResolvedContext(["pkg_a-1.0.0", "!pkg_b-1+"])
        self.assertIn("ResolvedContext:failed(", str(failed))
        self.assertIsInstance(hash(failed), int)

    def test_get_patched_request(self) -> None:
        ctx = ResolvedContext(["pkg_a-1.0.0", "~pkg_c-1"])

        # strict=True uses resolved packages
        strict_req = [str(x) for x in ctx.get_patched_request(strict=True)]
        self.assertIn("pkg_a-1.0.0", strict_req)
        self.assertIn("pkg_b-2.0.0", strict_req)

        # ^subtraction, package_subtractions, overrides (same type vs diff type), new pkg
        patched = ctx.get_patched_request(
            package_requests=["^pkg_c", "pkg_a-2.0.0", "!pkg_a-1.0.0", "pkg_no_tools"],
            package_subtractions=[],
            strict=False,
            rank=0,
        )
        patched_strs = [str(x) for x in patched]
        self.assertNotIn("~pkg_c-1", patched_strs)
        self.assertIn("pkg_a-2.0.0", patched_strs)
        self.assertIn("!pkg_a-1.0.0", patched_strs)
        self.assertIn("pkg_no_tools", patched_strs)

        # rank > 1 with PackageRequest objects (avoids str.conflict bug at line 673)
        patched_rank = ctx.get_patched_request(
            package_requests=[PackageRequest("pkg_a-2.0.0")],
            strict=False,
            rank=2,
        )
        # pkg_b was not overridden so rank=2 adds ~pkg_b<2_
        self.assertIn("~pkg_b<2_", [str(x) for x in patched_rank])

        # Weak override replaces weak request
        patched_weak = ctx.get_patched_request(package_requests=[PackageRequest("~pkg_c-1.0")])
        self.assertIn("~pkg_c-1.0", [str(x) for x in patched_weak])

    def test_graph_variants(self) -> None:
        ctx = ResolvedContext(["pkg_a-1.0.0"])
        dot_str = ctx.graph(as_dot=True)
        self.assertIn("digraph", dot_str)

        # Compact graph_string -> graph() and graph(as_dot=True)
        d = ctx.to_dict()
        ctx_from_dict = ResolvedContext.from_dict(d)
        self.assertIsNone(ctx_from_dict.graph_)
        g = ctx_from_dict.graph(as_dot=False)
        self.assertIsNotNone(g)

        ctx_from_dict2 = ResolvedContext.from_dict(d)
        dot_from_compact = ctx_from_dict2.graph(as_dot=True)
        self.assertIn("digraph", dot_from_compact)

        # Legacy dot graph_string (non-'{')
        ctx_from_dict2.graph_ = None
        ctx_from_dict2.graph_string = "digraph legacy { a -> b; }"
        self.assertEqual(ctx_from_dict2.graph(as_dot=True), "digraph legacy { a -> b; }")

        # No graph
        ctx_from_dict2.graph_ = None
        ctx_from_dict2.graph_string = None
        self.assertFalse(ctx_from_dict2.has_graph)
        self.assertIsNone(ctx_from_dict2.graph())

    def test_get_resolve_diff_and_print_resolve_diff(self) -> None:
        ctx1 = ResolvedContext(["pkg_a-1.0.0", "pkg_b==1.0.0", "pkg_c"])
        ctx2 = ResolvedContext(["pkg_a-2.0.0", "pkg_b==2.0.0", "pkg_no_tools"])

        # Same context -> empty diff
        self.assertEqual(ctx1.get_resolve_diff(ctx1), {})
        with mock.patch("builtins.print") as mock_print:
            ctx1.print_resolve_diff(ctx1)
            mock_print.assert_not_called()

        # Different package_paths -> error
        other_path = _make_memory_repo({"pkg_a": {"1.0.0": {"name": "pkg_a", "version": "1.0.0"}}})
        ctx_other = ResolvedContext(["pkg_a"], package_paths=[other_path])
        with self.assertRaises(ResolvedContextError):
            ctx1.get_resolve_diff(ctx_other)

        # Diff ctx1 -> ctx2: pkg_a & pkg_b newer in ctx2, pkg_no_tools added, pkg_c removed
        diff = ctx1.get_resolve_diff(ctx2)
        self.assertIn("pkg_a", diff["newer_packages"])
        self.assertIn("pkg_b", diff["newer_packages"])
        self.assertEqual({p.name for p in diff["added_packages"]}, {"pkg_no_tools"})
        self.assertEqual({p.name for p in diff["removed_packages"]}, {"pkg_c"})

        # Reverse diff -> older_packages
        rev_diff = ctx2.get_resolve_diff(ctx1)
        self.assertIn("pkg_a", rev_diff["older_packages"])

        # print_resolve_diff with load_path heading=True and explicit tuple
        ctx1.set_load_path("/tmp/a.rxt")
        ctx2.set_load_path("/tmp/b.rxt")
        with mock.patch("builtins.print") as mock_print:
            ctx1.print_resolve_diff(ctx2, heading=True)
            ctx2.print_resolve_diff(ctx1, heading=("Two", "One"))
        printed = "\n".join(
            " ".join(str(a) for a in call.args)
            for call in mock_print.call_args_list
        )
        self.assertIn("a.rxt", printed)
        self.assertIn("b.rxt", printed)
        self.assertIn("Two", printed)
        self.assertIn("One", printed)
        self.assertIn("(+1 versions)", printed)
        self.assertIn("(-1 versions)", printed)

    def test_tools_and_conflicting_tools(self) -> None:
        ctx_none = ResolvedContext(["pkg_no_tools"])
        buf = StringIO()
        ctx_none.print_tools(buf=buf)
        self.assertEqual(buf.getvalue(), "")
        self.assertEqual(ctx_none.get_tool_variants("anything"), set())
        self.assertEqual(ctx_none.get_conflicting_tools(), {})

        ctx = ResolvedContext(["pkg_a-1.0.0"])
        self.assertEqual(len(ctx.get_tool_variants("shared_tool")), 2)
        self.assertEqual(len(ctx.get_tool_variants("tool_a")), 1)
        conflicts = ctx.get_conflicting_tools()
        self.assertIn("shared_tool", conflicts)
        self.assertNotIn("tool_a", conflicts)

        buf = StringIO()
        ctx.print_tools(buf=buf)
        out = buf.getvalue()
        self.assertIn("shared_tool", out)
        self.assertIn("(in conflict)", out)

    def test_get_dependency_graph(self) -> None:
        ctx = ResolvedContext(["pkg_a-1.0.0", ".eph-1"])
        g = ctx.get_dependency_graph(as_dot=False)
        self.assertIn("pkg_a", g.nodes())
        self.assertIn("pkg_b", g.nodes())
        self.assertIn(".eph", g.nodes())
        self.assertTrue(g.has_edge(("pkg_a", "pkg_b")))

        dot = ctx.get_dependency_graph(as_dot=True)
        self.assertIn("digraph", dot)
        self.assertIn("pkg_a", dot)

    def test_validate(self) -> None:
        ctx = ResolvedContext(["pkg_no_tools"])
        ctx.validate()

        with mock.patch.object(
            ctx.resolved_packages[0],
            "validate_data",
            side_effect=RezError("corrupt"),
        ):
            with self.assertRaises(ResolvedContextError):
                ctx.validate()

    def test_get_resolve_as_exact_requests(self) -> None:
        ctx = ResolvedContext(["pkg_a-1.0.0"])
        reqs = [str(r) for r in ctx.get_resolve_as_exact_requests()]
        self.assertIn("pkg_a==1.0.0", reqs)
        self.assertIn("pkg_b==2.0.0", reqs)

    def test_serialization_edge_cases(self) -> None:
        ctx = ResolvedContext(
            ["pkg_a-1.0.0", ".eph-1"],
            package_orderers=[SortedOrder(descending=True)],
        )
        d = ctx.to_dict(fields=["status", "resolved_ephemerals", "package_orderers"])
        self.assertEqual(set(d.keys()), {"status", "resolved_ephemerals", "package_orderers"})
        self.assertEqual(d["resolved_ephemerals"], [".eph-1"])

        # Roundtrip with package_orderers and resolved_ephemerals
        ctx_rt = ResolvedContext.from_dict(ctx.to_dict())
        self.assertEqual([str(x) for x in ctx_rt.resolved_ephemerals], [".eph-1"])
        self.assertIsNotNone(ctx_rt.package_orderers)

        # Older serialize_version < 4.0 calls convert_old_variant_handle
        old_d = ctx.to_dict()
        old_d["serialize_version"] = "3.5"
        with mock.patch(
            "rez.utils.backcompat.convert_old_variant_handle",
            side_effect=lambda h: h,
        ) as mock_conv:
            ResolvedContext.from_dict(old_d)
        self.assertEqual(mock_conv.call_count, len(old_d["resolved_packages"]))

        # YAML buffer loading and error handling
        yaml_buf = StringIO(
            "serialize_version: '4.9'\n"
            "timestamp: 1\n"
            "building: false\n"
            "caching: false\n"
            "implicit_packages: []\n"
            "package_requests: []\n"
            "package_paths: []\n"
            "rez_version: '3.0'\n"
            "rez_path: '/tmp'\n"
            "user: 'u'\n"
            "host: 'h'\n"
            "platform: 'linux'\n"
            "arch: 'x86_64'\n"
            "os: 'os'\n"
            "created: 1\n"
            "status: 'solved'\n"
            "failure_description: null\n"
            "solve_time: 0.0\n"
            "load_time: 0.0\n"
            "graph: ''\n"
            "resolved_packages: []\n"
        )
        ctx_yaml = ResolvedContext.read_from_buffer(yaml_buf, identifier_str="ctx.yaml")
        self.assertTrue(ctx_yaml.success)

        with self.assertRaises(ResolvedContextError) as cm:
            ResolvedContext.read_from_buffer(StringIO("{invalid json"), identifier_str="bad.rxt")
        self.assertIn("bad.rxt", str(cm.exception))

    @unittest.expectedFailure
    def test_serialization_future_version_warns(self) -> None:
        # Bug at src/rez/resolved_context.py:1730 (%d format specifier given str from _print_version)
        ctx = ResolvedContext(["pkg_a-1.0.0"])
        full_d = ctx.to_dict()
        full_d["serialize_version"] = "99.0"
        stderr_buf = StringIO()
        with mock.patch("sys.stderr", stderr_buf):
            loaded = ResolvedContext.from_dict(full_d, identifier_str="future.rxt")
        self.assertTrue(loaded.success)
        err = stderr_buf.getvalue()
        self.assertIn("future.rxt", err)
        self.assertIn("99.0", err)

    def test_execute_env_vars_and_errors(self) -> None:
        # rez_1_environment_variables + ephemerals + rez_tools_visibility ordering
        self.update_settings({
            "rez_1_environment_variables": True,
            "disable_rez_1_compatibility": False,
            "rez_tools_visibility": "prepend",
        })
        ctx = ResolvedContext(["pkg_no_tools", ".eph-1"])
        mock_rez_bin = os.path.normpath("/mock/rez/bin")
        with mock.patch.object(system, "rez_bin_path", mock_rez_bin):
            env = ctx.get_environ()
            self.assertEqual(env.get("REZ_USED_EPH_RESOLVE"), ".eph-1")
            self.assertEqual(env.get("REZ_EPH_EPH_REQUEST"), "1")
            self.assertEqual(env.get("REZ_RESOLVE_MODE"), "latest")
            self.assertEqual(env.get("REZ_VERSION"), ctx.rez_version)
            prepend_parts = env["PATH"].split(os.pathsep)
            self.assertGreater(len(prepend_parts), 1)
            self.assertEqual(prepend_parts[0], mock_rez_bin)

            # rez_tools_visibility = append
            self.update_settings({"rez_tools_visibility": "append"})
            env_append = ctx.get_environ()
            append_parts = env_append["PATH"].split(os.pathsep)
            self.assertGreater(len(append_parts), 1)
            self.assertEqual(append_parts[-1], mock_rez_bin)

    @unittest.expectedFailure
    def test_execute_catch_rex_errors(self) -> None:
        # Bug at src/rez/resolved_context.py:2185: RexExecutor.compile_code wraps SourceCodeError in RexError,
        # so catching SourceCodeError never triggers PackageCommandError and RexError escapes uncaught.
        pkg_cmd_data = {
            "bad_pkg": {
                "1.0.0": {
                    "name": "bad_pkg",
                    "version": "1.0.0",
                    "commands": "def commands():\n    undefined_symbol",
                },
            },
        }
        bad_path = _make_memory_repo(pkg_cmd_data)
        self.update_settings({"catch_rex_errors": True})
        for verb in (0, 2):
            ctx_bad = ResolvedContext(["bad_pkg"], package_paths=[bad_path], verbosity=verb)
            with self.assertRaises(PackageCommandError):
                ctx_bad.get_environ()

    def test_append_suite_paths(self) -> None:
        ctx = ResolvedContext(["pkg_no_tools"])
        ctx._set_parent_suite("/suites/parent", "ctx1")
        parent_bin = os.path.join("/suites/parent", "bin")
        other_bin = os.path.join("/suites/other", "bin")

        for vis in ("never", "always", "parent"):
            self.update_settings({"suite_visibility": vis})
            with mock.patch(
                "rez.suite.Suite.visible_suite_paths",
                return_value=["/suites/other", "/suites/parent"],
            ):
                env = ctx.get_environ(parent_environ={"PATH": "/usr/bin"})
                if vis == "never":
                    self.assertNotIn(parent_bin, env["PATH"])
                    self.assertNotIn(other_bin, env["PATH"])
                elif vis == "always":
                    self.assertIn(other_bin, env["PATH"])
                    self.assertIn(parent_bin, env["PATH"])
                elif vis == "parent":
                    self.assertIn(parent_bin, env["PATH"])
                    self.assertNotIn(other_bin, env["PATH"])

    @unittest.expectedFailure
    def test_append_suite_paths_parent_priority(self) -> None:
        # Bug at src/rez/resolved_context.py:2299-2306: parent_priority drops other visible suites
        # instead of placing parent_suite_path before them.
        ctx = ResolvedContext(["pkg_no_tools"])
        ctx._set_parent_suite("/suites/parent", "ctx1")
        self.update_settings({"suite_visibility": "parent_priority"})
        with mock.patch(
            "rez.suite.Suite.visible_suite_paths",
            return_value=["/suites/other", "/suites/parent"],
        ):
            env = ctx.get_environ(parent_environ={"PATH": "/usr/bin"})
        path_parts = env["PATH"].split(os.pathsep)
        self.assertIn("/suites/parent/bin", path_parts)
        self.assertIn("/suites/other/bin", path_parts)
        self.assertLess(
            path_parts.index("/suites/parent/bin"),
            path_parts.index("/suites/other/bin"),
        )

    def test_context_tracking(self) -> None:
        orig_payload = ResolvedContext.context_tracking_payload
        ResolvedContext.context_tracking_payload = None
        try:
            self.update_settings({
                "context_tracking_host": "amqp.example.com",
                "context_tracking_extra_fields": {
                    "keep": "value",
                    "empty": "",
                    "unexpanded": "$SOME_UNSET_VAR",
                },
            })
            with mock.patch("rez.utils.amqp.publish_message") as mock_pub:
                ctx = ResolvedContext(["pkg_no_tools"])
                mock_pub.assert_called_once()
                payload = mock_pub.call_args.kwargs["data"]
                self.assertEqual(payload["action"], "created")
                self.assertEqual(payload["keep"], "value")
                self.assertNotIn("empty", payload)
                self.assertNotIn("unexpanded", payload)

                # Second call reuses cached context_tracking_payload
                ResolvedContext.from_dict(ctx.to_dict())
                self.assertEqual(mock_pub.call_count, 2)

            # Exception in publish_message is caught and logged
            with mock.patch("rez.utils.amqp.publish_message", side_effect=RuntimeError("conn failed")):
                ctx2 = ResolvedContext(["pkg_no_tools"])
                self.assertTrue(ctx2.success)
        finally:
            ResolvedContext.context_tracking_payload = orig_payload


class TestResolvedContextFilesystem(TestBase, TempdirMixin):
    """Tests requiring filesystem packages, .rxt files, bundles, caches, or shells."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        TempdirMixin.setUpClass()
        cls.local_repo = os.path.join(cls.root, "local_pkgs")
        cls.remote_repo = os.path.join(cls.root, "remote_pkgs")
        _write_fs_package(cls.local_repo, "local_pkg", "1.0.0", "def commands():\n    env.LOCAL_VAR = '1'")
        _write_fs_package(cls.remote_repo, "remote_pkg", "1.0.0", "def commands():\n    env.REMOTE_VAR = '1'")

        cls.settings = dict(
            packages_path=[cls.local_repo, cls.remote_repo],
            local_packages_path=cls.local_repo,
            package_filter=None,
            implicit_packages=[],
            warn_untimestamped=False,
            resolve_caching=False,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        TempdirMixin.tearDownClass()
        super().tearDownClass()

    def test_get_current_and_is_current(self) -> None:
        rxt_path = os.path.join(self.root, "current_test.rxt")
        ctx = ResolvedContext(["local_pkg"])
        self.assertFalse(ctx.is_current())
        ctx.save(rxt_path)

        with restore_os_environ():
            os.environ.pop("REZ_RXT_FILE", None)
            self.assertIsNone(ResolvedContext.get_current())
            loaded = ResolvedContext.load(rxt_path)
            self.assertIsNone(loaded.is_current())

            os.environ["REZ_RXT_FILE"] = rxt_path
            current = ResolvedContext.get_current()
            self.assertIsNotNone(current)
            self.assertTrue(loaded.is_current())

            loaded.set_load_path("/other/path.rxt")
            self.assertFalse(loaded.is_current())

    def test_print_info_branches(self) -> None:
        # Solved context with verbosity=2, local package, implicit, ephemeral, cached root, NOT FOUND
        self.update_settings({
            "implicit_packages": ["~remote_pkg"],
        })
        pf = PackageFilterList.from_pod([{"excludes": ["glob(*-99)"]}])
        rxt_path = os.path.join(self.root, "info_test.rxt")
        ctx = ResolvedContext(
            ["local_pkg", ".eph-1"],
            timestamp=1700000000,
            building=True,
            package_filter=pf,
        )
        ctx.save(rxt_path)
        loaded = ResolvedContext.load(rxt_path)

        buf = StringIO()
        with restore_os_environ():
            os.environ["REZ_RXT_FILE"] = rxt_path
            os.environ["REZ_LOCAL_PKG_ORIG_ROOT"] = "/orig/root"
            os.environ["REZ_LOCAL_PKG_ROOT"] = "/cached/root"
            loaded.print_info(buf=buf, verbosity=2, source_order=True, show_resolved_uris=False)

        out = buf.getvalue()
        self.assertIn("(local)", out)
        self.assertIn("(implicit)", out)
        self.assertIn("(ephemeral)", out)
        self.assertIn("cached", out)
        self.assertIn("NOT FOUND", out)
        self.assertIn("package filters:", out)
        self.assertIn("resolve details:", out)
        self.assertIn("rxt file:", out)
        self.assertIn("tools:", out)
        shell_name = "cmd" if sys.platform == "win32" else "sh"
        shell_code = loaded.get_shell_code(shell=shell_name)
        self.assertIn("REZ_USED_LOCAL_RESOLVE", shell_code)
        self.assertIn("REZ_BUILD_ENV", shell_code)

        # show_resolved_uris=True
        buf_uri = StringIO()
        loaded.print_info(buf=buf_uri, show_resolved_uris=True)
        self.assertIn("package.py", buf_uri.getvalue())

        # Failed context print_info
        failed = ResolvedContext(["local_pkg", "!local_pkg"])
        buf_fail = StringIO()
        failed.print_info(buf=buf_fail)
        self.assertIn("resolve failed,", buf_fail.getvalue())
        self.assertIn("The context failed to resolve:", buf_fail.getvalue())

    def test_retargeted_filtering_and_missing(self) -> None:
        target_repo = os.path.join(self.root, "target_pkgs")
        _write_fs_package(target_repo, "local_pkg", "1.0.0", "def commands():\n    env.LOCAL_VAR = '1'")
        ctx = ResolvedContext(["local_pkg", "remote_pkg"])

        # Only retarget local_pkg; remote_pkg stays in original repo
        retargeted_partial = ctx.retargeted(
            package_paths=[target_repo],
            package_names=["local_pkg"],
        )
        self.assertTrue(
            retargeted_partial.get_resolved_package("local_pkg").root.startswith(canonical_path(target_repo))
        )
        self.assertTrue(
            retargeted_partial.get_resolved_package("remote_pkg").root.startswith(canonical_path(self.remote_repo))
        )

        # skip_missing=True keeps remote_pkg from original repo
        retargeted_skip = ctx.retargeted(package_paths=[target_repo], skip_missing=True)
        self.assertTrue(
            retargeted_skip.get_resolved_package("remote_pkg").root.startswith(canonical_path(self.remote_repo))
        )

        # skip_missing=False raises PackageNotFoundError
        with self.assertRaises(PackageNotFoundError):
            ctx.retargeted(package_paths=[target_repo], skip_missing=False)

    def test_which_and_execute_methods(self) -> None:
        ctx = ResolvedContext(["remote_pkg"])

        # which: not found -> None, fallback=True -> finds python3.13
        self.assertIsNone(ctx.which("definitely_missing_binary_xyz"))
        with mock.patch("rez.resolved_context.which", side_effect=[None, "/usr/bin/python3.13"]):
            self.assertEqual(ctx.which("python3.13", fallback=True), "/usr/bin/python3.13")

        # execute_command with custom parent_environ
        p = ctx.execute_command(
            [sys.executable, "-c", "import os; print(os.environ['CUSTOM_ENV_VAR'] + ':' + os.environ['REMOTE_VAR'])"],
            parent_environ={"CUSTOM_ENV_VAR": "hello", "PATH": os.environ.get("PATH", "")},
            stdout=subprocess.PIPE,
            text=True,
        )
        stdout, _ = p.communicate()
        self.assertEqual(stdout.strip(), "hello:1")

        # execute_rex_code
        shell_name = "cmd" if sys.platform == "win32" else "sh"
        p_rex = ctx.execute_rex_code(
            "setenv('REX_CODE_VAR', '42')\ninfo('REX_CODE_VAR=' + getenv('REX_CODE_VAR'))",
            shell=shell_name,
            stdout=subprocess.PIPE,
            text=True,
        )
        rex_out, _ = p_rex.communicate()
        self.assertEqual(p_rex.returncode, 0)
        self.assertIn("REX_CODE_VAR=42", rex_out)

        # execute_shell with list command, start_new_session, detached, debug
        self.update_settings({
            "terminal_emulator_command": "xterm -e",
            "debug_shell_startup": True,
        })
        sh_cls = plugin_manager.get_plugin_class("shell", shell_name)
        with mock.patch.object(sh_cls, "spawn_shell") as mock_spawn:
            mock_proc = mock.Mock()
            mock_proc.communicate.return_value = ("ok", "")
            mock_proc.returncode = 0
            mock_spawn.return_value = mock_proc
            try:
                rc, out, _ = ctx.execute_shell(
                    shell=shell_name,
                    command=["echo", "hi"],
                    block=True,
                    start_new_session=True,
                    detached=True,
                )
                self.assertEqual(rc, 0)
                self.assertEqual(out, "ok")
                self.assertEqual(mock_spawn.call_args.kwargs["pre_command"], ["xterm", "-e"])
            finally:
                if mock_spawn.called:
                    shutil.rmtree(mock_spawn.call_args.args[1], ignore_errors=True)

    def test_bundle_post_commands_and_adjust_variant(self) -> None:
        bundle_dir = os.path.join(self.root, "my_bundle")
        os.makedirs(bundle_dir, exist_ok=True)
        with open(os.path.join(bundle_dir, "bundle.yaml"), "w", encoding="utf-8") as f:
            f.write("{}\n")
        with open(os.path.join(bundle_dir, "post_commands.py"), "w", encoding="utf-8") as f:
            f.write("setenv('BUNDLE_POST_VAR', 'from_bundle')\n")

        rxt_path = os.path.join(bundle_dir, "context.rxt")
        ctx = ResolvedContext(["remote_pkg"])
        ctx.save(rxt_path)
        loaded = ResolvedContext.load(rxt_path)

        shell_name = "cmd" if sys.platform == "win32" else "sh"
        bundle_cmd = "echo %BUNDLE_POST_VAR%" if sys.platform == "win32" else "echo $BUNDLE_POST_VAR"
        rc, out, _ = loaded.execute_shell(
            shell=shell_name,
            command=bundle_cmd,
            block=True,
            stdout=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), "from_bundle")

        # _adjust_variant_for_bundling non-filesystem & already-absolute
        with mock.patch.object(ResolvedContext, "_get_bundle_path", return_value=bundle_dir):
            mem_handle = {"variables": {"repository_type": "memory", "location": "memory@1"}}
            ResolvedContext._adjust_variant_for_bundling(mem_handle, out=True)
            self.assertEqual(mem_handle["variables"]["location"], "memory@1")

            abs_path = os.path.abspath("/abs/path")
            abs_handle = {"variables": {"repository_type": "filesystem", "location": abs_path}}
            ResolvedContext._adjust_variant_for_bundling(abs_handle, out=False)
            self.assertEqual(abs_handle["variables"]["location"], abs_path)

    def test_package_cache_paths(self) -> None:
        orig_present = ResolvedContext.package_cache_present
        try:
            # Missing cache dir -> PackageCacheError sets package_cache_present = False
            missing_cache = os.path.join(self.root, "no_such_cache")
            self.update_settings({
                "cache_packages_path": missing_cache,
                "write_package_cache": True,
                "read_package_cache": True,
            })
            ResolvedContext.package_cache_present = True
            self.assertIsNone(ResolvedContext._get_package_cache())
            self.assertFalse(ResolvedContext.package_cache_present)
            # Second call hits early return
            self.assertIsNone(ResolvedContext._get_package_cache())

            # Existing cache dir with sync write & read_package_cache
            ResolvedContext.package_cache_present = True
            cache_dir = os.path.join(self.root, "pkg_cache")
            os.makedirs(cache_dir, exist_ok=True)
            self.update_settings({
                "cache_packages_path": cache_dir,
                "write_package_cache": True,
                "read_package_cache": True,
            })
            with mock.patch("rez.package_cache.PackageCache.add_variants") as mock_add, \
                    mock.patch("rez.package_cache.PackageCache.get_cached_root", return_value="/cached/pkg/root"):
                ctx = ResolvedContext(["remote_pkg"], package_cache_async=False)
                mock_add.assert_called_once()
                env = ctx.get_environ()
                self.assertEqual(env.get("REZ_REMOTE_PKG_ROOT"), "/cached/pkg/root")
                self.assertIn("REZ_REMOTE_PKG_ORIG_ROOT", env)
        finally:
            ResolvedContext.package_cache_present = orig_present


if __name__ == "__main__":
    unittest.main()
