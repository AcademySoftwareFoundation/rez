import rez.contrib.unittest2 as unittest
from rez.tests.util import TestBase
import subprocess


tools = [
    "rezolve",
    "rez",
    "rez-settings",
    "rez-build",
    "rez-release",
    "rez-env",
    "rez-context",
    "rez-suite",
    "rez-tools",
    "rez-exec",
    "rez-test",
    "rez-bootstrap",
    "bez",
    "_rez_fwd"]


class TestCLI(TestBase):
    def test_tool_invocation(self):
        for tool in tools:
            p = subprocess.Popen([tool, "--help"])
            p.wait()
            self.assertTrue(not p.returncode)


def get_test_suites():
    suites = []
    suite = unittest.TestSuite()
    suite.addTest(TestCLI("test_tool_invocation"))
    suites.append(suite)
    return suites
