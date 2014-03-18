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
        try:
            self.sh = create_shell(shell)
        except:
            self.sh = None

    def _create_context(self, pkgs):
        return ResolvedContext(pkgs,
                               caching=False,
                               package_paths=[],
                               add_implicit_packages=False)

    def test_create_shell(self):
        print "\n\nSHELL TYPE: %s" % self.shell
        create_shell(self.shell)

    def test_no_output(self):
        self.assertTrue(self.sh)
        _,_,command,_ = self.sh.startup_capabilities(command=True)
        if command:
            r = self._create_context(["hello_world"])
            p = r.execute_shell(shell=self.shell,
                                command="hello_world -q",
                                stdout=subprocess.PIPE)
            self.assertEqual(_stdout(p), '', \
                "This test and others will fail, because one or more of your "
                "startup scripts are printing to stdout. Please remove the "
                "printout and try again.")

    def test_command(self):
        self.assertTrue(self.sh)
        _,_,command,_ = self.sh.startup_capabilities(command=True)
        if command:
            r = self._create_context(["hello_world"])
            p = r.execute_shell(shell=self.shell,
                                command="hello_world",
                                stdout=subprocess.PIPE)
            self.assertEqual(_stdout(p), "Hello Rez World!")

    def test_command_returncode(self):
        self.assertTrue(self.sh)
        _,_,command,_ = self.sh.startup_capabilities(command=True)
        if command:
            r = self._create_context(["hello_world"])
            p = r.execute_shell(shell=self.shell,
                                command="hello_world -q -r 66",
                                stdout=subprocess.PIPE)
            p.wait()
            self.assertEqual(p.returncode, 66)

    def test_norc(self):
        self.assertTrue(self.sh)
        _,norc,command,_ = self.sh.startup_capabilities(norc=True, command=True)
        if norc and command:
            r = self._create_context(["hello_world"])
            p = r.execute_shell(shell=self.shell,
                                norc=True,
                                command="hello_world",
                                stdout=subprocess.PIPE)
            self.assertEqual(_stdout(p), "Hello Rez World!")

    def test_stdin(self):
        self.assertTrue(self.sh)
        _,_,_,stdin = self.sh.startup_capabilities(stdin=True)
        if stdin:
            r = self._create_context(["hello_world"])
            p = r.execute_shell(shell=self.shell,
                                stdout=subprocess.PIPE,
                                stdin=subprocess.PIPE)
            stdout,_ = p.communicate(input="hello_world\n")
            stdout = stdout.strip()
            self.assertEqual(stdout, "Hello Rez World!")

    def test_rcfile(self):
        self.assertTrue(self.sh)
        rcfile,_,command,_ = self.sh.startup_capabilities(rcfile=True, command=True)
        if rcfile and command:
            f,path = tempfile.mkstemp()
            os.write(f, "hello_world\n")
            os.close(f)

            r = self._create_context(["hello_world"])
            p = r.execute_shell(shell=self.shell,
                                rcfile=path,
                                command="hello_world -q",
                                stdout=subprocess.PIPE)
            self.assertEqual(_stdout(p), "Hello Rez World!")
            os.remove(path)

    def test_rez_command(self):
        """Test that the Rez cli tools have been bound in the target env."""
        self.assertTrue(self.sh)
        _,_,command,_ = self.sh.startup_capabilities(command=True)
        if command:
            r = self._create_context([])
            p = r.execute_shell(shell=self.shell,
                                command="rez-env --bo -c 'hello_world' hello_world",
                                stdout=subprocess.PIPE)
            self.assertEqual(_stdout(p), "Hello Rez World!")


def run(verbosity=2):
    suites = []
    for shell in get_shell_types():
        suite = unittest.TestSuite()
        suite.addTest(TestShell("test_create_shell", shell))
        suite.addTest(TestShell("test_no_output", shell))
        suite.addTest(TestShell("test_command", shell))
        suite.addTest(TestShell("test_command_returncode", shell))
        suite.addTest(TestShell("test_norc", shell))
        suite.addTest(TestShell("test_stdin", shell))
        suite.addTest(TestShell("test_rcfile", shell))
        suite.addTest(TestShell("test_rez_command", shell))
        suites.append(suite)

    all_ = unittest.TestSuite(suites)
    unittest.TextTestRunner(verbosity=verbosity).run(all_)
