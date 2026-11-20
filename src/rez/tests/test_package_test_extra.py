# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Additional unit tests for rez.package_test
"""
from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from unittest import mock

from rez.exceptions import PackageNotFoundError, PackageTestError, RezError
from rez.package_test import PackageTestResults, PackageTestRunner
from rez.resolved_context import ResolvedContext
from rez.tests.util import TestBase
from rez.utils.formatting import PackageRequest
from rez.utils.sourcecode import SourceCode


class TestPackageTestExtra(TestBase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.settings = dict(
            package_filter=None,
            implicit_packages=[],
            warn_untimestamped=False,
            resolve_caching=False,
        )

    def _setup_memory_repo(self, packages: dict) -> list[str]:
        from rez.package_repository import package_repository_manager

        mem_path = "memory@%s" % hex(id(packages))
        repo = package_repository_manager.get_repository(mem_path)
        repo.data = packages
        return [mem_path]

    def test_verbose_bool_and_get_package_caching(self) -> None:
        """verbose accepts bool for backwards compat and get_package caches result."""
        paths = self._setup_memory_repo({
            "foo": {
                "1.0": {
                    "name": "foo",
                    "version": "1.0",
                }
            }
        })
        runner_true = PackageTestRunner("foo", package_paths=paths, verbose=True)
        self.assertEqual(runner_true.verbose, 2)

        runner_false = PackageTestRunner("foo", package_paths=paths, verbose=False)
        self.assertEqual(runner_false.verbose, 0)

        pkg1 = runner_true.get_package()
        pkg2 = runner_true.get_package()
        self.assertIsNotNone(pkg1)
        self.assertIs(pkg1, pkg2)

    def test_get_package_not_found(self) -> None:
        """get_package raises PackageNotFoundError when package cannot be found."""
        paths = self._setup_memory_repo({})
        runner = PackageTestRunner("nonexistent_pkg", package_paths=paths)
        with self.assertRaises(PackageNotFoundError):
            runner.get_package()

    def test_use_current_env_no_current_context(self) -> None:
        """use_current_env returns None/empty when no current context exists."""
        with mock.patch.object(ResolvedContext, "get_current", return_value=None):
            runner = PackageTestRunner("foo", use_current_env=True)
            self.assertIsNone(runner.get_package())
            self.assertEqual(runner.get_test_names(), [])

    def test_use_current_env_package_not_in_context(self) -> None:
        """use_current_env returns None when target package is not in current context."""
        paths = self._setup_memory_repo({
            "other": {"1.0": {"name": "other", "version": "1.0"}},
            "foo": {"1.0": {"name": "foo", "version": "1.0"}},
        })
        ctx = ResolvedContext(["other==1.0"], package_paths=paths)
        with mock.patch.object(ResolvedContext, "get_current", return_value=ctx):
            runner = PackageTestRunner("foo", use_current_env=True)
            self.assertIsNone(runner.get_package())

    def test_use_current_env_version_mismatch(self) -> None:
        """use_current_env returns None when current context version does not match."""
        paths = self._setup_memory_repo({
            "foo": {"1.0": {"name": "foo", "version": "1.0"}},
        })
        ctx = ResolvedContext(["foo==1.0"], package_paths=paths)
        with mock.patch.object(ResolvedContext, "get_current", return_value=ctx):
            runner = PackageTestRunner("foo>=2.0", use_current_env=True)
            self.assertIsNone(runner.get_package())

    def test_use_current_env_run_success_and_unmet_requires(self) -> None:
        """use_current_env runs matching tests and fails when current env lacks requires."""
        paths = self._setup_memory_repo({
            "foo": {
                "1.0": {
                    "name": "foo",
                    "version": "1.0",
                    "tests": {
                        "ok_test": {
                            "command": [sys.executable, "-c", "pass"],
                        },
                        "needs_bar": {
                            "command": [sys.executable, "-c", "pass"],
                            "requires": ["bar"],
                        },
                    },
                }
            },
            "bar": {"1.0": {"name": "bar", "version": "1.0"}},
        })
        ctx = ResolvedContext(["foo==1.0"], package_paths=paths)
        with mock.patch.object(ResolvedContext, "get_current", return_value=ctx):
            runner = PackageTestRunner("foo==1.0", use_current_env=True)
            self.assertEqual(runner.run_test("ok_test"), 0)
            self.assertEqual(runner.num_success, 1)

            ret = runner.run_test("needs_bar")
            self.assertEqual(ret, -1)
            self.assertEqual(runner.num_failed, 1)

            with self.assertRaises(PackageTestError):
                runner.run_test("no_such_test")

    def test_get_package_test_names_run_on_and_ran_once(self) -> None:
        """get_package_test_names filters by run_on (str/list/default) and ran_once."""
        paths = self._setup_memory_repo({
            "pkg": {
                "1.0": {
                    "name": "pkg",
                    "version": "1.0",
                    "tests": {
                        "str_test": "echo hi",
                        "list_run_on": {
                            "command": "echo ci",
                            "run_on": ["ci", "nightly"],
                        },
                        "str_run_on": {
                            "command": "echo rel",
                            "run_on": "release",
                        },
                        "on_var_true": {
                            "command": "echo v",
                            "on_variants": True,
                        },
                        "on_var_false": {
                            "command": "echo nv",
                            "on_variants": False,
                        },
                    },
                }
            }
        })
        runner = PackageTestRunner("pkg", package_paths=paths)
        pkg = runner.get_package()

        self.assertEqual(
            PackageTestRunner.get_package_test_names(pkg, run_on=["default"]),
            ["on_var_false", "on_var_true", "str_test"],
        )
        self.assertEqual(
            PackageTestRunner.get_package_test_names(pkg, run_on=["ci"]),
            ["list_run_on"],
        )
        self.assertEqual(
            PackageTestRunner.get_package_test_names(pkg, run_on=["release"]),
            ["str_run_on"],
        )
        self.assertEqual(
            PackageTestRunner.get_package_test_names(
                pkg,
                ran_once=["str_test", "on_var_false", "on_var_true"],
            ),
            ["list_run_on", "on_var_true", "str_run_on"],
        )

    def test_results_properties_cumulative_and_print_summary(self) -> None:
        """PackageTestRunner properties, cumulative results, and print_summary work."""
        paths = self._setup_memory_repo({
            "pkg": {
                "1.0": {
                    "name": "pkg",
                    "version": "1.0",
                    "tests": {
                        "pass_t": [sys.executable, "-c", "import sys; sys.exit(0)"],
                        "fail_t": [sys.executable, "-c", "import sys; sys.exit(1)"],
                    },
                }
            }
        })
        cumulative = PackageTestResults()
        with self.assertRaises(RuntimeError):
            cumulative.add_test_result("t", None, "invalid_status", "bad")

        runner = PackageTestRunner(
            "pkg",
            package_paths=paths,
            cumulative_test_results=cumulative,
        )
        self.assertEqual(runner.run_test("pass_t"), 0)
        self.assertEqual(runner.run_test("fail_t"), 1)

        dry_runner = PackageTestRunner(
            "pkg",
            package_paths=paths,
            dry_run=True,
            verbose=1,
            cumulative_test_results=cumulative,
        )
        self.assertEqual(dry_runner.run_test("pass_t"), 0)

        self.assertEqual(runner.num_tests, 2)
        self.assertEqual(runner.num_success, 1)
        self.assertEqual(runner.num_failed, 1)
        self.assertEqual(runner.num_skipped, 0)

        self.assertEqual(cumulative.num_tests, 3)
        self.assertEqual(cumulative.num_success, 1)
        self.assertEqual(cumulative.num_failed, 1)
        self.assertEqual(cumulative.num_skipped, 1)

        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            runner.print_summary()
        output = buf.getvalue()
        self.assertIn("1 succeeded, 1 failed, 0 skipped", output)
        self.assertIn("pass_t", output)
        self.assertIn("fail_t", output)

    def test_on_variants_requires_filter(self) -> None:
        """on_variants type='requires' filters variants by requirements and conflicts."""
        paths = self._setup_memory_repo({
            "depA": {"1": {"name": "depA", "version": "1"}},
            "depB": {"1": {"name": "depB", "version": "1"}},
            "mvar": {
                "1.0": {
                    "name": "mvar",
                    "version": "1.0",
                    "variants": [
                        ["depA-1"],
                        ["depB-1"],
                        ["depA-1", "depB-1"],
                    ],
                    "tests": {
                        "only_a": {
                            "command": [sys.executable, "-c", "pass"],
                            "on_variants": {"type": "requires", "value": ["depA"]},
                        },
                        "not_a": {
                            "command": [sys.executable, "-c", "pass"],
                            "on_variants": {"type": "requires", "value": ["!depA"]},
                        },
                    },
                }
            },
        })
        runner = PackageTestRunner("mvar", package_paths=paths)
        self.assertEqual(runner.run_test("only_a"), 0)
        self.assertEqual(runner.num_success, 2)
        self.assertEqual(runner.num_skipped, 1)

        runner2 = PackageTestRunner("mvar", package_paths=paths)
        self.assertEqual(runner2.run_test("not_a"), 0)
        self.assertEqual(runner2.num_success, 1)
        self.assertEqual(runner2.num_skipped, 2)

    def test_extra_test_args_extra_requests_and_unversioned(self) -> None:
        """extra_test_args (str), extra_package_requests, verbose=1, unversioned pkg."""
        paths = self._setup_memory_repo({
            "depA": {"1": {"name": "depA", "version": "1"}},
            "unver": {
                "_NO_VERSION": {
                    "name": "unver",
                    "tests": {
                        "str_cmd": (
                            "%s -c \"import os, sys; "
                            "sys.exit(0 if sys.argv[1:] == ['a', 'b c'] "
                            "and os.environ.get('REZ_DEPA_VERSION') == '1' else 1)\""
                            % sys.executable
                        ),
                        "list_cmd": [
                            sys.executable,
                            "-c",
                            (
                                "import os, sys; "
                                "sys.exit(0 if os.environ.get('REZ_DEPA_VERSION') == '1' else 1)"
                            ),
                        ],
                        "ci_only": {
                            "command": [sys.executable, "-c", "pass"],
                            "run_on": ["ci"],
                        },
                    },
                }
            },
        })
        runner = PackageTestRunner(
            "unver",
            package_paths=paths,
            extra_package_requests=[PackageRequest("depA")],
            verbose=1,
        )
        self.assertEqual(runner.run_test("str_cmd", extra_test_args=["a", "b c"]), 0)
        self.assertEqual(runner.run_test("list_cmd"), 0)
        self.assertEqual(runner.num_success, 2)

        # Also exercise find_requested_test_names (empty, explicit non-default, wildcard)
        self.assertEqual(sorted(runner.find_requested_test_names([])), ["list_cmd", "str_cmd"])
        self.assertEqual(runner.find_requested_test_names(["ci_only"]), {"ci_only"})
        self.assertEqual(runner.get_test_names(run_on=["ci"]), ["ci_only"])
        self.assertEqual(runner.find_requested_test_names(["str_*"]), {"str_cmd"})

    @unittest.expectedFailure
    def test_list_command_extra_test_args(self) -> None:
        """list command with extra_test_args double-quotes args (src/rez/package_test.py:424)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            script = os.path.join(tmpdir, "check_args.py")
            with open(script, "w") as f:
                f.write(
                    "import sys\n"
                    "print(repr(sys.argv[1:]))\n"
                    "sys.exit(0 if sys.argv[1:] == ['x', 'y z'] else 1)\n"
                )
            paths = self._setup_memory_repo({
                "pkg": {
                    "1.0": {
                        "name": "pkg",
                        "version": "1.0",
                        "tests": {
                            "list_cmd": [sys.executable, script],
                        },
                    }
                },
            })
            buf = io.StringIO()
            runner = PackageTestRunner("pkg", package_paths=paths, stdout=buf)
            ret = runner.run_test("list_cmd", extra_test_args=["x", "y z"])
            self.assertEqual(ret, 0)
            self.assertIn("['x', 'y z']", buf.getvalue())

    def test_context_conflict_and_multiple_failures_stop_on_fail_false(self) -> None:
        """Unresolvable conflict (context.success=False) and multiple failures with stop_on_fail=False."""
        paths = self._setup_memory_repo({
            "depA": {
                "1": {"name": "depA", "version": "1"},
                "2": {"name": "depA", "version": "2"},
            },
            "pkg": {
                "1.0": {
                    "name": "pkg",
                    "version": "1.0",
                    "variants": [["depA-1"], ["depA-2"]],
                    "tests": {
                        "conflict_t": {
                            "command": [sys.executable, "-c", "pass"],
                            "requires": ["depA==99"],
                            "on_variants": True,
                        },
                        "fail_both": {
                            "command": [sys.executable, "-c", "import sys; sys.exit(3)"],
                            "on_variants": True,
                        },
                        "empty_t": "",
                        "rel_t": {
                            "command": [sys.executable, "-c", "pass"],
                            "run_on": "release",
                        },
                        "only_var1_resolvable": {
                            "command": [sys.executable, "-c", "pass"],
                            "requires": ["depA==2"],
                        },
                    },
                }
            },
        })
        runner = PackageTestRunner(
            "pkg",
            package_paths=paths,
            stop_on_fail=False,
            verbose=2,
        )
        # conflict_t fails to resolve on both variants -> hits context.success=False,
        # print_info(stderr), and second-failure exitcode branch (384->387)
        self.assertEqual(runner.run_test("conflict_t"), -1)
        self.assertEqual(runner.num_failed, 2)

        # fail_both fails on both variants -> hits second-failure branch (492->495)
        self.assertEqual(runner.run_test("fail_both"), 3)
        self.assertEqual(runner.num_failed, 4)

        # empty_t hits _get_test_info returning None (line 558)
        self.assertEqual(runner.run_test("empty_t"), 0)
        self.assertEqual(runner.num_skipped, 2)

        # rel_t hits run_on as str in _get_test_info (lines 584-585) and
        # _get_target_variants looping past variant 0 to preferred variant 1 (681->655)
        self.assertEqual(runner.run_test("rel_t"), 0)
        self.assertEqual(runner.num_success, 1)

        # only_var1_resolvable hits context.success=False in _get_target_variants (line 676)
        self.assertEqual(runner.run_test("only_var1_resolvable"), 0)
        self.assertEqual(runner.num_success, 2)

    def test_use_current_env_cached_pkg_with_missing_current_context(self) -> None:
        """_get_context returns None when use_current_env=True and current context is None."""
        runner = PackageTestRunner("foo==1.0", use_current_env=True)
        with mock.patch.object(ResolvedContext, "get_current", return_value=None):
            self.assertIsNone(runner._get_context(["foo==1.0"]))

    def test_stop_on_fail_command_and_resolve_failures(self) -> None:
        """stop_on_fail stops after first failed command or failed resolve."""
        paths = self._setup_memory_repo({
            "depA": {"1": {"name": "depA", "version": "1"}},
            "depB": {"1": {"name": "depB", "version": "1"}},
            "pkg": {
                "1.0": {
                    "name": "pkg",
                    "version": "1.0",
                    "variants": [["depA-1"], ["depB-1"]],
                    "tests": {
                        "fail_cmd": {
                            "command": [sys.executable, "-c", "import sys; sys.exit(2)"],
                            "on_variants": True,
                        },
                        "bad_req": {
                            "command": [sys.executable, "-c", "pass"],
                            "requires": ["nonexistent_dep_xyz"],
                            "on_variants": True,
                        },
                    },
                }
            },
        })
        runner = PackageTestRunner("pkg", package_paths=paths, stop_on_fail=True)
        self.assertEqual(runner.run_test("fail_cmd"), 2)
        self.assertTrue(runner.stopped_on_fail)
        self.assertEqual(runner.num_failed, 1)

        err_buf = io.StringIO()
        runner2 = PackageTestRunner(
            "pkg",
            package_paths=paths,
            stop_on_fail=True,
            stderr=err_buf,
        )
        self.assertEqual(runner2.run_test("bad_req"), -1)
        self.assertTrue(runner2.stopped_on_fail)
        self.assertEqual(runner2.num_failed, 1)

    def test_rez_error_during_context_resolve(self) -> None:
        """RezError raised during context creation is caught and recorded as failed."""
        paths = self._setup_memory_repo({
            "pkg": {
                "1.0": {
                    "name": "pkg",
                    "version": "1.0",
                    "tests": {
                        "t": [sys.executable, "-c", "pass"],
                    },
                }
            }
        })
        runner = PackageTestRunner("pkg", package_paths=paths)
        with mock.patch("rez.package_test.ResolvedContext", side_effect=RezError("boom")):
            ret = runner.run_test("t")
        self.assertEqual(ret, -1)
        self.assertEqual(runner.num_failed, 1)
        self.assertIn("boom", runner.test_results.test_results[0]["description"])

    def test_late_tests_missing_in_variant_and_handle_mismatch(self) -> None:
        """Variants missing a late test or resolving to a different handle are skipped."""
        def _late_tests():
            import sys

            if getattr(this, "index", None) == 1:  # noqa: F821
                return {}
            return {
                "t": {
                    "command": [sys.executable, "-c", "pass"],
                    "on_variants": True,
                }
            }

        sc = SourceCode(func=_late_tests)
        sc.late_binding = True

        paths = self._setup_memory_repo({
            "depA": {"1": {"name": "depA", "version": "1"}},
            "depB": {"1": {"name": "depB", "version": "1"}},
            "latepkg": {
                "1.0": {
                    "name": "latepkg",
                    "version": "1.0",
                    "variants": [["depA-1"], ["depB-1"]],
                    "tests": sc,
                }
            },
        })
        runner = PackageTestRunner("latepkg", package_paths=paths)
        ret = runner.run_test("t")
        self.assertEqual(ret, 0)
        self.assertEqual(runner.num_success, 1)
        self.assertEqual(runner.num_skipped, 1)
        self.assertEqual(
            runner.test_results.test_results[1]["description"],
            "The test is not declared in this variant",
        )

        # Handle mismatch: variant 0 has [] and variant 1 has ["depA-1"], so requiring
        # depA-1 resolves to variant 1 even when running variant 0.
        paths2 = self._setup_memory_repo({
            "depA": {"1": {"name": "depA", "version": "1"}},
            "mismatchpkg": {
                "1.0": {
                    "name": "mismatchpkg",
                    "version": "1.0",
                    "variants": [[], ["depA-1"]],
                    "tests": {
                        "t": {
                            "command": [sys.executable, "-c", "pass"],
                            "requires": ["depA-1"],
                            "on_variants": True,
                        }
                    },
                }
            },
        })
        runner2 = PackageTestRunner("mismatchpkg", package_paths=paths2)
        ret2 = runner2.run_test("t")
        self.assertEqual(ret2, 0)
        self.assertEqual(runner2.num_skipped, 1)
        self.assertEqual(runner2.num_success, 1)
        self.assertEqual(
            runner2.test_results.test_results[0]["description"],
            "Could not resolve to variant (known issue)",
        )
