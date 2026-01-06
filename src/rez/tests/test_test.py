# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
test rez package.py unit tests
"""
from rez.tests.util import TestBase, TempdirMixin
from rez.resolved_context import ResolvedContext
from rez.package_test import PackageTestRunner


class TestTest(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls):
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
    def tearDownClass(cls):
        TempdirMixin.tearDownClass()

    def test_1(self):
        """package.py unit tests are correctly run in a testing environment"""
        self.inject_python_repo()
        context = ResolvedContext(["testing_obj", "python"])
        self._run_tests(context)

    def test_2(self):
        """package.py unit tests are correctly run in a testing environment when no verbosity is set"""
        self.inject_python_repo()
        context = ResolvedContext(["testing_obj", "python"])
        # This will get us more code coverage :)
        self._run_tests(context, verbose=0)

    def _run_tests(self, r, verbose=2):
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
        self.assertEqual(1, len(test_names))

        for test_name in test_names:
            runner.run_test(test_name)

        self.assertEqual(runner.test_results.num_tests, 1)

        self.assertEqual(
            self._get_test_result(runner, "move_meeting_to_noon")["status"],
            "failed",
            "move_meeting_to_noon did not fail",
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
