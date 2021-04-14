"""
test shell invocation
"""
from __future__ import print_function

from rez.system import system
from rez.shells import create_shell
from rez.resolved_context import ResolvedContext
from rez.rex import literal, expandable
from rez.utils.execution import ExecutableScriptMode, _get_python_script_files
from rez.tests.util import TestBase, TempdirMixin, per_available_shell, \
    install_dependent
from rez.bind import hello_world
import unittest
import subprocess
import tempfile
import inspect
import textwrap
import os


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
            package_filter=None,
            implicit_packages=[],
            warn_untimestamped=False)

    @classmethod
    def tearDownClass(cls):
        TempdirMixin.tearDownClass()

    @classmethod
    def _create_context(cls, pkgs):
        return ResolvedContext(pkgs, caching=False)

    @per_available_shell()
    def test_no_output(self):
        sh = create_shell()
        _, _, _, command = sh.startup_capabilities(command=True)
        if command:
            r = self._create_context(["hello_world"])
            p = r.execute_shell(command="hello_world -q",
                                stdout=subprocess.PIPE, text=True)

            self.assertEqual(
                _stdout(p), '',
                "This test and others will fail, because one or more of your "
                "startup scripts are printing to stdout. Please remove the "
                "printout and try again.")

    def test_create_executable_script(self):
        script_file = os.path.join(self.root, "script")
        py_script_file = os.path.join(self.root, "script.py")

        for platform in ['windows', 'linux']:

            files = _get_python_script_files(script_file,
                                             ExecutableScriptMode.py,
                                             platform)
            self.assertListEqual(files, [py_script_file])

            files = _get_python_script_files(py_script_file,
                                             ExecutableScriptMode.py,
                                             platform)
            self.assertListEqual(files, [py_script_file])

            files = _get_python_script_files(script_file,
                                             ExecutableScriptMode.single,
                                             platform)
            self.assertListEqual(files, [script_file])

            files = _get_python_script_files(py_script_file,
                                             ExecutableScriptMode.single,
                                             platform)
            self.assertListEqual(files, [py_script_file])

            files = _get_python_script_files(script_file,
                                             ExecutableScriptMode.both,
                                             platform)
            self.assertListEqual(files, [script_file, py_script_file])

            files = _get_python_script_files(py_script_file,
                                             ExecutableScriptMode.both,
                                             platform)
            self.assertListEqual(files, [py_script_file])

            files = _get_python_script_files(script_file,
                                             ExecutableScriptMode.platform_specific,
                                             platform)
            if platform == "windows":
                self.assertListEqual(files, [py_script_file])
            else:
                self.assertListEqual(files, [script_file])

            files = _get_python_script_files(py_script_file,
                                             ExecutableScriptMode.platform_specific,
                                             platform)
            self.assertListEqual(files, [py_script_file])

    @per_available_shell()
    def test_command(self):
        sh = create_shell()
        _, _, _, command = sh.startup_capabilities(command=True)

        if command:
            r = self._create_context(["hello_world"])
            p = r.execute_shell(command="hello_world",
                                stdout=subprocess.PIPE, text=True)
            self.assertEqual(_stdout(p), "Hello Rez World!")

    @per_available_shell()
    def test_command_returncode(self):
        sh = create_shell()
        _, _, _, command = sh.startup_capabilities(command=True)

        if command:
            r = self._create_context(["hello_world"])
            command = "hello_world -q -r 66"
            commands = (command, command.split())
            for cmd in commands:
                with r.execute_shell(command=cmd, stdout=subprocess.PIPE) as p:
                    p.wait()
                self.assertEqual(p.returncode, 66)

    @per_available_shell()
    def test_norc(self):
        sh = create_shell()
        _, norc, _, command = sh.startup_capabilities(norc=True, command=True)

        if norc and command:
            r = self._create_context(["hello_world"])
            p = r.execute_shell(norc=True,
                                command="hello_world",
                                stdout=subprocess.PIPE, text=True)
            self.assertEqual(_stdout(p), "Hello Rez World!")

    @per_available_shell()
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

    @per_available_shell()
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
                                stdout=subprocess.PIPE,
                                text=True)
            self.assertEqual(_stdout(p), "Hello Rez World!")
            os.remove(path)

    @per_available_shell()
    @install_dependent()
    def test_rez_env_output(self):
        # here we are making sure that running a command via rez-env prints
        # exactly what we expect.

        # Assumes that the shell has an echo command, build-in or alias
        cmd = [os.path.join(system.rez_bin_path, "rez-env"), "--", "echo", "hey"]
        process = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, universal_newlines=True
        )
        sh_out = process.communicate()
        self.assertEqual(sh_out[0].strip(), "hey")

    @per_available_shell()
    @install_dependent()
    def test_rez_command(self):
        sh = create_shell()
        _, _, _, command = sh.startup_capabilities(command=True)

        if command:
            r = self._create_context([])
            with r.execute_shell(command="rezolve -h") as p:
                p.wait()
            self.assertEqual(p.returncode, 0)

            with r.execute_shell(command="rez-env -h") as p:
                p.wait()
            self.assertEqual(p.returncode, 0)

    @per_available_shell()
    def test_rex_code(self):
        """Test that Rex code run in the shell creates the environment variable
        values that we expect."""
        def _execute_code(func, expected_output):
            loc = inspect.getsourcelines(func)[0][1:]
            code = textwrap.dedent('\n'.join(loc))
            r = self._create_context([])
            p = r.execute_rex_code(code, stdout=subprocess.PIPE, text=True)

            out, _ = p.communicate()
            self.assertEqual(p.returncode, 0)

            output = out.strip().split("\n")
            self.assertEqual(output, expected_output)

        def _rex_assigning():
            from rez.shells import create_shell
            sh = create_shell()

            def _print(value):
                env.FOO = value
                # Wrap the output in quotes to prevent the shell from
                # interpreting parts of our output as commands. This can happen
                # when we include special characters (&, <, >, ^) in a
                # variable.
                info('"${FOO}"')

            env.GREET = "hi"
            env.WHO = "Gary"

            _print("ello")
            _print(literal("ello"))
            _print(expandable("ello"))
            info('')
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

            # Generic form of variables
            _print("hey $WHO")
            _print("hey ${WHO}")
            _print(expandable("${GREET} ").e("$WHO"))
            _print(expandable("${GREET} ").l("$WHO"))
            _print(literal("${WHO}"))
            _print(literal("${WHO}").e(" $WHO"))

            # Make sure we are escaping &, <, >, ^ properly.
            _print('hey & world')
            _print('hey > world')
            _print('hey < world')
            _print('hey ^ world')

            # Platform dependent form of variables.
            for token in sh.get_all_key_tokens("WHO"):
                _print("hey " + token)
                _print(expandable("${GREET} ").e(token))
                _print(expandable("${GREET} ").l(token))
                _print(literal(token))
                _print(literal(token).e(" " + token))

        expected_output = [
            "ello",
            "ello",
            "ello",
            "",
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
            "${WHO} Gary",
            "hey & world",
            "hey > world",
            "hey < world",
            "hey ^ world"
        ]

        # Assertions for other environment variable types
        from rez.shells import create_shell
        sh = create_shell()
        for token in sh.get_all_key_tokens("WHO"):
            expected_output += [
                "hey Gary",
                "hi Gary",
                "hi " + token,
                token,
                token + " Gary",
            ]

        # We are wrapping all variable outputs in quotes in order to make sure
        # our shell isn't interpreting our output as instructions when echoing
        # it but this means we need to wrap our expected output as well. Only
        # exception is empty string, which is just passed through.
        expected_output = ['"{}"'.format(o) if o else o for o in expected_output]

        _execute_code(_rex_assigning, expected_output)

        def _rex_appending():
            from rez.shells import create_shell
            sh = create_shell()

            env.FOO.append("hey")
            info(sh.get_key_token("FOO"))
            env.FOO.append(literal("$DAVE"))
            info(sh.get_key_token("FOO"))
            env.FOO.append("Dave's not here man")
            info(sh.get_key_token("FOO"))

        expected_output = [
            "hey",
            os.pathsep.join(["hey", "$DAVE"]),
            os.pathsep.join(["hey", "$DAVE", "Dave's not here man"])
        ]

        _execute_code(_rex_appending, expected_output)

    @per_available_shell()
    def test_rex_code_alias(self):
        """Ensure PATH changes do not influence the alias command.

        This is important for Windows because the doskey.exe might not be on
        the PATH anymore at the time it's executed. That's why we figure out
        the absolute path to doskey.exe before we modify PATH and continue to
        use the absolute path after the modifications.

        """
        def _execute_code(func):
            loc = inspect.getsourcelines(func)[0][1:]
            code = textwrap.dedent('\n'.join(loc))
            r = self._create_context([])
            p = r.execute_rex_code(code, stdout=subprocess.PIPE)

            out, _ = p.communicate()
            self.assertEqual(p.returncode, 0)

        def _alias_after_path_manipulation():
            # Appending something to the PATH and creating an alias afterwards
            # did fail before we implemented a doskey specific fix.
            env.PATH.append("hey")
            alias("alias_test", "echo test_echo")

        # We don't expect any output, the shell should just return with exit
        # code 0.
        _execute_code(_alias_after_path_manipulation)

    @per_available_shell()
    def test_alias_command(self):
        """Testing alias can be passed in as command

        This is important for Windows CMD shell because the doskey.exe isn't
        executed yet when the alias is being passed.

        """
        def _make_alias(ex):
            ex.alias('hi', 'echo "hi"')

        r = self._create_context([])
        p = r.execute_shell(command='hi',
                            actions_callback=_make_alias,
                            stdout=subprocess.PIPE)

        out, _ = p.communicate()
        self.assertEqual(0, p.returncode)

    @per_available_shell()
    def test_alias_command_with_args(self):
        """Testing alias can be passed in as command with args

        This is important for Windows CMD shell because the doskey.exe isn't
        executed yet when the alias is being passed.
        """
        def _make_alias(ex):
            ex.alias('tell', 'echo')

        r = self._create_context([])
        p = r.execute_shell(command='tell "hello"',
                            actions_callback=_make_alias,
                            stdout=subprocess.PIPE)

        out, _ = p.communicate()
        self.assertEqual(0, p.returncode)


if __name__ == '__main__':
    unittest.main()


# Copyright 2013-2016 Allan Johns.
#
# This library is free software: you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.
