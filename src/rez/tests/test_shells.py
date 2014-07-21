"""
Test noninteractive invocation of each type of shell (bash etc), and ensure that
their behaviour is correct wrt shell options such as --rcfile, -c, --stdin etc.
"""

from rez.shells import create_shell
from rez.resolved_context import ResolvedContext
import rez.vendor.unittest2 as unittest
from rez.tests.util import TestBase, TempdirMixin, shell_dependent, \
    install_dependent
from rez.bind import hello_world
import subprocess
import tempfile
import os
import sys



def _stdout(proc):
    out_,_ = proc.communicate()
    return out_.strip()


class TestShells(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls):
        TempdirMixin.setUpClass()

        packages_path = os.path.join(cls.root, "packages")
        os.makedirs(packages_path)
        hello_world.bind(packages_path)

        cls.settings = dict(
            packages_path=[packages_path],
            implicit_packages=[],
            add_bootstrap_path=False,
            warn_untimestamped=False,
            resolve_caching=False)

    @classmethod
    def tearDownClass(cls):
        TempdirMixin.tearDownClass()

    def _create_context(self, pkgs):
        return ResolvedContext(pkgs,
                               caching=False)

    @shell_dependent
    def test_no_output(self):
        sh = create_shell()
        _,_,_,command = sh.startup_capabilities(command=True)
        if command:
            r = self._create_context(["hello_world"])
            p = r.execute_shell(command="hello_world -q",
                                stdout=subprocess.PIPE)

            self.assertEqual(_stdout(p), '', \
                "This test and others will fail, because one or more of your "
                "startup scripts are printing to stdout. Please remove the "
                "printout and try again.")

    @shell_dependent
    def test_command(self):
        sh = create_shell()
        _,_,_,command = sh.startup_capabilities(command=True)

        if command:
            r = self._create_context(["hello_world"])
            p = r.execute_shell(command="hello_world",
                                stdout=subprocess.PIPE)
            self.assertEqual(_stdout(p), "Hello Rez World!")

    @shell_dependent
    def test_command_returncode(self):
        sh = create_shell()
        _,_,_,command = sh.startup_capabilities(command=True)

        if command:
            r = self._create_context(["hello_world"])
            p = r.execute_shell(command="hello_world -q -r 66",
                                stdout=subprocess.PIPE)
            p.wait()
            self.assertEqual(p.returncode, 66)

    @shell_dependent
    def test_norc(self):
        sh = create_shell()
        _,norc,_,command = sh.startup_capabilities(norc=True, command=True)

        if norc and command:
            r = self._create_context(["hello_world"])
            p = r.execute_shell(norc=True,
                                command="hello_world",
                                stdout=subprocess.PIPE)
            self.assertEqual(_stdout(p), "Hello Rez World!")

    @shell_dependent
    def test_stdin(self):
        sh = create_shell()
        _,_,stdin,_ = sh.startup_capabilities(stdin=True)

        if stdin:
            r = self._create_context(["hello_world"])
            p = r.execute_shell(stdout=subprocess.PIPE,
                                stdin=subprocess.PIPE)
            stdout,_ = p.communicate(input="hello_world\n")
            stdout = stdout.strip()
            self.assertEqual(stdout, "Hello Rez World!")

    @shell_dependent
    def test_rcfile(self):
        sh = create_shell()
        rcfile,_,_,command = sh.startup_capabilities(rcfile=True, command=True)

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

    @shell_dependent
    @install_dependent
    def test_rez_command(self):
        sh = create_shell()
        _,_,_,command = sh.startup_capabilities(command=True)

        if command:
            r = self._create_context([])
            p = r.execute_shell(command="rezolve -h")
            p.wait()
            self.assertEqual(p.returncode, 0)

            p = r.execute_shell(command="rez-env -h")
            p.wait()
            self.assertEqual(p.returncode, 0)


def get_test_suites():
    suites = []
    suite = unittest.TestSuite()
    suite.addTest(TestShells("test_no_output"))
    suite.addTest(TestShells("test_command"))
    suite.addTest(TestShells("test_command_returncode"))
    suite.addTest(TestShells("test_norc"))
    suite.addTest(TestShells("test_stdin"))
    suite.addTest(TestShells("test_rcfile"))
    suite.addTest(TestShells("test_rez_command"))
    suites.append(suite)
    return suites

if __name__ == '__main__':
    unittest.main()
