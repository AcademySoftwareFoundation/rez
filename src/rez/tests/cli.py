import rez.contrib.unittest2 as unittest
import subprocess


tools = [
    "rezolve",
    "rez",
    "rez-settings",
    "rez-build",
    "rez-release",
    "rez-env",
    "rez-context",
    "rez-wrap",
    "rez-tools",
    "rez-exec",
    "rez-test",
    "rez-bootstrap",
    "bez",
    "_rez_fwd"]


class TestCLI(unittest.TestCase):
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
