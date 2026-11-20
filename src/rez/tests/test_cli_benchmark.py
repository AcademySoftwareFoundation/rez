# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Unit tests for rez.cli.benchmark.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import subprocess
import tempfile
from unittest.mock import MagicMock, patch

from rez.cli import benchmark
from rez.tests.util import TempdirMixin, TestBase


_SENTINEL = object()


class TestCliBenchmark(TestBase, TempdirMixin):
    """Tests for rez.cli.benchmark CLI and helper functions."""

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
        self._orig_opts = getattr(benchmark, "_opts", _SENTINEL)
        self._orig_out_dir = benchmark.out_dir
        self._orig_pkg_repo_dir = benchmark.pkg_repo_dir
        self.work_dir = tempfile.mkdtemp(dir=self.root)

    def tearDown(self) -> None:
        if self._orig_opts is _SENTINEL:
            if hasattr(benchmark, "_opts"):
                delattr(benchmark, "_opts")
        else:
            benchmark._opts = self._orig_opts
        benchmark.out_dir = self._orig_out_dir
        benchmark.pkg_repo_dir = self._orig_pkg_repo_dir
        super().tearDown()

    def _make_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(prog="rez-benchmark")
        benchmark.setup_parser(parser)
        return parser

    def test_setup_parser_defaults_and_options(self) -> None:
        """setup_parser registers --out, --iterations, --histogram, and --compare."""
        parser = self._make_parser()
        opts = parser.parse_args([])
        self.assertEqual(opts.out, "out")
        self.assertEqual(opts.iterations, 1)
        self.assertFalse(opts.histogram)
        self.assertIsNone(opts.compare)

        opts = parser.parse_args([
            "--out", "results_dir",
            "--iterations", "5",
            "--histogram",
            "--compare", "other_dir",
        ])
        self.assertEqual(opts.out, "results_dir")
        self.assertEqual(opts.iterations, 5)
        self.assertTrue(opts.histogram)
        self.assertEqual(opts.compare, "other_dir")

    def test_command_dispatch(self) -> None:
        """command() sets module globals and dispatches to histogram/compare/run_benchmark."""
        parser = self._make_parser()
        out_path = os.path.join(self.work_dir, "out1")

        opts = parser.parse_args(["--out", out_path, "--histogram"])
        with patch.object(benchmark, "print_histogram") as mock_hist:
            benchmark.command(opts, parser)
        mock_hist.assert_called_once_with()
        self.assertIs(benchmark._opts, opts)
        self.assertEqual(benchmark.out_dir, os.path.abspath(out_path))
        self.assertEqual(benchmark.pkg_repo_dir, os.path.join(os.path.abspath(out_path), "packages"))

        opts = parser.parse_args(["--out", out_path, "--compare", "baseline"])
        with patch.object(benchmark, "compare") as mock_compare:
            benchmark.command(opts, parser)
        mock_compare.assert_called_once_with()

        opts = parser.parse_args(["--out", out_path])
        with patch.object(benchmark, "run_benchmark") as mock_run:
            benchmark.command(opts, parser)
        mock_run.assert_called_once_with()

    def test_load_packages(self) -> None:
        """load_packages iterates families, validates packages, and iterates variants."""
        from rez.package_maker import make_package

        pkg_repo_dir = os.path.join(self.work_dir, "packages")
        os.makedirs(pkg_repo_dir)
        with make_package("foo", pkg_repo_dir) as pkg:
            pkg.version = "1.0.0"
        with make_package("bar", pkg_repo_dir) as pkg:
            pkg.version = "1.0.0"
            pkg.variants = [["linux"]]

        benchmark.pkg_repo_dir = pkg_repo_dir

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            benchmark.load_packages()

        output = stdout.getvalue()
        self.assertIn("Warming package cache...", output)
        self.assertIn("[1/2].", output)
        self.assertIn("[2/2].", output)

    def test_get_system_info_with_cpuinfo(self) -> None:
        """get_system_info parses /proc/cpuinfo output when cat succeeds."""
        cpuinfo = (
            "processor\t: 0\n"
            "model name\t: Test CPU\n"
            "\n"
            "line without colon\n"
            "processor\t: 3\n"
            "model name\t: Test CPU\n"
        )
        proc = MagicMock()
        proc.returncode = 0
        proc.communicate.return_value = (cpuinfo, None)

        with patch("rez.utils.execution.Popen", return_value=proc) as mock_popen:
            info = benchmark.get_system_info()

        mock_popen.assert_called_once_with(
            ["cat", "/proc/cpuinfo"],
            stdout=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(info["num_cpu"], 4)
        self.assertEqual(info["cpu"], "Test CPU")
        self.assertIn("rez_version", info)
        self.assertIn("rez_solver_version", info)
        self.assertIn("py_version", info)
        self.assertIn("platform", info)

    def test_get_system_info_nonzero_and_exception(self) -> None:
        """get_system_info omits CPU fields on non-zero exit or Popen exception."""
        proc = MagicMock()
        proc.returncode = 1
        proc.communicate.return_value = ("", None)

        with patch("rez.utils.execution.Popen", return_value=proc):
            info = benchmark.get_system_info()

        self.assertNotIn("num_cpu", info)
        self.assertNotIn("cpu", info)

        with patch("rez.utils.execution.Popen", side_effect=OSError("no proc")):
            info_err = benchmark.get_system_info()

        self.assertNotIn("num_cpu", info_err)
        self.assertNotIn("cpu", info_err)

    def test_run_benchmark_existing_out_dir_exits(self) -> None:
        """run_benchmark exits with code 1 when out_dir already exists."""
        out_dir = os.path.join(self.work_dir, "existing")
        os.mkdir(out_dir)
        benchmark.out_dir = out_dir

        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as cm:
                benchmark.run_benchmark()

        self.assertEqual(cm.exception.code, 1)
        self.assertIn("must not exist", stderr.getvalue())

    def test_run_benchmark_success(self) -> None:
        """run_benchmark creates out_dir, extracts packages, warms cache, and runs resolves."""
        from rez.package_maker import make_package

        out_dir = os.path.join(self.work_dir, "fresh_out")
        pkg_repo_dir = os.path.join(out_dir, "packages")
        benchmark.out_dir = out_dir
        benchmark.pkg_repo_dir = pkg_repo_dir
        proc = MagicMock()

        def fake_popen(cmd, **kwargs):
            os.makedirs(pkg_repo_dir, exist_ok=True)
            with make_package("alpha", pkg_repo_dir) as pkg:
                pkg.version = "1.0.0"
            return proc

        stdout = io.StringIO()
        with patch("rez.utils.execution.Popen", side_effect=fake_popen) as mock_popen:
            with patch.object(benchmark, "do_resolves") as mock_resolves:
                with contextlib.redirect_stdout(stdout):
                    benchmark.run_benchmark()

        self.assertTrue(os.path.isdir(out_dir))
        mock_popen.assert_called_once()
        args, kwargs = mock_popen.call_args
        self.assertEqual(args[0][:2], ["tar", "-xf"])
        self.assertTrue(args[0][2].endswith(os.path.join("data", "benchmarking", "packages.tar.gz")))
        self.assertEqual(kwargs, {"cwd": out_dir})
        proc.wait.assert_called_once_with()
        mock_resolves.assert_called_once_with()
        output = stdout.getvalue()
        self.assertIn("Warming package cache...", output)
        self.assertIn("[1/1].", output)

    def test_do_resolves_mixed_outcomes(self) -> None:
        """do_resolves records success, failed, and error outcomes and writes JSON files."""
        out_dir = os.path.join(self.work_dir, "out_mixed")
        os.mkdir(out_dir)
        pkg_repo_dir = os.path.join(out_dir, "packages")
        fake_root = os.path.join(self.work_dir, "rez_root")
        req_dir = os.path.join(fake_root, "data", "benchmarking")
        os.makedirs(req_dir)
        with open(os.path.join(req_dir, "requests.json"), "w") as f:
            json.dump([["foo"], ["bar"], ["boom"]], f)

        benchmark.out_dir = out_dir
        benchmark.pkg_repo_dir = pkg_repo_dir
        benchmark._opts = argparse.Namespace(iterations=2)

        pkg_obj = MagicMock()
        pkg_obj.uri = os.path.join(pkg_repo_dir, "foo", "1.0")

        success_ctxt = MagicMock()
        success_ctxt.success = True
        success_ctxt.resolved_packages = [pkg_obj]

        failed_ctxt = MagicMock()
        failed_ctxt.success = False

        def fake_resolved_context(**kwargs):
            self.assertIs(kwargs["add_implicit_packages"], False)
            cb = kwargs["callback"]
            ret = cb(None)
            self.assertEqual(ret[1], "")
            req = kwargs["package_requests"]
            if req == ["foo"]:
                return success_ctxt
            if req == ["bar"]:
                return failed_ctxt
            raise RuntimeError("solver exploded")

        stdout = io.StringIO()
        with patch("rez.module_root_path", fake_root):
            with patch("rez.resolved_context.ResolvedContext", side_effect=fake_resolved_context):
                with patch.object(benchmark, "get_system_info", return_value={"rez_version": "0.0"}):
                    with contextlib.redirect_stdout(stdout):
                        benchmark.do_resolves()

        with open(os.path.join(out_dir, "resolves.json")) as f:
            resolves = json.load(f)
        self.assertEqual(len(resolves), 3)
        self.assertEqual(resolves[0]["status"], "success")
        self.assertEqual(resolves[0]["resolved_packages"], [os.path.join("foo", "1.0")])
        self.assertEqual(resolves[1]["status"], "failed")
        self.assertEqual(resolves[2]["status"], "error")
        self.assertEqual(resolves[2]["error"], "solver exploded")

        with open(os.path.join(out_dir, "summary.json")) as f:
            summary = json.load(f)
        self.assertEqual(summary["num_success_resolves"], 2)
        self.assertEqual(summary["num_failed_resolves"], 1)
        self.assertEqual(summary["num_error_resolves"], 1)
        self.assertEqual(summary["rez_version"], "0.0")
        for key in ("median", "mean", "min", "max", "stddev"):
            self.assertIn(key, summary)

    def test_do_resolves_all_errors_omits_timing_stats(self) -> None:
        """do_resolves omits timing stats when all resolves raise errors."""
        out_dir = os.path.join(self.work_dir, "out_err")
        os.mkdir(out_dir)
        fake_root = os.path.join(self.work_dir, "rez_root_err")
        req_dir = os.path.join(fake_root, "data", "benchmarking")
        os.makedirs(req_dir)
        with open(os.path.join(req_dir, "requests.json"), "w") as f:
            json.dump([["boom"]], f)

        benchmark.out_dir = out_dir
        benchmark.pkg_repo_dir = os.path.join(out_dir, "packages")
        benchmark._opts = argparse.Namespace(iterations=1)

        stdout = io.StringIO()
        with patch("rez.module_root_path", fake_root):
            with patch("rez.resolved_context.ResolvedContext", side_effect=RuntimeError("fail")):
                with patch.object(benchmark, "get_system_info", return_value={}):
                    with contextlib.redirect_stdout(stdout):
                        benchmark.do_resolves()

        with open(os.path.join(out_dir, "summary.json")) as f:
            summary = json.load(f)
        self.assertEqual(summary["num_success_resolves"], 0)
        self.assertEqual(summary["num_error_resolves"], 1)
        self.assertNotIn("mean", summary)

    def test_print_histogram(self) -> None:
        """print_histogram buckets resolve_time entries and prints 40 histogram rows."""
        out_dir = os.path.join(self.work_dir, "hist_out")
        os.mkdir(out_dir)
        resolves = [
            {"request": ["err"], "status": "error"},
            {"request": ["a"], "resolve_time": 0.1},
            {"request": ["b"], "resolve_time": 0.5},
            {"request": ["c"], "resolve_time": 2.1},
        ]
        with open(os.path.join(out_dir, "resolves.json"), "w") as f:
            json.dump(resolves, f)

        benchmark.out_dir = out_dir
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            benchmark.print_histogram()

        lines = stdout.getvalue().strip().splitlines()
        self.assertEqual(len(lines), 40)
        self.assertTrue(any("#" in line for line in lines))
        self.assertIn("#", lines[-1])
        self.assertIn("|", lines[0])

    def test_compare_matching_with_length_mismatch(self) -> None:
        """compare prints percentage deltas when resolves match (skipping extra entries)."""
        dir1 = os.path.join(self.work_dir, "cmp1")
        dir2 = os.path.join(self.work_dir, "cmp2")
        os.mkdir(dir1)
        os.mkdir(dir2)

        with open(os.path.join(dir1, "resolves.json"), "w") as f:
            json.dump(
                [
                    {"request": ["a"], "resolved_packages": ["a/1.0"]},
                    {"request": ["b"], "resolved_packages": ["b/1.0"]},
                ],
                f,
            )
        with open(os.path.join(dir2, "resolves.json"), "w") as f:
            json.dump(
                [
                    {"request": ["a"], "resolved_packages": ["a/1.0"]},
                ],
                f,
            )

        summary1 = {"max": 2.0, "min": 1.0, "mean": 1.5, "median": 1.5, "stddev": 0.5}
        summary2 = {"max": 1.5, "min": 1.2, "mean": 1.5, "median": 1.35, "stddev": 0.6}
        with open(os.path.join(dir1, "summary.json"), "w") as f:
            json.dump(summary1, f)
        with open(os.path.join(dir2, "summary.json"), "w") as f:
            json.dump(summary2, f)

        benchmark.out_dir = dir1
        benchmark._opts = argparse.Namespace(compare=dir2)

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            benchmark.compare()

        deltas = json.loads(stdout.getvalue())
        self.assertEqual(deltas["max_delta"][1], "-25.00%")
        self.assertEqual(deltas["min_delta"][1], "+20.00%")
        self.assertEqual(deltas["mean_delta"][1], "+0.00%")

    def test_compare_mismatch_exits(self) -> None:
        """compare exits with code 1 and prints mismatch details when resolves differ."""
        dir1 = os.path.join(self.work_dir, "mismatch1")
        dir2 = os.path.join(self.work_dir, "mismatch2")
        os.mkdir(dir1)
        os.mkdir(dir2)

        with open(os.path.join(dir1, "resolves.json"), "w") as f:
            json.dump([{"request": ["a"], "resolved_packages": ["a/1.0"]}], f)
        with open(os.path.join(dir2, "resolves.json"), "w") as f:
            json.dump([{"request": ["a"], "resolved_packages": ["a/2.0"]}], f)

        benchmark.out_dir = dir1
        benchmark._opts = argparse.Namespace(compare=dir2)

        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as cm:
                benchmark.compare()

        self.assertEqual(cm.exception.code, 1)
        self.assertIn("MISMATCHING RESULT (#0):", stderr.getvalue())
