from rez.rex import RexExecutor, Python, Setenv, Appendenv, Prependenv, Info, \
    Comment, Alias, Command, Source, Error, Shebang, Unsetenv
from rez.exceptions import RexError, RexUndefinedVariableError
from rez.config import config
import rez.vendor.unittest2 as unittest
from rez.tests.util import TestBase
from rez.util import convert_old_commands
import inspect
import textwrap
import os


class TestRex(TestBase):

    def _create_executor(self, env, **kwargs):
        interp = Python(target_environ={}, passive=True)
        return RexExecutor(interpreter=interp,
                           parent_environ=env,
                           bind_rez=False,
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
                       Setenv('BAH', '${FOO}'),
                       Setenv('EEK', '${BAH}'),
                       Info('expansions visible in control flow')],
                   expected_output = {
                       'FOO': 'foo',
                       'BAH': 'foo',
                       'EEK': 'foo'})

        # with EXT defined
        self._test(func=_rex,
                   env={"EXT": "alpha"},
                   expected_actions = [
                       Setenv('FOO', 'foo'),
                       Setenv('BAH', '${FOO}'),
                       Setenv('EEK', '${BAH}'),
                       Info('expansions visible in control flow'),
                       Setenv('FEE', '${EXT}')],
                   expected_output = {
                       'FOO': 'foo',
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
        """Custom environment variable separators"""

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
        """Convert old style commands to rex"""

        expected = ""
        rez_commands = convert_old_commands([], annotate=False)
        self.assertEqual(rez_commands, expected)

        expected = "setenv('A', 'B')"
        rez_commands = convert_old_commands(["export A=B"], annotate=False)
        self.assertEqual(rez_commands, expected)

        expected = "setenv('A', 'B:{env.C}')"
        rez_commands = convert_old_commands(["export A=B:$C"], annotate=False)
        self.assertEqual(rez_commands, expected)

        expected = "appendenv('A', 'B')"
        rez_commands = convert_old_commands(["export A=$A:B"], annotate=False)
        self.assertEqual(rez_commands, expected)

        expected = "prependenv('A', 'B')"
        rez_commands = convert_old_commands(["export A=B:$A"], annotate=False)
        self.assertEqual(rez_commands, expected)

        expected = "appendenv('A', 'B:{env.C}')"
        rez_commands = convert_old_commands(["export A=$A:B:$C"],
                                            annotate=False)
        self.assertEqual(rez_commands, expected)

        expected = "prependenv('A', '{env.C}:B')"
        rez_commands = convert_old_commands(["export A=$C:B:$A"],
                                            annotate=False)
        self.assertEqual(rez_commands, expected)


def get_test_suites():
    suites = []
    suite = unittest.TestSuite()
    suite.addTest(TestRex("test_1"))
    suite.addTest(TestRex("test_2"))
    suite.addTest(TestRex("test_3"))
    suite.addTest(TestRex("test_4"))
    suite.addTest(TestRex("test_5"))
    suite.addTest(TestRex("test_6"))
    suite.addTest(TestRex("test_7"))
    suite.addTest(TestRex("test_8"))
    suite.addTest(TestRex("test_9"))
    suites.append(suite)
    return suites

if __name__ == '__main__':
    unittest.main()
