# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Additional unit tests for rez.solver covering graph generation, callbacks,
printer verbosity, failure reasons, variant slices, scopes, and edge cases.
"""
from __future__ import annotations

import contextlib
import io
import unittest
from unittest import mock

import rez.solver as solver_mod
from rez.exceptions import PackageFamilyNotFoundError, PackageNotFoundError, ResolveError, RezSystemError
from rez.package_filter import PackageFilterList, Rule
from rez.package_repository import package_repository_manager
from rez.solver import (
    Cycle,
    DependencyConflict,
    DependencyConflicts,
    FailureReason,
    Reduction,
    Solver,
    SolverCallbackReturn,
    SolverState,
    SolverStatus,
    TotalReduction,
    _PackageScope,
    _PackageVariantList,
    _Printer,
)
from rez.tests.util import TestBase
from rez.version import Requirement, Version, VersionRange


def _make_mem_repo(pkg_data: dict) -> list[str]:
    mem_path = "memory@%s" % hex(id(pkg_data))
    repo = package_repository_manager.get_repository(mem_path)
    repo.data = pkg_data
    return [mem_path]


class TestSolverPrinterAndStats(TestBase):
    def test_printer_verbosity_3_and_suppress_passive(self) -> None:
        buf = io.StringIO()
        pr = _Printer(3, buf=buf, suppress_passive=False)
        pr.header("HEAD %s", "1")
        pr.subheader("SUB")
        pr("msg %d", 1)
        pr.br()
        pr("msg %d", 2)
        pr.passive("passive %s", "ok")

        out = buf.getvalue()
        self.assertIn("-" * 80, out)
        self.assertIn("HEAD 1", out)
        self.assertIn("SUB", out)
        self.assertIn("msg 1", out)
        self.assertIn("msg 2", out)
        self.assertIn("passive ok", out)

        buf2 = io.StringIO()
        pr2 = _Printer(3, buf=buf2, suppress_passive=True)
        pr2.passive("should not appear")
        self.assertEqual(buf2.getvalue(), "")

    def test_solve_verbosity_3_and_print_stats(self) -> None:
        paths = _make_mem_repo({
            "a": {"1.0": {"name": "a", "version": "1.0", "requires": ["b-1"]}},
            "b": {"1.0": {"name": "b", "version": "1.0"}},
        })
        buf = io.StringIO()
        s = Solver([Requirement("a")], paths, verbosity=3, buf=buf)
        s.solve()
        self.assertEqual(s.status, SolverStatus.solved)
        self.assertIn("SOLVE STATS:", buf.getvalue())
        self.assertIn("SolverStatus.solved", str(s))

        buf2 = io.StringIO()
        s2 = Solver([Requirement("a")], paths, verbosity=0, buf=buf2, print_stats=True)
        s2.solve()
        self.assertEqual(s2.status, SolverStatus.solved)
        self.assertIn("solve_stats", buf2.getvalue())


class TestFailureReasonsAndState(TestBase):
    def test_solver_state_and_failure_reasons(self) -> None:
        paths = _make_mem_repo({
            "a": {"1.0": {"name": "a", "version": "1.0"}},
        })
        s = Solver([Requirement("a")], paths)
        phase = s.phase_stack[-1]
        state = SolverState(1, 0, phase)
        self.assertIn("solve #1 (0 fails so far):", str(state))

        base_fr = FailureReason()
        self.assertEqual(base_fr.involved_requirements(), [])
        self.assertEqual(base_fr.description(), "")

        red = Reduction("a", Version("1.0"), 0, Requirement("b-1"), Requirement("b-2"))
        self.assertIn("Reduction(", repr(red))
        self.assertEqual(
            [str(r) for r in red.involved_requirements()],
            ["a-1.0", "b-1", "b-2"],
        )

        red_same = Reduction("a", Version("1.0"), 0, Requirement("b-1"), Requirement("b-2"))
        red_none = Reduction("a", Version("1.0"), None, Requirement("b-1"), Requirement("b-2"))
        self.assertIn("[]", red_none.reducee_str())
        self.assertIn("[]", repr(red_none))
        self.assertEqual(red, red_same)
        self.assertNotEqual(red, red_none)

        tr = TotalReduction([red])
        self.assertEqual(len(tr.involved_requirements()), 3)

        dc = DependencyConflict(Requirement("b-1"), Requirement("b-2"))
        dcs = DependencyConflicts([dc])
        self.assertEqual([str(r) for r in dcs.involved_requirements()], ["b-1", "b-2"])

        cyc = Cycle([
            solver_mod.VersionedObject.construct("a", Version("1.0")),
            solver_mod.VersionedObject.construct("b", Version("1.0")),
        ])
        self.assertEqual([str(r) for r in cyc.involved_requirements()], ["a-1.0", "b-1.0"])


class TestPackageVariantAndLists(TestBase):
    def test_package_variant_handle_eq_lt_and_internal_conflict(self) -> None:
        paths = _make_mem_repo({
            "a": {
                "1.0": {
                    "name": "a",
                    "version": "1.0",
                    "variants": [["x-1"], ["x-2"]],
                },
                "2.0": {
                    "name": "a",
                    "version": "2.0",
                    "requires": ["x-1", "!x-1"],
                },
            },
            "b": {
                "2.0": {
                    "name": "b",
                    "version": "2.0",
                    "variants": [["x-1"], ["x-2"]],
                },
            },
            "x": {
                "1": {"name": "x", "version": "1"},
                "2": {"name": "x", "version": "2"},
            },
        })
        s = Solver([Requirement("a-1.0")], paths)
        vl_a = _PackageVariantList("a", s)
        entries_a = vl_a.get_intersection(VersionRange("1.0"))
        v0, v1 = entries_a[0].variants

        self.assertIsInstance(v0.handle, dict)
        self.assertTrue(v0 == v0)
        self.assertFalse(v0 == v1)

        vl_b = _PackageVariantList("b", s)
        entries_b = vl_b.get_intersection(VersionRange("2.0"))
        vb1 = entries_b[0].variants[1]
        self.assertTrue(v0 < vb1)
        self.assertFalse(vb1 < v0)

        entries_bad = vl_a.get_intersection(VersionRange("2.0"))
        v_bad = entries_bad[0].variants[0]
        with self.assertRaises(ResolveError):
            _ = v_bad.requires_list

    # src/rez/solver.py:367-372: PackageVariant.__lt__ uses 'and' and fails with TypeError when index is None
    @unittest.expectedFailure
    def test_package_variant_lt_bug(self) -> None:
        paths = _make_mem_repo({
            "a": {
                "1.0": {"name": "a", "version": "1.0", "variants": [["x-1"]]},
                "2.0": {"name": "a", "version": "2.0", "variants": [["x-1"]]},
            },
            "b": {
                "1.0": {"name": "b", "version": "1.0"},
                "2.0": {"name": "b", "version": "2.0"},
            },
            "x": {"1": {"name": "x", "version": "1"}},
        })
        s = Solver([Requirement("a")], paths)
        vl_a = _PackageVariantList("a", s)
        v_a1 = vl_a.get_intersection(VersionRange("1.0"))[0].variants[0]

        vl_b = _PackageVariantList("b", s)
        v_b2_raw = vl_b.get_intersection(VersionRange("2.0"))[0].variants[0]
        v_b2_none = solver_mod.PackageVariant(v_b2_raw.variant, building=False)
        self.assertIsNone(v_b2_none.index)
        self.assertTrue(v_a1 < v_b2_none)

    def test_variant_list_filter_dump_and_str(self) -> None:
        self.update_settings({"debug_package_exclusions": True})
        paths = _make_mem_repo({
            "a": {
                "1.0": {"name": "a", "version": "1.0"},
                "2.0": {"name": "a", "version": "2.0"},
                "3.0": {"name": "a", "version": "3.0"},
            },
        })
        pfilter = PackageFilterList()
        pfilter.add_exclusion(Rule.parse_rule("range(a-2.0)"))
        loaded = []
        s = Solver([Requirement("a")], paths, package_filter=pfilter, package_load_callback=loaded.append)
        vl = _PackageVariantList("a", s)

        # Intersect only 1.0 and 2.0 so 3.0 remains unexpanded, 2.0 is filtered, 1.0 is expanded
        entries = vl.get_intersection(VersionRange("1.0+<3.0"))
        self.assertEqual(len(entries), 1)
        self.assertEqual(len(loaded), 3)
        # Second call hits already-filtered entry (value is None)
        entries2 = vl.get_intersection(VersionRange("1.0+<3.0"))
        self.assertEqual(len(entries2), 1)

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            vl.dump()
        dumped = buf.getvalue()
        self.assertIn("[FILTERED]", dumped)
        self.assertIn("a-1.0[]", dumped)
        self.assertIn("Package(", dumped)

        vl_str = str(vl)
        self.assertIn("a[", vl_str)
        self.assertIn("a-1.0[]", vl_str)
        self.assertIn("Package(", vl_str)

    def test_variant_slice_str_dump_intersect_cache_and_split(self) -> None:
        paths = _make_mem_repo({
            "a": {
                "1.0": {
                    "name": "a",
                    "version": "1.0",
                    "variants": [["x-1", "y-1"], ["x-1", "y-1"]],
                },
                "2.0": {
                    "name": "a",
                    "version": "2.0",
                    "variants": [["z-1"]],
                },
                "3.0": {
                    "name": "a",
                    "version": "3.0",
                },
            },
            "x": {"1": {"name": "x", "version": "1"}},
            "y": {"1": {"name": "y", "version": "1"}},
            "z": {"1": {"name": "z", "version": "1"}},
        })
        buf = io.StringIO()
        s = Solver([Requirement("a")], paths, verbosity=3, buf=buf)
        sl_multi = s._get_variant_slice("a", VersionRange("1.0+"))
        # >1 version, nversions != nvariants, not extractable
        self.assertIn("a[1.0..3.0(3:4)]", str(sl_multi))

        # Cached intersect (optimised=True)
        r = VersionRange("1.0+<=2.0")
        sl_sub = sl_multi.intersect(r)
        self.assertIs(sl_sub.intersect(r), sl_sub)

        # Single version, >1 variants, extractable ('*')
        sl_v1 = s._get_variant_slice("a", VersionRange("1.0"))
        self.assertEqual(str(sl_v1), "[a==1.0[0,1]]*")

        # Single variant with index is None
        sl_v3 = s._get_variant_slice("a", VersionRange("3.0"))
        self.assertEqual(str(sl_v3), "[a==3.0]")

        # Single variant with index is not None
        sl_v2 = s._get_variant_slice("a", VersionRange("2.0"))
        self.assertEqual(str(sl_v2), "[a==2.0[0]]*")

        # dump()
        dump_buf = io.StringIO()
        with contextlib.redirect_stdout(dump_buf):
            sl_v2.dump()
        self.assertIn("a-2.0[0]", dump_buf.getvalue())

        # split() with len(common_fams) > 1 (x and y shared by first 2 variants, not 3rd)
        sl_sub.sort_versions()
        # Reverse so 1.0 (with 2 variants sharing x, y) comes first before 2.0 (with z)
        sl_sub.entries.reverse()
        first, second = sl_sub.split()
        self.assertEqual(len(first), 2)
        self.assertEqual(len(second), 1)
        self.assertIn("split (reason:", buf.getvalue())

        # split() when all >2 variants share an unextracted common family raises RezSystemError
        paths_common = _make_mem_repo({
            "p": {
                "1.0": {"name": "p", "version": "1.0", "requires": ["x-1"]},
                "2.0": {"name": "p", "version": "2.0", "requires": ["x-1"]},
                "3.0": {"name": "p", "version": "3.0", "requires": ["x-1"]},
            },
            "x": {"1": {"name": "x", "version": "1"}},
        })
        s_common = Solver([Requirement("p")], paths_common)
        sl_common = s_common._get_variant_slice("p", VersionRange("1.0+"))
        with self.assertRaises(RezSystemError):
            sl_common.split()


class TestPackageScopeAndCache(TestBase):
    def test_variant_cache_none_and_scope_not_found(self) -> None:
        paths = _make_mem_repo({
            "a": {"1.0": {"name": "a", "version": "1.0"}},
        })
        s = Solver([Requirement("a")], paths)
        self.assertIsNone(s._get_variant_slice("a", VersionRange("99.0")))

        with self.assertRaises(PackageNotFoundError):
            _PackageScope(Requirement("a-99.0"), s)

    def test_ephemeral_and_conflict_scope_intersections(self) -> None:
        paths = _make_mem_repo({
            "a": {"1.0": {"name": "a", "version": "1.0"}, "2.0": {"name": "a", "version": "2.0"}},
        })
        buf = io.StringIO()
        s = Solver([Requirement("a")], paths, verbosity=1, buf=buf)

        # Ephemeral non-conflict: narrowed & conflict
        e_scope = _PackageScope(Requirement(".eph-1+<3"), s)
        self.assertEqual(str(e_scope), ".eph-1+<3")
        narrowed = e_scope.intersect(VersionRange("2"))
        self.assertIsNotNone(narrowed)
        self.assertEqual(str(narrowed), ".eph-2")
        self.assertIsNone(narrowed.intersect(VersionRange("1")))

        # Ephemeral conflict: narrowed & conflict
        ec_scope = _PackageScope(Requirement("!.eph-2"), s)
        ec_narrowed = ec_scope.intersect(VersionRange("1+<3"))
        self.assertIsNotNone(ec_narrowed)
        self.assertEqual(str(ec_narrowed), ".eph-1+<2|2_+<3")
        self.assertIsNone(ec_scope.intersect(VersionRange("2")))

        # Conflict scope: !a-1 intersected with 1.0+ yields a-2.0
        c_scope = _PackageScope(Requirement("!a-1"), s)
        c_res = c_scope.intersect(VersionRange("1.0+"))
        self.assertIsNotNone(c_res)
        self.assertFalse(c_res.is_conflict)
        self.assertEqual(str(c_res), "[a==2.0]")

        # Conflict scope: !a intersected with 1.0+ leaves no versions -> None
        c_all = _PackageScope(Requirement("!a"), s)
        self.assertIsNone(c_all.intersect(VersionRange("1.0+")))


class TestSolverCallbacksResetDumpAndErrors(TestBase):
    def test_force_unoptimised_solver_and_non_pending_phase(self) -> None:
        paths = _make_mem_repo({
            "a": {
                "1.0": {"name": "a", "version": "1.0"},
                "2.0": {"name": "a", "version": "2.0"},
            },
        })
        with mock.patch.object(solver_mod, "_force_unoptimised_solver", True):
            s = Solver([Requirement("a")], paths, optimised=True)
            self.assertFalse(s.optimised)

        s.solve()
        phase = s.phase_stack[-1]
        self.assertIs(phase.solve(), phase)
        self.assertIn("[a==2.0]", str(phase))

        # Calling solve() again raises ResolveError; solve_step() is a no-op
        with self.assertRaises(ResolveError):
            s.solve()
        s.solve_step()

        # reset() resets back to unsolved
        s.reset()
        self.assertEqual(s.status, SolverStatus.unsolved)
        self.assertIsNone(s.resolved_packages)
        self.assertIsNone(s.resolved_ephemerals)
        self.assertFalse(s.cyclic_fail)
        self.assertIsNone(s.phase_stack[-1]._get_minimal_graph())

    def test_callbacks_abort_and_fail(self) -> None:
        paths = _make_mem_repo({
            "a": {
                "1.0": {"name": "a", "version": "1.0", "requires": ["b-1"]},
                "2.0": {"name": "a", "version": "2.0", "requires": ["b-2"]},
            },
            "b": {
                "1.0": {"name": "b", "version": "1.0"},
                "2.0": {"name": "b", "version": "2.0"},
            },
        })

        # Abort callback (only fires when status is still unsolved after solve_step)
        def abort_cb(state: SolverState) -> tuple[SolverCallbackReturn, str]:
            return SolverCallbackReturn.abort, "user aborted"

        buf = io.StringIO()
        s_abort = Solver([Requirement("a")], paths, callback=abort_cb, verbosity=3, buf=buf)
        s_abort.solve()
        self.assertEqual(s_abort.status, SolverStatus.unsolved)
        self.assertEqual(s_abort.abort_reason, "user aborted")
        self.assertIn("solve aborted: user aborted", buf.getvalue())

        # Fail callback: ignored when num_fails == 0, fails when num_fails > 0
        paths_fail = _make_mem_repo({
            "a": {
                "1.0": {"name": "a", "version": "1.0", "requires": ["d-1"]},
                "2.0": {"name": "a", "version": "2.0", "requires": ["b-2"]},
            },
            "b": {
                "2.0": {"name": "b", "version": "2.0", "requires": ["c-2"]},
            },
            "c": {"1.0": {"name": "c", "version": "1.0"}, "2.0": {"name": "c", "version": "2.0"}},
            "d": {"1.0": {"name": "d", "version": "1.0"}},
        })
        calls = []

        def fail_cb(state: SolverState) -> tuple[SolverCallbackReturn, str]:
            calls.append(state.num_fails)
            return SolverCallbackReturn.fail, "forced fail"

        buf2 = io.StringIO()
        s_fail = Solver([Requirement("a"), Requirement("!c-2")], paths_fail, callback=fail_cb, verbosity=3, buf=buf2)
        s_fail.solve()
        self.assertIn(0, calls)
        self.assertIn(1, calls)
        self.assertEqual(s_fail.status, SolverStatus.failed)
        self.assertIn("forced fail:", s_fail.failure_description())
        self.assertIsNone(s_fail._latest_nonfailed_phase())

        # failure_index out of range
        with self.assertRaises(IndexError):
            s_fail.failure_reason(failure_index=999)

        # failure_description when failure_reason is None
        s_fail.phase_stack[-1].failure_reason = None
        self.assertIn("Solver failed with unknown reason.", s_fail.failure_description())
        self.assertIsNone(s_fail.failure_packages())

    def test_dump_with_failed_phases_and_missing_family_no_requesters(self) -> None:
        paths = _make_mem_repo({
            "a": {
                "1.0": {"name": "a", "version": "1.0", "requires": ["d-1"]},
                "2.0": {"name": "a", "version": "2.0", "requires": ["b-2"]},
            },
            "b": {
                "2.0": {"name": "b", "version": "2.0", "requires": ["c-2"]},
            },
            "c": {"1.0": {"name": "c", "version": "1.0"}, "2.0": {"name": "c", "version": "2.0"}},
            "d": {"1.0": {"name": "d", "version": "1.0"}},
        })
        s = Solver([Requirement("a"), Requirement("!c-2")], paths)
        s.solve()
        self.assertEqual(s.status, SolverStatus.solved)
        self.assertGreater(len(s.failed_phase_list), 0)

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            s.dump()
        out = buf.getvalue()
        self.assertIn("solve stack:", out)
        self.assertIn("previous failures:", out)

        # _ResolvePhase.solve() re-raises PackageFamilyNotFoundError when requesters is empty
        paths_missing = _make_mem_repo({
            "a": {"1.0": {"name": "a", "version": "1.0", "requires": ["missing_pkg-1"]}},
        })
        s_miss = Solver([Requirement("a")], paths_missing)
        with self.assertRaises(PackageFamilyNotFoundError):
            s_miss.solve()


class TestSolverGraphs(TestBase):
    def test_graph_solved_extraction_merge_and_conflict_scope(self) -> None:
        paths = _make_mem_repo({
            "a": {"1.0": {"name": "a", "version": "1.0", "requires": ["c-1+"]}},
            "b": {"1.0": {"name": "b", "version": "1.0", "requires": ["c-<3"]}},
            "c": {
                "2.0": {"name": "c", "version": "2.0"},
            },
            "d": {"1.0": {"name": "d", "version": "1.0"}},
        })
        s = Solver([Requirement("a"), Requirement("b"), Requirement("!d")], paths)
        s.solve()
        self.assertEqual(s.status, SolverStatus.solved)
        g = s.get_graph()
        labels = [dict(g.node_attributes(n)).get("label") for n in g.nodes()]
        self.assertIn("c-1+<3", labels)
        self.assertIn("!d", labels)
        self.assertTrue(
            any(("arrowhead", "odot") in g.edge_attributes(e) for e in g.edges())
        )

    def test_graph_unsolved_scope_node(self) -> None:
        paths = _make_mem_repo({
            "a": {
                "1.0": {"name": "a", "version": "1.0", "requires": ["b-1"]},
                "2.0": {"name": "a", "version": "2.0", "requires": ["b-2"]},
            },
            "b": {
                "1.0": {"name": "b", "version": "1.0"},
                "2.0": {"name": "b", "version": "2.0"},
            },
        })
        s = Solver([Requirement("a")], paths)
        s.solve_step()
        self.assertEqual(s.status, SolverStatus.unsolved)
        g = s.get_graph()
        node_attrs = [dict(g.node_attributes(n)) for n in g.nodes()]
        self.assertTrue(
            any(
                attrs.get("label") == "a[1.0..2.0(2)]" and attrs.get("fillcolor") == "#F6F6F6"
                for attrs in node_attrs
            )
        )

    def test_graph_cycle_and_cyclic_fail(self) -> None:
        paths = _make_mem_repo({
            "a": {"1.0": {"name": "a", "version": "1.0", "requires": ["b-1"]}},
            "b": {"1.0": {"name": "b", "version": "1.0", "requires": ["a-1"]}},
        })
        s = Solver([Requirement("a")], paths)
        s.solve()
        self.assertEqual(s.status, SolverStatus.failed)
        self.assertTrue(s.cyclic_fail)
        self.assertIsInstance(s.failure_reason(), Cycle)
        self.assertEqual(len(s.failure_packages()), 2)
        g = s.get_graph()
        node_labels = {n: dict(g.node_attributes(n)).get("label", "") for n in g.nodes()}
        cycle_edges = [
            (node_labels[src], node_labels[dst])
            for src, dst in g.edges()
            if g.edge_label((src, dst)) == "CYCLE"
        ]
        self.assertIn(("a-1.0[]", "b-1.0[]"), cycle_edges)
        self.assertIn(("b-1.0[]", "a-1.0[]"), cycle_edges)

    def test_graph_total_reduction_single_and_multi(self) -> None:
        # Single reduction (conflict dependency is never extracted, always reduced)
        paths_single = _make_mem_repo({
            "a": {"1.0": {"name": "a", "version": "1.0", "requires": ["!b-2"]}},
            "b": {"2.0": {"name": "b", "version": "2.0"}},
        })
        s1 = Solver([Requirement("a"), Requirement("b-2")], paths_single)
        s1.solve()
        self.assertEqual(s1.status, SolverStatus.failed)
        self.assertIsInstance(s1.failure_reason(), TotalReduction)
        self.assertEqual(len(s1.failure_packages()), 3)
        g1 = s1.get_graph()
        self.assertTrue(any(g1.edge_label(e) == "CONFLICT" for e in g1.edges()))

        # Multi reduction (>1 reductions in TotalReduction) + prune_unfailed
        paths_multi = _make_mem_repo({
            "a": {
                "1.0": {"name": "a", "version": "1.0", "requires": ["!b-3"]},
                "2.0": {"name": "a", "version": "2.0", "requires": ["!b-3"]},
            },
            "b": {"3.0": {"name": "b", "version": "3.0"}},
            "unrelated": {"1.0": {"name": "unrelated", "version": "1.0"}},
        })
        s2 = Solver([Requirement("a"), Requirement("b-3"), Requirement("unrelated")], paths_multi, prune_unfailed=True)
        s2.solve()
        self.assertEqual(s2.status, SolverStatus.failed)
        fr = s2.failure_reason()
        self.assertIsInstance(fr, TotalReduction)
        self.assertGreater(len(fr.reductions), 1)
        g2 = s2.get_graph()
        self.assertTrue(any(g2.edge_label(e) == "CONFLICT" for e in g2.edges()))
        # unrelated was pruned
        labels = [
            dict(g2.node_attributes(n)).get("label", "")
            for n in g2.nodes()
        ]
        self.assertFalse(any("unrelated" in lbl for lbl in labels))

    def test_graph_dependency_conflicts(self) -> None:
        # Initial conflict request '!b' conflicting with extracted 'b-1' (scope_n is not None and scope_r is None)
        paths = _make_mem_repo({
            "a": {"1.0": {"name": "a", "version": "1.0", "requires": ["b-1"]}},
            "b": {"1.0": {"name": "b", "version": "1.0"}},
        })
        s1 = Solver([Requirement("a"), Requirement("!b")], paths)
        s1.solve()
        self.assertEqual(s1.status, SolverStatus.failed)
        self.assertIsInstance(s1.failure_reason(), DependencyConflicts)
        self.assertEqual(len(s1.failure_packages()), 2)
        g1 = s1.get_graph()
        g1_labels = {n: dict(g1.node_attributes(n)).get("label", "") for n in g1.nodes()}
        g1_conflicts = [
            (g1_labels[src], g1_labels[dst])
            for src, dst in g1.edges()
            if g1.edge_label((src, dst)) == "CONFLICT"
        ]
        self.assertIn(("!b", "b-1"), g1_conflicts)

        # Two packages extracting conflicting requirements for 'c' where 'c' is also in scopes
        paths2 = _make_mem_repo({
            "a": {"1.0": {"name": "a", "version": "1.0", "requires": ["c-1"]}},
            "b": {"1.0": {"name": "b", "version": "1.0", "requires": ["c-2"]}},
            "c": {
                "1.0": {"name": "c", "version": "1.0"},
                "2.0": {"name": "c", "version": "2.0"},
            },
        })
        s2 = Solver([Requirement("a"), Requirement("b"), Requirement("c-1")], paths2)
        s2.solve()
        self.assertEqual(s2.status, SolverStatus.failed)
        g2 = s2.get_graph()
        g2_labels = {n: dict(g2.node_attributes(n)).get("label", "") for n in g2.nodes()}
        g2_conflicts = [
            (g2_labels[src], g2_labels[dst])
            for src, dst in g2.edges()
            if g2.edge_label((src, dst)) == "CONFLICT"
        ]
        self.assertIn(("c-2", "c-1.0[]"), g2_conflicts)
