"""
Test noninteractive invocation of each type of shell (bash etc), and ensure that
their behaviour is correct wrt shell options such as --rcfile, -c, --stdin etc.
"""

from rez.shells import get_shell_types, create_shell
from rez.resolved_context import ResolvedContext
from rez.tests.util import _stdout
import subprocess
import unittest
import tempfile
import os
import sys



class TestShell(unittest.TestCase):
    def __init__(self, fn, shell):
        unittest.TestCase.__init__(self, fn)
        self.shell = shell
        self.sh = create_shell(shell)

    def test_no_output(self):
        if self.sh.supports_command():
            r = ResolvedContext(["hello_world"])
            p = r.execute_shell(shell=self.shell,
                                command="hello_world -q",
                                stdout=subprocess.PIPE)
            self.assertEqual(_stdout(p), '', \
                "This test and others will fail, because one or more of your "
                "startup scripts are printing to stdout. Please remove the "
                "printout and try again.")

    def test_command(self):
        if self.sh.supports_command():
            r = ResolvedContext(["hello_world"])
            p = r.execute_shell(shell=self.shell,
                                command="hello_world",
                                stdout=subprocess.PIPE)
            self.assertEqual(_stdout(p), "Hello Rez World!")

    def test_command_returncode(self):
        if self.sh.supports_command():
            r = ResolvedContext(["hello_world"])
            p = r.execute_shell(shell=self.shell,
                                command="hello_world -q -r 66",
                                stdout=subprocess.PIPE)
            p.wait()
            self.assertEqual(p.returncode, 66)

    def test_norc(self):
        if self.sh.supports_norc():
            r = ResolvedContext(["hello_world"])
            p = r.execute_shell(shell=self.shell,
                                norc=True,
                                command="hello_world",
                                stdout=subprocess.PIPE)
            self.assertEqual(_stdout(p), "Hello Rez World!")

    def test_stdin(self):
        if self.sh.supports_stdin():
            r = ResolvedContext(["hello_world"])
            p = r.execute_shell(shell=self.shell,
                                stdout=subprocess.PIPE,
                                stdin=subprocess.PIPE)
            stdout,_ = p.communicate(input="hello_world\n")
            stdout = stdout.strip()
            self.assertEqual(stdout, "Hello Rez World!")


def run(verbosity=2):
    suites = []
    for shell in get_shell_types():
        suite = unittest.TestSuite()
        suite.addTest(TestShell("test_no_output", shell))
        suite.addTest(TestShell("test_command", shell))
        suite.addTest(TestShell("test_command_returncode", shell))
        suite.addTest(TestShell("test_norc", shell))
        suite.addTest(TestShell("test_stdin", shell))
        suites.append(suite)

    all_ = unittest.TestSuite(suites)
    unittest.TextTestRunner(verbosity=verbosity).run(all_)
