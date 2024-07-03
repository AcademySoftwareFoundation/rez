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
        context = ResolvedContext(["testing_obj"])
        self._run_tests(context)

    def _run_tests(self, r):
        """Run unit tests in package.py"""
        self.inject_python_repo()
        runner = PackageTestRunner(
            package_request="testing_obj",
            package_paths=r.package_paths,
            stop_on_fail=False,
            verbose=2
        )

        test_names = runner.get_test_names()

        for test_name in test_names:
            runner.run_test(test_name)

        successful_test = self._get_test_result(runner, "check_car_ideas")
        failed_test = self._get_test_result(runner, "move_meeting_to_noon")

        self.assertEqual(runner.test_results.num_tests, 2)
        self.assertEqual(successful_test["status"], "success")
        self.assertEqual(failed_test["status"], "failed")

    def _get_test_result(self, runner, test_name):
        return next(
            (result for result in runner.test_results.test_results if result.get("test_name") == test_name),
            None
        )
