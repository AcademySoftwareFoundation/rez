from rez.cli.lint import linter, LintNull
from rez.tests.util import TestBase, TempdirMixin
import rez.vendor.unittest2 as unittest
import os


class TestLint(TestBase, TempdirMixin):

    @classmethod
    def setUpClass(cls):
        TempdirMixin.setUpClass()

        cls.settings = dict()
        cls.test_variable = "LINT_TEST_VARIABLE"

    @classmethod
    def tearDownClass(cls):
        TempdirMixin.tearDownClass()

    def assertConsumed(self, expected, actual):
        self.assertEqual(expected[0], actual[0], "consumed path error")
        self.assertEqual(expected[1], map(str, actual[1]), "exceptions error")


class TestLintOk(TestLint):

    @classmethod
    def setUpClass(cls):
        TestLint.setUpClass()

        cls.test_file = os.path.join(cls.root, "LINT_TEST_FILE")
        with open(cls.test_file, "w") as fd:
            fd.write("Hello, World!")

    def test_variable_with_file(self):
        os.environ[self.test_variable] = self.test_file
        consumed = linter(self.test_variable)

        self.assertEqual(1, len(consumed))
        self.assertConsumed((self.test_file, ["single file"]), consumed[0])

    def test_valid_variable(self):
        os.environ[self.test_variable] = self.root
        consumed = linter(self.test_variable)

        self.assertEqual(1, len(consumed))
        self.assertConsumed((self.root, []), consumed[0])


class TestLintFailures(TestLint):

    def test_variable_with_no_paths(self):

        os.environ[self.test_variable] = ""
        consumed = linter(self.test_variable)

        self.assertEqual(0, len(consumed))

    def test_variable_with_empty_paths(self):

        os.environ[self.test_variable] = "  "
        consumed = linter(self.test_variable)

        self.assertEqual(1, len(consumed))
        self.assertConsumed(("  ", ["null"]), consumed[0])

    def test_variable_with_missing_path(self):

        os.environ[self.test_variable] = "/foo"
        consumed = linter(self.test_variable)

        self.assertEqual(1, len(consumed))
        self.assertConsumed(("/foo", ["not found"]), consumed[0])

    def test_variable_exists_but_empty(self):
        os.environ[self.test_variable] = self.root
        consumed = linter(self.test_variable)

        self.assertEqual(1, len(consumed))
        self.assertConsumed((self.root, ["empty"]), consumed[0])

    def test_variable_with_duplicate_path(self):
        os.environ[self.test_variable] = os.pathsep.join(["/foo", "/foo"])
        consumed = linter(self.test_variable)

        self.assertEqual(2, len(consumed))
        self.assertConsumed(("/foo", ["not found"]), consumed[0])
        self.assertConsumed(("/foo", ["duplicate"]), consumed[1])


def get_test_suites():

    suites = []
    tests = [TestLintFailures]

    for test in tests:
        suites.append(unittest.TestLoader().loadTestsFromTestCase(test))

    return suites


if __name__ == '__main__':

    unittest.main()
