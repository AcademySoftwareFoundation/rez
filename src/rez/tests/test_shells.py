# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
test shell invocation
"""
from rez.system import system
from rez.shells import create_shell, get_shell_types, get_shell_class
from rez.resolved_context import ResolvedContext
from rez.rex import literal, expandable
from rez.plugin_managers import plugin_manager
from rez.utils.execution import ExecutableScriptMode, _get_python_script_files
from rez.utils.platform_ import platform_
from rez.tests.util import TestBase, TempdirMixin, get_available_shells, \
    per_available_shell, install_dependent
from rez.bind import hello_world
from rez.config import config
import unittest
import subprocess
import tempfile
import inspect
import textwrap
import os


def _stdout(proc):
    out_, _ = proc.communicate()
    if proc.returncode:
        raise RuntimeError(
            "The subprocess failed with exitcode %d" % proc.returncode
        )
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

    def test_aaa_shell_presence(self):
        """Ensure specific shell types are present as loaded plugins.

        The env var _REZ_ENSURE_TEST_SHELLS should be set by a CI system (such
        as github actions) to make sure the shells we expect to be installed,
        are installed, and are getting tested.

        Note 'aaa' forces unittest to run this test first.
        """
        shells = os.getenv("_REZ_ENSURE_TEST_SHELLS", "").split(',')
        shells = set(x for x in shells if x)

        if not shells:
            self.skipTest(
                "Not ensuring presence of shells from explicit list because "
                "$_REZ_ENSURE_TEST_SHELLS is either empty or not defined"
            )
            return

        # check for missing shells
        missing_shells = shells - set(get_shell_types())
        if missing_shells:
            raise RuntimeError(
                "The following shells should be available for testing but are "
                "not present: %r" % list(missing_shells)
            )

        # check for unavailable shells
        for shell in shells:
            if not get_shell_class(shell).is_available():
                raise RuntimeError(
                    "The shell %r is not available (executable not found)"
                    % shell
                )

        # check for shell plugins that failed to load
        for (name, reason) in plugin_manager.get_failed_plugins("shell"):
            if name in shells:
                raise RuntimeError(
                    "The shell plugin %r failed to load: %s"
                    % (name, reason)
                )

    @per_available_shell()
    def test_no_output(self, shell):
        sh = create_shell(shell)
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
    def test_command(self, shell):
        sh = create_shell(shell)
        _, _, _, command = sh.startup_capabilities(command=True)

        if command:
            r = self._create_context(["hello_world"])
            p = r.execute_shell(command="hello_world",
                                stdout=subprocess.PIPE, text=True)
            self.assertEqual(_stdout(p), "Hello Rez World!")

    @per_available_shell()
    def test_per_available_shell_decorator(self, shell):
        """
        Test that the "per_available_shell" decorator correctly sets the default shell
        and that ResolvedContext.execute_shell will use the default shell as expected.
        """
        # Based on:
        # * https://stackoverflow.com/a/3327022
        # * https://stackoverflow.com/a/61469226
        # * https://stackoverflow.com/a/27776822
        data = {
            "bash": {
                "command": "echo $BASH",
                "assert": lambda x: self.assertEqual(os.path.basename(x), "bash"),
            },
            "gitbash": {
                "command": "uname -s",
                "assert": lambda x: self.assertRegex(x, r"^(MINGW|CYGWIN|MSYS).*$")
            },
            "csh": {
                "command": "echo $shell",
                # csh should usually resolve to csh, but on macOS, it will resolve to tcsh,
                # at least on GitHub Actions Hosted runners.
                "assert": lambda x: self.assertEqual(
                    os.path.basename(x), "csh" if system.platform != "osx" else "tcsh"
                ),
            },
            "tcsh": {
                "command": "echo $shell",
                "assert": lambda x: self.assertEqual(os.path.basename(x), "tcsh"),
            },
            "sh": {
                # This is a hack. $0 doesn't work when run through execute_shell,
                # but will work when running "rez-env --shell sh -c 'echo $0'"
                # Output result to /dev/null because we don't want the content to affect the test,
                # we just want to test is the variable exists.
                "command": "set -o nounset; echo $REZ_STORED_PROMPT_SH > /dev/null",
                "assert": lambda x: self.assertEqual(x, ""),
            },
            "zsh": {
                "command": "echo $ZSH_NAME",
                "assert": lambda x: self.assertEqual(os.path.basename(x), "zsh"),
            },
            "powershell": {
                "command": "echo $PSVersionTable.PSEdition",
                "assert": lambda x: self.assertEqual(x, "Desktop"),
            },
            "pwsh": {
                "command": "echo $PSVersionTable.PSEdition",
                "assert": lambda x: self.assertEqual(x, "Core"),
            },
            "cmd": {
                "command": "dir 2>&1 *`|echo CMD",
                "assert": lambda x: self.assertEqual(x, "CMD"),
            },
        }

        if shell not in data:
            self.fail("Please add support for {0!r} in the test".format(shell))

        r = self._create_context([])
        p = r.execute_shell(command=data[shell]["command"],
                            stdout=subprocess.PIPE, text=True)
        data[shell]["assert"](_stdout(p).strip())

    @per_available_shell()
    def test_command_returncode(self, shell):
        sh = create_shell(shell)
        _, _, _, command = sh.startup_capabilities(command=True)

        if command:
            r = self._create_context(["hello_world"])
            command = "hello_world -q -r 66"
            commands = (command, command.split())
            for cmd in commands:
                with r.execute_shell(command=cmd, stdout=subprocess.PIPE) as p:
                    p.wait()
                self.assertEqual(p.returncode, 66)

    @unittest.skipIf(platform_.name != "windows", "GUI entrypoint test is only relevant on Windows")
    @unittest.skipIf("pwsh" not in get_available_shells(), "PowerShell unavailable or disabled")
    def test_pwsh_lastexitcode_gui(self):
        """This validates some semi-unintuitive behavior on Windows, where GUI applications
        will "return" immediately without any exit status when launched from a shell.
        """
        sh = create_shell("pwsh")
        _, _, _, command = sh.startup_capabilities(command=True)

        if command:
            def actions_callback(ex):
                """Action callback to enable PowerShell's "strict" mode."""
                ex.command("Set-StrictMode -version Latest")

            r = self._create_context(["hello_world"])
            command = "hello_world -q -r 66"
            commands = (command, command.split())
            for cmd in commands:
                with r.execute_shell(shell="pwsh", command=cmd, actions_callback=actions_callback,
                                     stdout=subprocess.PIPE) as p:
                    p.wait()
                self.assertEqual(p.returncode, 66)

            command = "hello_world_gui -q -r 49"
            commands = (command, command.split())
            for cmd in commands:
                with r.execute_shell(shell="pwsh", command=cmd, actions_callback=actions_callback,
                                     stdout=subprocess.PIPE) as p:
                    p.wait()
                # The GUI application should return control to the shell immediately, and that
                # should bubble up through the rez shell as a 0 exit status.
                self.assertEqual(p.returncode, 0)

    @per_available_shell()
    def test_norc(self, shell):
        sh = create_shell(shell)
        _, norc, _, command = sh.startup_capabilities(norc=True, command=True)

        if norc and command:
            r = self._create_context(["hello_world"])
            p = r.execute_shell(norc=True,
                                command="hello_world",
                                stdout=subprocess.PIPE, text=True)
            self.assertEqual(_stdout(p), "Hello Rez World!")

    @per_available_shell()
    def test_stdin(self, shell):
        sh = create_shell(shell)
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
    def test_rcfile(self, shell):
        sh = create_shell(shell)
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

    # TODO fix cmd shell command string escape
    # as per https://github.com/AcademySoftwareFoundation/rez/pull/1130, then remove this
    # exclusion
    #
    @per_available_shell(exclude=["cmd"])
    @install_dependent()
    def test_rez_env_output(self, shell):

        def _test(txt):
            # Assumes that the shell has an echo command, built-in or alias
            binpath = os.path.join(system.rez_bin_path, "rez-env")
            args = [binpath, "--shell", shell, "--", "echo", txt]

            process = subprocess.Popen(
                args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, universal_newlines=True
            )
            sh_out = process.communicate()

            # because powershell may not exit with !0 on error, depending on
            # how it's been configured
            #
            if sh_out[1]:
                raise RuntimeError("Command %r failed:\n%s" % (txt, sh_out[1]))

            self.assertEqual(sh_out[0].strip(), txt)

        # please note - it's no coincidence that there are no substrings like
        # '$you' here. These would expand to the equivalent env-var (as
        # intended), which would be an empty string. We're not testing that
        # here though.
        #

        _test("hey")  # simple case
        _test("hey you")  # with a space
        _test("<hey>")  # special characters
        _test("!hey>$")  # more special characters
        _test("'hey'")  # single quotes
        _test('"hey"')  # double quotes
        _test("hey `")  # backtick
        _test("hey $ ?yeah> 'you'..^!")  # throw lots of stuff at it

    @per_available_shell()
    @install_dependent()
    def test_rez_command(self, shell):
        sh = create_shell(shell)
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
    def test_rex_code(self, shell):
        """Test that Rex code run in the shell creates the environment variable
        values that we expect.
        """
        config.override("default_shell", shell)

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

            env.FOO.unset()
            env.FOO.append("hey")
            info(sh.get_key_token("FOO"))
            env.FOO.append(literal("$DAVE"))
            info(sh.get_key_token("FOO"))
            env.FOO.append("Dave's not here man")
            info(sh.get_key_token("FOO"))

        expected_output = [
            "hey",
            sh.pathsep.join(["hey", "$DAVE"]),
            sh.pathsep.join(["hey", "$DAVE", "Dave's not here man"])
        ]

        _execute_code(_rex_appending, expected_output)

        def _rex_prepending():
            from rez.shells import create_shell
            sh = create_shell()

            env.FOO.unset()
            env.FOO.prepend("hey")
            info(sh.get_key_token("FOO"))
            env.FOO.prepend(literal("$DAVE"))
            info(sh.get_key_token("FOO"))
            env.FOO.prepend("Dave's not here man")
            info(sh.get_key_token("FOO"))

        expected_output = [
            "hey",
            sh.pathsep.join(["$DAVE", "hey"]),
            sh.pathsep.join(["Dave's not here man", "$DAVE", "hey"])
        ]

        _execute_code(_rex_prepending, expected_output)

    @per_available_shell()
    def test_rex_code_alias(self, shell):
        """Ensure PATH changes do not influence the alias command.

        This is important for Windows because the doskey.exe might not be on
        the PATH anymore at the time it's executed. That's why we figure out
        the absolute path to doskey.exe before we modify PATH and continue to
        use the absolute path after the modifications.
        """
        config.override("default_shell", shell)

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
    def test_alias_command(self, shell):
        """Testing alias can be passed in as command

        This is important for Windows CMD shell because the doskey.exe isn't
        executed yet when the alias is being passed.
        """
        config.override("default_shell", shell)

        def _make_alias(ex):
            ex.alias('hi', 'echo "hi"')

        r = self._create_context([])
        p = r.execute_shell(command='hi',
                            actions_callback=_make_alias,
                            stdout=subprocess.PIPE)

        out, _ = p.communicate()
        self.assertEqual(0, p.returncode)

    @per_available_shell()
    def test_alias_command_with_args(self, shell):
        """Testing alias can be passed in as command with args

        This is important for Windows CMD shell because the doskey.exe isn't
        executed yet when the alias is being passed.
        """
        config.override("default_shell", shell)

        def _make_alias(ex):
            ex.alias('tell', 'echo')

        r = self._create_context([])
        p = r.execute_shell(command='tell "hello"',
                            actions_callback=_make_alias,
                            stdout=subprocess.PIPE)

        out, _ = p.communicate()
        self.assertEqual(0, p.returncode)

    @per_available_shell()
    def test_alias_return_code(self, shell):
        """Ensure return codes are correct while using aliases."""
        config.override("default_shell", shell)

        def _make_alias(ex):
            ex.alias('my_alias', 'hello_world -r 1')

        r = self._create_context(["hello_world"])
        p = r.execute_shell(command='my_alias',
                            actions_callback=_make_alias,
                            stdout=subprocess.PIPE)

        out, _ = p.communicate()
        self.assertEqual(1, p.returncode)

    @per_available_shell()
    def test_find_executable_config_override(self, shell):
        """Test the shell plugin returns correct exec override from settings."""
        config.override("default_shell", shell)
        override_attr = "plugins.shell.{}.executable_fullpath".format(shell)
        cls = type(create_shell(shell))
        with tempfile.TemporaryDirectory() as td:
            exe_path = os.path.join(td, cls.executable_name())
            with open(exe_path, 'w'):
                config.override(override_attr, exe_path)
                assert cls.find_executable(cls.executable_name()) == exe_path


if __name__ == '__main__':
    unittest.main()
