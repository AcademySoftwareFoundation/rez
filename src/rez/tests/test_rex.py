"""
test the rex command generator API
"""
from rez.rex import RexExecutor, Python, Setenv, Appendenv, Prependenv, Info, \
    Comment, Alias, Command, Source, Error, Shebang, Unsetenv, expandable, \
    literal
from rez.rex_bindings import VersionBinding
from rez.exceptions import RexError, RexUndefinedVariableError
from rez.config import config
import unittest
from rez.vendor.version.version import Version
from rez.tests.util import TestBase
from rez.utils.backcompat import convert_old_commands
import inspect
import textwrap
import os


class TestRex(TestBase):

    def _create_executor(self, env, **kwargs):
        interp = Python(target_environ={}, passive=True)
        return RexExecutor(interpreter=interp,
                           parent_environ=env,
                           shebang=False,
                           **kwargs)

    def _test(self, func, env, expected_actions=None, expected_output=None,
              expected_exception=None, **ex_kwargs):
        """Tests rex code as a function object, and code string."""
        loc = inspect.getsourcelines(func)[0][1:]
        code = textwrap.dedent('\n'.join(loc))

        if expected_exception:
            ex = self._create_executor(env, **ex_kwargs)
            self.assertRaises(expected_exception, ex.execute_function, func)

            ex = self._create_executor(env, **ex_kwargs)
            self.assertRaises(expected_exception, ex.execute_code, code)
        else:
            ex = self._create_executor(env, **ex_kwargs)
            ex.execute_function(func)
            self.assertEqual(ex.actions, expected_actions)
            self.assertEqual(ex.get_output(), expected_output)

            ex = self._create_executor(env, **ex_kwargs)
            ex.execute_code(code)
            self.assertEqual(ex.actions, expected_actions)
            self.assertEqual(ex.get_output(), expected_output)

    def test_1(self):
        """Test simple use of every available action."""
        def _rex():
            shebang()
            setenv("FOO", "foo")
            setenv("BAH", "bah")
            getenv("BAH")
            unsetenv("BAH")
            unsetenv("NOTEXIST")
            prependenv("A", "/tmp")
            prependenv("A", "/data")
            appendenv("B", "/tmp")
            appendenv("B", "/data")
            defined("BAH")
            undefined("BAH")
            defined("NOTEXIST")
            undefined("NOTEXIST")
            alias("thing", "thang")
            info("that's interesting")
            error("oh noes")
            command("runme --with --args")
            source("./script.src")

        self._test(func=_rex,
                   env={},
                   expected_actions = [
                       Shebang(),
                       Setenv('FOO', 'foo'),
                       Setenv('BAH', 'bah'),
                       Unsetenv('BAH'),
                       Unsetenv('NOTEXIST'),
                       Setenv('A', '/tmp'),
                       Prependenv('A', '/data'),
                       Setenv('B', '/tmp'),
                       Appendenv('B', '/data'),
                       Alias('thing', 'thang'),
                       Info("that's interesting"),
                       Error('oh noes'),
                       Command('runme --with --args'),
                       Source('./script.src')],
                   expected_output = {
                       'FOO': 'foo',
                       'A': os.pathsep.join(["/data","/tmp"]),
                       'B': os.pathsep.join(["/tmp","/data"])})

    def test_2(self):
        """Test simple setenvs and assignments."""
        def _rex():
            env.FOO = "foo"
            setenv("BAH", "bah")
            env.EEK = env.FOO

        self._test(func=_rex,
                   env={},
                   expected_actions = [
                       Setenv('FOO', 'foo'),
                       Setenv('BAH', 'bah'),
                       Setenv('EEK', 'foo')],
                   expected_output = {
                       'FOO': 'foo',
                       'EEK': 'foo',
                       'BAH': 'bah'})

    def test_3(self):
        """Test appending/prepending."""
        def _rex():
            appendenv("FOO", "test1")
            env.FOO.append("test2")
            env.FOO.append("test3")

            env.BAH.prepend("A")
            prependenv("BAH", "B")
            env.BAH.append("C")

        # no parent variables enabled
        self._test(func=_rex,
                   env={},
                   expected_actions = [
                       Setenv('FOO', 'test1'),
                       Appendenv('FOO', 'test2'),
                       Appendenv('FOO', 'test3'),
                       Setenv('BAH', 'A'),
                       Prependenv('BAH', 'B'),
                       Appendenv('BAH', 'C')],
                   expected_output = {
                       'FOO': os.pathsep.join(["test1","test2","test3"]),
                       'BAH': os.pathsep.join(["B","A","C"])})

        # FOO and BAH enabled as parent variables, but not present
        expected_actions = [Appendenv('FOO', 'test1'),
                            Appendenv('FOO', 'test2'),
                            Appendenv('FOO', 'test3'),
                            Prependenv('BAH', 'A'),
                            Prependenv('BAH', 'B'),
                            Appendenv('BAH', 'C')]

        self._test(func=_rex,
                   env={},
                   expected_actions=expected_actions,
                   expected_output = {
                       'FOO': os.pathsep.join(["", "test1","test2","test3"]),
                       'BAH': os.pathsep.join(["B","A", "","C"])},
                   parent_variables=["FOO","BAH"])

        # FOO and BAH enabled as parent variables, and present
        self._test(func=_rex,
                   env={"FOO": "tmp",
                        "BAH": "Z"},
                   expected_actions=expected_actions,
                   expected_output = {
                       'FOO': os.pathsep.join(["tmp", "test1","test2","test3"]),
                       'BAH': os.pathsep.join(["B","A", "Z","C"])},
                   parent_variables=["FOO","BAH"])

    def test_4(self):
        """Test control flow using internally-set env vars."""
        def _rex():
            env.FOO = "foo"
            setenv("BAH", "bah")
            env.EEK = "foo"

            if env.FOO == "foo":
                env.FOO_VALID = 1
                info("FOO validated")

            if env.FOO == env.EEK:
                comment("comparison ok")

        self._test(func=_rex,
                   env={},
                   expected_actions = [
                       Setenv('FOO', 'foo'),
                       Setenv('BAH', 'bah'),
                       Setenv('EEK', 'foo'),
                       Setenv('FOO_VALID', '1'),
                       Info('FOO validated'),
                       Comment('comparison ok')],
                   expected_output = {
                       'FOO': 'foo',
                       'BAH': 'bah',
                       'EEK': 'foo',
                       'FOO_VALID': '1'})

    def test_5(self):
        """Test control flow using externally-set env vars."""
        def _rex():
            if defined("EXT") and env.EXT == "alpha":
                env.EXT_FOUND = 1
                env.EXT.append("beta")  # will still overwrite
            else:
                env.EXT_FOUND = 0
                if undefined("EXT"):
                    info("undefined working as expected")

        # with EXT undefined
        self._test(func=_rex,
                   env={},
                   expected_actions = [
                       Setenv('EXT_FOUND', '0'),
                       Info("undefined working as expected")],
                   expected_output = {'EXT_FOUND': '0'})

        # with EXT defined
        self._test(func=_rex,
                   env={"EXT": "alpha"},
                   expected_actions = [
                       Setenv('EXT_FOUND', '1'),
                       Setenv('EXT', 'beta')],
                   expected_output = {
                       'EXT_FOUND': '1',
                       'EXT': 'beta'})

    def test_6(self):
        """Test variable expansion."""
        def _rex():
            env.FOO = "foo"
            env.DOG = "$FOO"  # this will convert to '${FOO}'
            env.BAH = "${FOO}"
            env.EEK = "${BAH}"
            if env.BAH == "foo" and getenv("EEK") == "foo":
                info("expansions visible in control flow")

            if defined("EXT") and getenv("EXT") == "alpha":
                env.FEE = "${EXT}"

        # with EXT undefined
        self._test(func=_rex,
                   env={},
                   expected_actions = [
                       Setenv('FOO', 'foo'),
                       Setenv('DOG', '${FOO}'),
                       Setenv('BAH', '${FOO}'),
                       Setenv('EEK', '${BAH}'),
                       Info('expansions visible in control flow')],
                   expected_output = {
                       'FOO': 'foo',
                       'DOG': 'foo',
                       'BAH': 'foo',
                       'EEK': 'foo'})

        # with EXT defined
        self._test(func=_rex,
                   env={"EXT": "alpha"},
                   expected_actions = [
                       Setenv('FOO', 'foo'),
                       Setenv('DOG', '${FOO}'),
                       Setenv('BAH', '${FOO}'),
                       Setenv('EEK', '${BAH}'),
                       Info('expansions visible in control flow'),
                       Setenv('FEE', '${EXT}')],
                   expected_output = {
                       'FOO': 'foo',
                       'DOG': 'foo',
                       'FEE': 'foo',
                       'BAH': 'foo',
                       'EEK': 'foo',
                       'FEE': 'alpha'})

    def test_7(self):
        """Test exceptions."""
        def _rex1():
            # reference to undefined var
            getenv("NOTEXIST")

        self._test(func=_rex1,
                   env={},
                   expected_exception=RexUndefinedVariableError)

        def _rex2():
            # reference to undefined var
            info(env.NOTEXIST)

        self._test(func=_rex2,
                   env={},
                   expected_exception=RexUndefinedVariableError)

        def _rex3():
            # native error, this gets encapsulated in a RexError
            raise Exception("some non rex-specific error")

        self._test(func=_rex3,
                   env={},
                   expected_exception=RexError)

    def test_8(self):
        """Custom environment variable separators."""

        config.override("env_var_separators", {"FOO":",", "BAH":" "})

        def _rex():
            appendenv("FOO", "test1")
            env.FOO.append("test2")
            env.FOO.append("test3")

            env.BAH.prepend("A")
            prependenv("BAH", "B")
            env.BAH.append("C")

        self._test(func=_rex,
                   env={},
                   expected_actions = [
                       Setenv('FOO', 'test1'),
                       Appendenv('FOO', 'test2'),
                       Appendenv('FOO', 'test3'),
                       Setenv('BAH', 'A'),
                       Prependenv('BAH', 'B'),
                       Appendenv('BAH', 'C')],
                   expected_output = {
                       'FOO': ",".join(["test1","test2","test3"]),
                       'BAH': " ".join(["B","A","C"])})

    def test_9(self):
        """Test literal and expandable strings."""
        def _rex():
            env.A = "hello"
            env.FOO = expandable("$A")  # will convert to '${A}'
            env.BAH = expandable("${A}")
            env.EEK = literal("$A")

        def _rex2():
            env.BAH = "omg"
            env.FOO.append("$BAH")
            env.FOO.append(literal("${BAH}"))
            env.FOO.append(expandable("like, ").l("$SHE said, ").e("$BAH"))

        self._test(func=_rex,
                   env={},
                   expected_actions = [
                       Setenv('A', 'hello'),
                       Setenv('FOO', '${A}'),
                       Setenv('BAH', '${A}'),
                       Setenv('EEK', '$A')],
                   expected_output = {
                       'A': 'hello',
                       'FOO': 'hello',
                       'BAH': 'hello',
                       'EEK': '$A'})

        self._test(func=_rex2,
                   env={},
                   expected_actions = [
                       Setenv('BAH', 'omg'),
                       Setenv('FOO', '${BAH}'),
                       Appendenv('FOO', '${BAH}'),
                       Appendenv('FOO', 'like, $SHE said, ${BAH}')],
                   expected_output = {
                       'BAH': 'omg',
                       'FOO': os.pathsep.join(['omg', '${BAH}', 'like']) + ', $SHE said, omg'})

    def test_version_binding(self):
        """Test the Rex binding of the Version class."""
        v = VersionBinding(Version("1.2.3alpha"))
        self.assertEqual(v.major, 1)
        self.assertEqual(v.minor, 2)
        self.assertEqual(v.patch, "3alpha")
        self.assertEqual(len(v), 3)
        self.assertEqual(v[1], 2)
        self.assertEqual(v[:2], (1, 2))
        self.assertEqual(str(v), "1.2.3alpha")
        self.assertEqual(v[5], None)
        self.assertEqual(v.as_tuple(), (1, 2, "3alpha"))

    def test_old_style_commands(self):
        """Convert old style commands to rex"""
        expected = ""
        rez_commands = convert_old_commands([], annotate=False)
        self.assertEqual(rez_commands, expected)

        expected = "setenv('A', 'B')"
        rez_commands = convert_old_commands(["export A=B"], annotate=False)
        self.assertEqual(rez_commands, expected)

        expected = "setenv('A', 'B:$C')"
        rez_commands = convert_old_commands(["export A=B:$C"], annotate=False)
        self.assertEqual(rez_commands, expected)

        expected = "setenv('A', 'hey \"there\"')"
        rez_commands = convert_old_commands(['export A="hey \\"there\\""'],
                                            annotate=False)
        self.assertEqual(rez_commands, expected)

        expected = "appendenv('A', 'B')"
        rez_commands = convert_old_commands(["export A=$A:B"], annotate=False)
        self.assertEqual(rez_commands, expected)

        expected = "prependenv('A', 'B')"
        rez_commands = convert_old_commands(["export A=B:$A"], annotate=False)
        self.assertEqual(rez_commands, expected)

        expected = "appendenv('A', 'B:$C')"
        rez_commands = convert_old_commands(["export A=$A:B:$C"],
                                            annotate=False)
        self.assertEqual(rez_commands, expected)

        expected = "prependenv('A', '$C:B')"
        rez_commands = convert_old_commands(["export A=$C:B:$A"],
                                            annotate=False)
        self.assertEqual(rez_commands, expected)


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
