"""
Test noninteractive invocation of each type of shell (bash etc), and ensure that
their behaviour is correct wrt shell options such as --rcfile, -c, --stdin etc.
"""

from rez.shells import get_shell_types, create_shell
from rez.resolved_context import ResolvedContext
import rez.vendor.unittest2 as unittest
from rez.tests.util import ShellDependentTest
import subprocess
import tempfile
import os
import sys



def _stdout(proc):
    out_,_ = proc.communicate()
    return out_.strip()


class TestShell(ShellDependentTest):
    @classmethod
    def setUpClass(cls):
        cls.settings = dict(
            packages_path=[],
            implicit_packages=[],
            resolve_caching=False)

    def _create_context(self, pkgs):
        return ResolvedContext(pkgs,
                               caching=False)

    def test_no_output(self):
        sh = self.create_shell()
        _,_,command,_ = sh.startup_capabilities(command=True)
        if command:
            r = self._create_context(["hello_world"])
            p = r.execute_shell(command="hello_world -q",
                                stdout=subprocess.PIPE)

            self.assertEqual(_stdout(p), '', \
                "This test and others will fail, because one or more of your "
                "startup scripts are printing to stdout. Please remove the "
                "printout and try again.")

    def test_command(self):
        sh = self.create_shell()
        _,_,command,_ = sh.startup_capabilities(command=True)

        if command:
            r = self._create_context(["hello_world"])
            p = r.execute_shell(command="hello_world",
                                stdout=subprocess.PIPE)
            self.assertEqual(_stdout(p), "Hello Rez World!")

    def test_command_returncode(self):
        sh = self.create_shell()
        _,_,command,_ = sh.startup_capabilities(command=True)

        if command:
            r = self._create_context(["hello_world"])
            p = r.execute_shell(command="hello_world -q -r 66",
                                stdout=subprocess.PIPE)
            p.wait()
            self.assertEqual(p.returncode, 66)

    def test_norc(self):
        sh = self.create_shell()
        _,norc,command,_ = sh.startup_capabilities(norc=True, command=True)

        if norc and command:
            r = self._create_context(["hello_world"])
            p = r.execute_shell(norc=True,
                                command="hello_world",
                                stdout=subprocess.PIPE)
            self.assertEqual(_stdout(p), "Hello Rez World!")

    def test_stdin(self):
        sh = self.create_shell()
        _,_,_,stdin = sh.startup_capabilities(stdin=True)

        if stdin:
            r = self._create_context(["hello_world"])
            p = r.execute_shell(stdout=subprocess.PIPE,
                                stdin=subprocess.PIPE)
            stdout,_ = p.communicate(input="hello_world\n")
            stdout = stdout.strip()
            self.assertEqual(stdout, "Hello Rez World!")

    def test_rcfile(self):
        sh = self.create_shell()
        rcfile,_,command,_ = sh.startup_capabilities(rcfile=True, command=True)

        if rcfile and command:
            f,path = tempfile.mkstemp()
            os.write(f, "hello_world\n")
            os.close(f)

            r = self._create_context(["hello_world"])
            p = r.execute_shell(rcfile=path,
                                command="hello_world -q",
                                stdout=subprocess.PIPE)
            self.assertEqual(_stdout(p), "Hello Rez World!")
            os.remove(path)

    def test_rez_command(self):
        """Test that the Rez cli tools have been bound in the target env."""
        sh = self.create_shell()
        _,_,command,_ = sh.startup_capabilities(command=True)

        if command:
            r = self._create_context([])
            e = os.environ.copy()
            e["REZ_QUIET"] = "true"  # suppress warnings etc

            p = r.execute_shell(command="rez-env --paths= --ni -c 'hello_world' hello_world",
                                parent_environ=e,
                                stdout=subprocess.PIPE)
            self.assertEqual(_stdout(p), "Hello Rez World!")


def get_test_suites():
    suites = []
    suite = unittest.TestSuite()

    for shell in get_shell_types():
        suite.addTest(TestShell("test_create_shell", shell))
        suite.addTest(TestShell("test_no_output", shell))
        suite.addTest(TestShell("test_command", shell))
        suite.addTest(TestShell("test_command_returncode", shell))
        suite.addTest(TestShell("test_norc", shell))
        suite.addTest(TestShell("test_stdin", shell))
        suite.addTest(TestShell("test_rcfile", shell))
        suite.addTest(TestShell("test_rez_command", shell))

    suites.append(suite)
    return suites
