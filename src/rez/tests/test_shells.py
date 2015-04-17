"""
Test noninteractive invocation of each type of shell (bash etc), and ensure that
their behaviour is correct wrt shell options such as --rcfile, -c, --stdin etc.
"""

from rez.system import system
from rez.shells import create_shell
from rez.resolved_context import ResolvedContext
from rez.rex import RexExecutor, literal, expandable
import rez.vendor.unittest2 as unittest
from rez.tests.util import TestBase, TempdirMixin, shell_dependent, \
    install_dependent
from rez.util import which
from rez.bind import hello_world
from rez.utils.platform_ import platform_
import subprocess
import tempfile
import inspect
import textwrap
import os
import sys


def _stdout(proc):
    out_, _ = proc.communicate()
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
            warn_untimestamped=False,
            resolve_caching=False)

    @classmethod
    def tearDownClass(cls):
        TempdirMixin.tearDownClass()

    @classmethod
    def _create_context(cls, pkgs):
        from rez.config import config
        return ResolvedContext(pkgs, caching=False)

    @shell_dependent(exclude=["cmd"])
    def test_no_output(self):
        # TODO: issues with binding the 'hello_world' package means it is not
        # possible to run this test on Windows.  The 'hello_world' executable
        # is not registered correctly on Windows so always returned the
        # incorrect error code.
        sh = create_shell()
        _, _, _, command = sh.startup_capabilities(command=True)
        if command:
            r = self._create_context(["hello_world"])
            p = r.execute_shell(command="hello_world -q",
                                stdout=subprocess.PIPE)

            self.assertEqual(
                _stdout(p), '',
                "This test and others will fail, because one or more of your "
                "startup scripts are printing to stdout. Please remove the "
                "printout and try again.")

    @shell_dependent(exclude=["cmd"])
    def test_command(self):
        # TODO: issues with binding the 'hello_world' package means it is not
        # possible to run this test on Windows.  The 'hello_world' executable
        # is not registered correctly on Windows so always returned the
        # incorrect error code.
        sh = create_shell()
        _, _, _, command = sh.startup_capabilities(command=True)

        if command:
            r = self._create_context(["hello_world"])
            p = r.execute_shell(command="hello_world",
                                stdout=subprocess.PIPE)
            self.assertEqual(_stdout(p), "Hello Rez World!")

    @shell_dependent(exclude=["cmd"])
    def test_command_returncode(self):
        # TODO: issues with binding the 'hello_world' package means it is not
        # possible to run this test on Windows.  The 'hello_world' executable
        # is not registered correctly on Windows so always returned the
        # incorrect error code.
        sh = create_shell()
        _, _, _, command = sh.startup_capabilities(command=True)

        if command:
            r = self._create_context(["hello_world"])
            command = "hello_world -q -r 66"
            commands = (command, command.split())
            for cmd in commands:
                p = r.execute_shell(command=cmd, stdout=subprocess.PIPE)
                p.wait()
                self.assertEqual(p.returncode, 66)

    @shell_dependent()
    def test_norc(self):
        sh = create_shell()
        _, norc, _, command = sh.startup_capabilities(norc=True, command=True)

        if norc and command:
            r = self._create_context(["hello_world"])
            p = r.execute_shell(norc=True,
                                command="hello_world",
                                stdout=subprocess.PIPE)
            self.assertEqual(_stdout(p), "Hello Rez World!")

    @shell_dependent()
    def test_stdin(self):
        sh = create_shell()
        _, _, stdin, _ = sh.startup_capabilities(stdin=True)

        if stdin:
            r = self._create_context(["hello_world"])
            p = r.execute_shell(stdout=subprocess.PIPE,
                                stdin=subprocess.PIPE,
                                norc=True)
            stdout, _ = p.communicate(input="hello_world\n")
            stdout = stdout.strip()
            self.assertEqual(stdout, "Hello Rez World!")

    @shell_dependent()
    def test_rcfile(self):
        sh = create_shell()
        rcfile, _, _, command = sh.startup_capabilities(rcfile=True, command=True)

        if rcfile and command:
            f, path = tempfile.mkstemp()
            os.write(f, "hello_world\n")
            os.close(f)

            r = self._create_context(["hello_world"])
            p = r.execute_shell(rcfile=path,
                                command="hello_world -q",
                                stdout=subprocess.PIPE)
            self.assertEqual(_stdout(p), "Hello Rez World!")
            os.remove(path)

    @shell_dependent(exclude=["cmd"])
    @install_dependent
    def test_rez_env_output(self):
        # TODO: this test does not run on Windows using the CMD shell as it
        # does not accept commands from stdin.  Rather than explicitly skipping
        # the test (via the decorator) perhaps we should check for startup
        # capabilities as the other tests do.
        from rez.vendor.sh import sh

        # here we are making sure that running a command via rez-env prints
        # exactly what we expect. We use 'sh' because subprocess strips special
        # characters such as color codes - we want to ensure that the output
        # EXACTLY matches the output of the command being run.
        echo_cmd = which("echo")
        if not echo_cmd:
            print "\nskipping test, 'echo' command not found."
            return

        cmd = sh.Command(os.path.join(system.rez_bin_path, "rez-env"))
        sh_out = cmd(["--", "echo", "hey"])
        out = str(sh_out).strip()
        self.assertEqual(out, "hey")

    @shell_dependent()
    @install_dependent
    def test_rez_command(self):
        sh = create_shell()
        _, _, _, command = sh.startup_capabilities(command=True)

        if command:
            r = self._create_context([])
            p = r.execute_shell(command="rezolve -h")
            p.wait()
            self.assertEqual(p.returncode, 0)

            p = r.execute_shell(command="rez-env -h")
            p.wait()
            self.assertEqual(p.returncode, 0)

    @shell_dependent()
    def test_rex_code(self):
        """Test that Rex code run in the shell creates the environment variable
        values that we expect."""
        def _execute_code(func, expected_output):
            loc = inspect.getsourcelines(func)[0][1:]
            code = textwrap.dedent('\n'.join(loc))
            r = self._create_context([])
            p = r.execute_rex_code(code, stdout=subprocess.PIPE)

            out, _ = p.communicate()
            self.assertEqual(p.returncode, 0)
            token = '\r\n' if platform_.name == 'windows' else '\n'
            output = out.strip().split(token)
            self.assertEqual(output, expected_output)

        def _rex_assigning():
            import os
            windows = os.name == "nt"

            def _print(value):
                env.FOO = value
                info("%FOO%" if windows else "${FOO}")

            env.GREET = "hi"
            env.WHO = "Gary"

            _print("ello")
            _print(literal("ello"))
            _print(expandable("ello"))
            _print("\\")
            _print("\\'")
            _print("\\\"")
            _print(literal("\\"))
            _print(literal("\\'"))
            _print(literal("\\\""))
            _print("\\path1\\path2\\path3")
            _print(literal("\\path1").e("\\path2\\path3"))
            _print("hello world")
            _print("hello 'world'")
            _print('hello "world"')
            _print(literal("hello world"))
            _print(literal("hello 'world'"))
            _print(literal('hello "world"'))
            _print("hey %WHO%" if windows else "hey $WHO")
            _print("hey %WHO%" if windows else "hey ${WHO}")
            _print(expandable("%GREET% " if windows else "${GREET} ").e("%WHO%" if windows else "$WHO"))
            _print(expandable("%GREET% " if windows else "${GREET} ").l("$WHO"))
            _print(literal("${WHO}"))
            _print(literal("${WHO}").e(" %WHO%" if windows else " $WHO"))

        expected_output = [
            "ello",
            "ello",
            "ello",
            "\\",
            "\\'",
            "\\\"",
            "\\",
            "\\'",
            "\\\"",
            "\\path1\\path2\\path3",
            "\\path1\\path2\\path3",
            "hello world",
            "hello 'world'",
            'hello "world"',
            "hello world",
            "hello 'world'",
            'hello "world"',
            "hey Gary",
            "hey Gary",
            "hi Gary",
            "hi $WHO",
            "${WHO}",
            "${WHO} Gary"
        ]

        _execute_code(_rex_assigning, expected_output)

        def _rex_appending():
            import os
            windows = os.name == "nt"

            env.FOO.append("hey")
            info("%FOO%" if windows else "${FOO}")
            env.FOO.append(literal("$DAVE"))
            info("%FOO%" if windows else "${FOO}")
            env.FOO.append("Dave's not here man")
            info("%FOO%" if windows else "${FOO}")

        expected_output = [
            "hey",
            os.pathsep.join(["hey", "$DAVE"]),
            os.pathsep.join(["hey", "$DAVE", "Dave's not here man"])
        ]

        _execute_code(_rex_appending, expected_output)


def get_test_suites():
    suites = []
    suite = unittest.TestSuite()
    suite.addTest(TestShells("test_no_output"))
    suite.addTest(TestShells("test_command"))
    suite.addTest(TestShells("test_command_returncode"))
    suite.addTest(TestShells("test_norc"))
    suite.addTest(TestShells("test_stdin"))
    suite.addTest(TestShells("test_rcfile"))
    suite.addTest(TestShells("test_rez_env_output"))
    suite.addTest(TestShells("test_rez_command"))
    suite.addTest(TestShells("test_rex_code"))
    suites.append(suite)
    return suites

if __name__ == '__main__':
    unittest.main()
