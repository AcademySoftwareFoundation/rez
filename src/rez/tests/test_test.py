# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
test rez package.py unit tests
"""
import os
import textwrap

from rez.tests.util import TestBase, TempdirMixin
from rez.resolved_context import ResolvedContext
from rez.package_test import PackageTestRunner


class TestTest(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls) -> None:
        TempdirMixin.setUpClass()

        packages_path = cls.data_path("builds", "packages")
        cls.settings = dict(
            packages_path=[packages_path],
            package_filter=None,
            implicit_packages=[],
            warn_untimestamped=False,
            resolve_caching=False
        )

    @classmethod
    def tearDownClass(cls) -> None:
        TempdirMixin.tearDownClass()

    def test_1(self) -> None:
        """package.py unit tests are correctly run in a testing environment"""
        self.inject_python_repo()
        context = ResolvedContext(["testing_obj", "python"])
        self._run_tests(context)

    def test_2(self) -> None:
        """package.py unit tests are correctly run in a testing environment when no verbosity is set"""
        self.inject_python_repo()
        context = ResolvedContext(["testing_obj", "python"])
        # This will get us more code coverage :)
        self._run_tests(context, verbose=0)

    def test_combined_package_base_root_bindings(self) -> None:
        """base/root bind safely on combined packages, where they are None.

        Regression for the #1758 crash class: binding 'base' called
        executor.normalize_path(None), which crashes on Windows, where
        normalize_path delegates to a shell helper that assumes a string
        (to_windows_path). The same crash class also exists in
        resolved_context._bind_rez_info, fixed by #1759 - until that PR
        merges, Windows runs of this test error there, before reaching the
        package_test path guarded below (this PR must merge after #1759).
        On Linux normalize_path is an identity function, so this test
        cannot reproduce the crash locally - the Windows CI matrix is the
        red/green verification. This test pins the cross-platform contract:
        for a combined (py) package, pre_test_commands run with base and
        root bound as None, and assigning them to env vars yields the
        literal string "None", matching the combined-package convention
        established by #1759.
        """
        self.inject_python_repo()
        context = ResolvedContext(["python"])

        pkg_dir = os.path.join(self.root, "combined_pkgs")
        os.makedirs(pkg_dir, exist_ok=True)
        # py-COMBINED format (single .py at the repo root): pre_test_commands
        # are late-called. Note: in yaml-combined packages pre_test_commands
        # are currently a silent no-op (source arrives as a plain str, which
        # RexExecutor.compile_code execs without the trailing auto-call) -
        # separate issue, not covered here.
        # The check script asserts the #1759 convention: for combined
        # packages, base and root bind as None, and env assignment yields
        # the literal string "None". The test command runs in the caller's
        # cwd, so the script is referenced by absolute path (forward-slash
        # form: safe both as a Python string literal in the fixture and as
        # an argument on Windows).
        check_script = os.path.join(pkg_dir, "_check_combined_bindings.py")
        with open(check_script, "w") as f:
            f.write(textwrap.dedent("""\
                import os
                import sys

                base = os.environ.get("REZ_CB_BASE")
                root = os.environ.get("REZ_CB_ROOT")
                sys.exit(0 if base == "None" and root == "None" else 1)
            """))

        pkg_src = textwrap.dedent("""\
                name = 'combined_binding_tester'
                versions = ['1.0']

                def pre_test_commands():
                    env.REZ_CB_BASE = base
                    env.REZ_CB_ROOT = root

                tests = {
                    'check_combined_bindings': {
                        # Run a script file rather than a `python -c`
                        # payload: the Windows shells mangle double quotes
                        # inside command arguments, which silently rewrites
                        # string literals in a -c payload. A file path has
                        # no quoting to lose.
                        'command': ['python', '%s'],
                        'requires': ['python'],
                    }
                }
            """ % check_script.replace(os.sep, "/"))

        with open(
            os.path.join(pkg_dir, "combined_binding_tester.py"), "w"
        ) as f:
            f.write(pkg_src)

        runner = PackageTestRunner(
            package_request="combined_binding_tester",
            package_paths=[pkg_dir] + context.package_paths,
            stop_on_fail=False,
            verbose=0
        )
        runner.run_test("check_combined_bindings")

        result = self._get_test_result(runner, "check_combined_bindings")
        self.assertIsNotNone(result)
        self.assertEqual(
            result["status"],
            "success",
            "combined-package pre_test_commands base/root binding test "
            "failed: %s" % result
        )

    def _run_tests(self, r, verbose: int = 2) -> None:
        """Run unit tests in package.py"""
        self.inject_python_repo()
        runner = PackageTestRunner(
            package_request="testing_obj",
            package_paths=r.package_paths,
            stop_on_fail=False,
            verbose=verbose
        )

        test_names = runner.get_test_names()

        for test_name in test_names:
            runner.run_test(test_name)

        self.assertEqual(runner.test_results.num_tests, 5)
        self.assertEqual(
            self._get_test_result(runner, "check_car_ideas")["status"],
            "success",
            "check_car_ideas did not succeed",
        )
        self.assertEqual(
            self._get_test_result(runner, "move_meeting_to_noon")["status"],
            "failed",
            "move_meeting_to_noon did not fail",
        )
        self.assertEqual(
            self._get_test_result(runner, "command_as_string_success")["status"],
            "success",
            "command_as_string_success did not succeed",
        )
        self.assertEqual(
            self._get_test_result(runner, "command_as_string_fail")["status"],
            "failed",
            "command_as_string_fail did not fail",
        )
        self.assertEqual(
            self._get_test_result(runner, "pre_test_commands_bindings")["status"],
            "success",
            "pre_test_commands_bindings did not succeed",
        )

    def _get_test_result(self, runner, test_name):
        return next(
            (result for result in runner.test_results.test_results if result.get("test_name") == test_name),
            None
        )

    def test_wildcard_01(self):
        """package.py unit tests are correctly found with a wildcard then run in a testing environment"""
        self.inject_python_repo()
        context = ResolvedContext(["testing_obj", "python"])
        # This will get us more code coverage :)
        self.inject_python_repo()
        runner = PackageTestRunner(
            package_request="testing_obj",
            package_paths=context.package_paths,
        )

        test_names = runner.find_requested_test_names(["command_as_*"])
        self.assertEqual(2, len(test_names))

        for test_name in test_names:
            runner.run_test(test_name)

        self.assertEqual(runner.test_results.num_tests, 2)

        self.assertEqual(
            self._get_test_result(runner, "command_as_string_success")["status"],
            "success",
            "command_as_string_success did not succeed",
        )
        self.assertEqual(
            self._get_test_result(runner, "command_as_string_fail")["status"],
            "failed",
            "command_as_string_fail did not fail",
        )

    def test_wildcard_02(self):
        """
        package.py unit tests are correctly found with a wildcard + a package name then run
        in a testing environment
        """
        self.inject_python_repo()
        context = ResolvedContext(["testing_obj", "python"])
        # This will get us more code coverage :)
        self.inject_python_repo()
        runner = PackageTestRunner(
            package_request="testing_obj",
            package_paths=context.package_paths,

        )

        test_names = runner.find_requested_test_names(["command_as_*", "check_car_ideas"])
        self.assertEqual(3, len(test_names))

        for test_name in test_names:
            runner.run_test(test_name)

        self.assertEqual(runner.test_results.num_tests, 3)

        self.assertEqual(
            self._get_test_result(runner, "check_car_ideas")["status"],
            "success",
            "check_car_ideas did not succeed",
        )
        self.assertEqual(
            self._get_test_result(runner, "command_as_string_success")["status"],
            "success",
            "command_as_string_success did not succeed",
        )
        self.assertEqual(
            self._get_test_result(runner, "command_as_string_fail")["status"],
            "failed",
            "command_as_string_fail did not fail",
        )

    def test_wildcard_03(self):
        """
        package.py unit tests are correctly found with a wildcard equivalent to 'default' then run
        in a testing environment
        """
        self.inject_python_repo()
        context = ResolvedContext(["testing_obj", "python"])
        # This will get us more code coverage :)
        self.inject_python_repo()
        runner = PackageTestRunner(
            package_request="testing_obj",
            package_paths=context.package_paths,

        )

        test_names = runner.find_requested_test_names(["*"])
        self.assertEqual(5, len(test_names))

        for test_name in test_names:
            runner.run_test(test_name)

        self.assertEqual(runner.test_results.num_tests, 5)

        self.assertEqual(
            self._get_test_result(runner, "check_car_ideas")["status"],
            "success",
            "check_car_ideas did not succeed",
        )
        self.assertEqual(
            self._get_test_result(runner, "move_meeting_to_noon")["status"],
            "failed",
            "move_meeting_to_noon did not fail",
        )
        self.assertEqual(
            self._get_test_result(runner, "command_as_string_success")["status"],
            "success",
            "command_as_string_success did not succeed",
        )
        self.assertEqual(
            self._get_test_result(runner, "command_as_string_fail")["status"],
            "failed",
            "command_as_string_fail did not fail",
        )
        self.assertEqual(
            self._get_test_result(runner, "pre_test_commands_bindings")["status"],
            "success",
            "pre_test_commands_bindings did not succeed",
        )

    def test_wildcard_04(self):
        """
        package.py unit tests are correctly found with a wildcard which get all test starting by 'c' and
        the second letter is 'h' or 'o' then run in a testing environment
        """
        self.inject_python_repo()
        context = ResolvedContext(["testing_obj", "python"])
        # This will get us more code coverage :)
        self.inject_python_repo()
        runner = PackageTestRunner(
            package_request="testing_obj",
            package_paths=context.package_paths,

        )

        test_names = runner.find_requested_test_names(["c[ho]*"])
        self.assertEqual(3, len(test_names))

        for test_name in test_names:
            runner.run_test(test_name)

        self.assertEqual(runner.test_results.num_tests, 3)

        self.assertEqual(
            self._get_test_result(runner, "check_car_ideas")["status"],
            "success",
            "check_car_ideas did not succeed",
        )
        self.assertEqual(
            self._get_test_result(runner, "command_as_string_success")["status"],
            "success",
            "command_as_string_success did not succeed",
        )
        self.assertEqual(
            self._get_test_result(runner, "command_as_string_fail")["status"],
            "failed",
            "command_as_string_fail did not fail",
        )

    def test_wildcard_05(self):
        """
        package.py unit tests are correctly found with a wildcard which get all test which is not starting by 'c'
        then run in a testing environment
        """
        self.inject_python_repo()
        context = ResolvedContext(["testing_obj", "python"])
        # This will get us more code coverage :)
        self.inject_python_repo()
        runner = PackageTestRunner(
            package_request="testing_obj",
            package_paths=context.package_paths,

        )

        test_names = runner.find_requested_test_names(["[!c]*"])
        self.assertEqual(2, len(test_names))

        for test_name in test_names:
            runner.run_test(test_name)

        self.assertEqual(runner.test_results.num_tests, 2)

        self.assertEqual(
            self._get_test_result(runner, "move_meeting_to_noon")["status"],
            "failed",
            "move_meeting_to_noon did not fail",
        )
        self.assertEqual(
            self._get_test_result(runner, "pre_test_commands_bindings")["status"],
            "success",
            "pre_test_commands_bindings did not succeed",
        )

    def test_empty_test_list(self):
        """
        package.py unit tests are correctly found when no test name is provided (empty list)
        """
        self.inject_python_repo()
        context = ResolvedContext(["testing_obj", "python"])
        # This will get us more code coverage :)
        self.inject_python_repo()
        runner = PackageTestRunner(
            package_request="testing_obj",
            package_paths=context.package_paths,

        )

        test_names = runner.find_requested_test_names([])
        self.assertEqual(4, len(test_names))

        for test_name in test_names:
            runner.run_test(test_name)

        self.assertEqual(runner.test_results.num_tests, 4)

        self.assertEqual(
            self._get_test_result(runner, "check_car_ideas")["status"],
            "success",
            "check_car_ideas did not succeed",
        )
        self.assertEqual(
            self._get_test_result(runner, "move_meeting_to_noon")["status"],
            "failed",
            "move_meeting_to_noon did not fail",
        )
        self.assertEqual(
            self._get_test_result(runner, "command_as_string_success")["status"],
            "success",
            "command_as_string_success did not succeed",
        )
        self.assertEqual(
            self._get_test_result(runner, "command_as_string_fail")["status"],
            "failed",
            "command_as_string_fail did not fail",
        )
