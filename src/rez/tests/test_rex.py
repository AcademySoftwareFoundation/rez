from rez.rex import RexExecutor, Python, Setenv, Appendenv, Prependenv, Info, \
    Comment, Alias, Command, Source, Error, Shebang, Unsetenv
from rez.rex_bindings import VersionBinding
from rez.exceptions import RexError, RexUndefinedVariableError
from rez.config import config
import rez.vendor.unittest2 as unittest
from rez.vendor.version.version import Version
from rez.tests.util import TestBase, TempdirMixin
from rez.util import convert_old_commands
import inspect
import shutil
import tempfile
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


class TestRexFlattenEnvironment(TestBase, TempdirMixin):

    @classmethod
    def setUpClass(cls):
        TempdirMixin.setUpClass()

        cls.settings = dict(flatten_env_vars=[])

    @classmethod
    def tearDownClass(cls):

        TempdirMixin.tearDownClass()

    def setUp(self):
        TestBase.setUp(self)

        self.variable = "env_var_to_flatten"
        self.executor = self._create_executor({})

    def _create_executor(self, env, **kwargs):

        interp = Python(target_environ={}, passive=True)

        return RexExecutor(interpreter=interp,
                           parent_environ=env,
                           shebang=False,
                           **kwargs)

    def assertUndefined(self):

        self.assertFalse(self.executor.defined(self.variable))

    def assertDefined(self):

        self.assertTrue(self.executor.defined(self.variable))

    def assertValue(self, expected=None):

        expected = os.path.join(self.root, self.variable) if expected is None else expected
        self.assertEquals(expected, self.executor.env.get(self.variable).value())

    def test_variable_undefined_remains_undefined(self):

        self.assertUndefined()

        self.executor.flatten(self.root, variables=[self.variable])

        self.assertUndefined()

    def test_variable_defined_but_empty_remains_empty(self):

        self.executor.setenv(self.variable, "")

        self.assertDefined()

        self.executor.flatten(self.root, variables=[self.variable])

        self.assertDefined()
        self.assertValue("")


class TestRexFlattener(TestBase):

    @classmethod
    def setUpClass(cls):

        cls.settings = dict(flatten_env_vars=[])

    def setUp(self):

        self.root = tempfile.mkdtemp(prefix="rez_selftest_")
        self.variable = "env_var_to_flatten"
        self.executor = self._create_executor({})

    def tearDown(self):

        if os.path.exists(self.root):
            shutil.rmtree(self.root)

    def _touch(self, filepath):

        fd = open(filepath, "w")
        fd.write("Hello, World!")
        fd.close()

    def _makedirs(self, directorypath):

        os.makedirs(directorypath)

    def _create_executor(self, env, **kwargs):

        interp = Python(target_environ={}, passive=True)

        return RexExecutor(interpreter=interp,
                           parent_environ=env,
                           shebang=False,
                           **kwargs)

    def assertValue(self, expected=None):

        expected = os.path.join(self.root, self.variable) if expected is None else expected
        self.assertEquals(expected, self.executor.env.get(self.variable).value())

    def assertIsDir(self, target):

        self.assertTrue(os.path.isdir(os.path.join(self.root, self.variable, target)))

    def assertIsLink(self, target):

        self.assertTrue(os.path.islink(os.path.join(self.root, self.variable, target)))

    def assertReadlink(self, link, target):

        self.assertEqual(os.readlink(os.path.join(self.root, self.variable, link)), target)

    def assertNumberOfContents(self, expected, target=None):

        target = os.path.join(self.root, self.variable) if target is None else target
        self.assertEqual(expected, len(os.listdir(target)))


class TestRexDefaultFlattener(TestRexFlattener):

    def test_variable_defined_containing_missing_path_creates_empty_flatten(self):

        self.executor.setenv(self.variable, "/this/path/does/not/exist")

        self.executor.flatten(self.root, variables=[self.variable])

        self.assertValue()
        self.assertNumberOfContents(0)

    def test_variable_defined_containing_empty_path(self):

        item = os.path.join(self.root, "item")
        self._makedirs(item)

        self.executor.setenv(self.variable, item)

        self.executor.flatten(self.root, variables=[self.variable])

        self.assertValue()
        self.assertNumberOfContents(0)

    def test_variable_defined_containing_path_with_single_file(self):

        item = os.path.join(self.root, "item")
        self._makedirs(item)
        self._touch(os.path.join(item, "test.sh"))

        self.executor.setenv(self.variable, item)

        self.executor.flatten(self.root, variables=[self.variable])

        self.assertValue()
        self.assertNumberOfContents(1)
        self.assertIsLink("test.sh")
        self.assertReadlink("test.sh", os.path.join(item, "test.sh"))

    def test_variable_defined_containing_path_with_single_directory(self):

        item = os.path.join(self.root, "item")
        self._makedirs(item)
        self._makedirs(os.path.join(item, "test"))

        self.executor.setenv(self.variable, item)

        self.executor.flatten(self.root, variables=[self.variable])

        self.assertValue()
        self.assertNumberOfContents(1)
        self.assertIsLink("test")
        self.assertReadlink("test", os.path.join(item, "test"))

    def test_variable_defined_containing_paths_duplicate_files(self):

        item1 = os.path.join(self.root, "item1")
        self._makedirs(item1)
        self._touch(os.path.join(item1, "test1.sh"))

        item2 = os.path.join(self.root, "item2")
        self._makedirs(item2)
        self._touch(os.path.join(item2, "test1.sh"))
        self._touch(os.path.join(item2, "test2.sh"))

        self.executor.setenv(self.variable, item1 + os.pathsep + item2)

        self.executor.flatten(self.root, variables=[self.variable])

        self.assertValue()
        self.assertNumberOfContents(2)
        self.assertIsLink("test1.sh")
        self.assertReadlink("test1.sh", os.path.join(item1, "test1.sh"))
        self.assertIsLink("test2.sh")
        self.assertReadlink("test2.sh", os.path.join(item2, "test2.sh"))

    def test_variable_defined_containing_path_which_is_single_file(self):

        item = os.path.join(self.root, "item")
        self._makedirs(item)
        test_file = os.path.join(item, "test.sh")
        self._touch(test_file)

        self.executor.setenv(self.variable, test_file)

        self.executor.flatten(self.root, variables=[self.variable])

        self.assertValue(expected=os.path.join(self.root, self.variable) + os.pathsep + os.path.join(self.root, self.variable, "test.sh"))
        self.assertNumberOfContents(1)
        self.assertIsLink("test.sh")
        self.assertReadlink("test.sh", os.path.join(item, "test.sh"))

    def test_variable_defined_containing_complex_mixture(self):

        item1 = os.path.join(self.root, "item1")
        self._makedirs(item1)
        self._touch(os.path.join(item1, "test1.sh"))
        test_file1 = os.path.join(item1, "test3.sh")
        self._touch(os.path.join(item1, "test3.sh"))

        item2 = os.path.join(self.root, "item2")
        self._makedirs(item2)
        self._touch(os.path.join(item2, "test1.sh"))
        self._touch(os.path.join(item2, "test2.sh"))
        self._makedirs(os.path.join(item2, "test1"))

        item3 = os.path.join(self.root, "item3")
        self._makedirs(item3)
        self._makedirs(os.path.join(item3, "test1"))
        self._makedirs(os.path.join(item3, "test2"))

        test_file2 = os.path.join(item2, "test3.sh")
        self._touch(os.path.join(item2, "test3.sh"))

        self.executor.setenv(self.variable, test_file1 + os.pathsep + item1 + os.pathsep + item2 + os.pathsep + item3 + os.pathsep + test_file2)

        self.executor.flatten(self.root, variables=[self.variable])

        self.assertValue(expected=os.path.join(self.root, self.variable) + os.pathsep + os.path.join(self.root, self.variable, "test3.sh"))
        self.assertNumberOfContents(5)
        self.assertIsLink("test1.sh")
        self.assertReadlink("test1.sh", os.path.join(item1, "test1.sh"))
        self.assertIsLink("test2.sh")
        self.assertReadlink("test2.sh", os.path.join(item2, "test2.sh"))
        self.assertIsLink("test1")
        self.assertReadlink("test1", os.path.join(item2, "test1"))
        self.assertIsLink("test2")
        self.assertReadlink("test2", os.path.join(item3, "test2"))
        self.assertIsLink("test3.sh")
        self.assertReadlink("test3.sh", os.path.join(item1, "test3.sh"))


class TestRexPythonPathFlattener(TestRexFlattener):

    def setUp(self):

        TestRexFlattener.setUp(self)

        self.variable = "PYTHONPATH"

    def test_variable_contains_directory_of_py_files(self):
        """
        PYTHONPATH=self.root/item
        """

        item = os.path.join(self.root, "item")
        self._makedirs(item)
        test_file1 = os.path.join(item, "test1.py")
        self._touch(test_file1)
        test_file2 = os.path.join(item, "test2.py")
        self._touch(test_file2)

        self.executor.setenv(self.variable, item)

        self.executor.flatten(self.root, variables=[self.variable])

        self.assertValue(expected=os.path.join(self.root, self.variable))
        self.assertNumberOfContents(2)
        self.assertIsLink("test1.py")
        self.assertReadlink("test1.py", os.path.join(item, "test1.py"))

    def test_variable_contains_egg_file(self):
        """
        PYTHONPATH=self.root/item/test.egg
        """

        item = os.path.join(self.root, "item")
        self._makedirs(item)
        test_file = os.path.join(item, "test.egg")
        self._touch(test_file)

        self.executor.setenv(self.variable, test_file)

        self.executor.flatten(self.root, variables=[self.variable])

        self.assertValue(expected=os.path.join(self.root, self.variable) + os.pathsep + os.path.join(self.root, self.variable, "test.egg"))
        self.assertNumberOfContents(1)
        self.assertIsLink("test.egg")
        self.assertReadlink("test.egg", os.path.join(item, "test.egg"))

    def test_variable_contains_directory(self):
        """
        PYTHONPATH=self.root/item/
        """

        item = os.path.join(self.root, "item")
        self._makedirs(item)

        dir_ = os.path.join(item, "dir")
        self._makedirs(dir_)
        test_file = os.path.join(dir_, "__init__.py")
        self._touch(test_file)

        self.executor.setenv(self.variable, item)

        self.executor.flatten(self.root, variables=[self.variable])

        self.assertValue()
        self.assertNumberOfContents(1)
        self.assertIsDir("dir")
        self.assertIsLink("dir/__init__.py")
        self.assertReadlink("dir/__init__.py", os.path.join(item, "dir/__init__.py"))

    def test_variable_contains_egg_file_also_on_path(self):
        """
        PYTHONPATH=self.root/item/:self.root/item/test.egg
        """

        item = os.path.join(self.root, "item")
        self._makedirs(item)
        test_file = os.path.join(item, "test.egg")
        self._touch(test_file)

        self.executor.setenv(self.variable, test_file)

        self.executor.flatten(self.root, variables=[self.variable])

        self.assertValue(expected=os.path.join(self.root, self.variable) + os.pathsep + os.path.join(self.root, self.variable, "test.egg"))
        self.assertNumberOfContents(1)
        self.assertIsLink("test.egg")
        self.assertReadlink("test.egg", os.path.join(item, "test.egg"))

    def test_variable_contains_egg_file_not_on_path(self):
        """
        PYTHONPATH=self.root/item/
        """

        item = os.path.join(self.root, "item")
        self._makedirs(item)
        test_file = os.path.join(item, "test.egg")
        self._touch(test_file)
        self._touch(os.path.join(item, "test.pth"))
        self._touch(os.path.join(item, "site.py"))

        self.executor.setenv(self.variable, test_file)

        self.executor.flatten(self.root, variables=[self.variable])

        self.assertValue(expected=os.path.join(self.root, self.variable) + os.pathsep + os.path.join(self.root, self.variable, "test.egg"))
        self.assertNumberOfContents(1)
        self.assertIsLink("test.egg")
        self.assertReadlink("test.egg", os.path.join(item, "test.egg"))

    def test_variable_contains_multiple_directories_providing_namespace(self):
        """
        PYTHONPATH=self.root/item1:self.root/item2
        """

        item1 = os.path.join(self.root, "item1")
        self._makedirs(item1)
        self._makedirs(os.path.join(item1, "namespace"))
        self._touch(os.path.join(item1, "namespace", "__init__.py"))
        self._makedirs(os.path.join(item1, "namespace", "sub_a"))
        self._touch(os.path.join(item1, "namespace", "sub_a", "__init__.py"))

        item2 = os.path.join(self.root, "item2")
        self._makedirs(item2)
        self._makedirs(os.path.join(item2, "namespace"))
        self._touch(os.path.join(item2, "namespace", "__init__.py"))
        self._makedirs(os.path.join(item2, "namespace", "sub_b"))
        self._touch(os.path.join(item2, "namespace", "sub_b", "__init__.py"))

        self.executor.setenv(self.variable, item1 + os.pathsep + item2)

        self.executor.flatten(self.root, variables=[self.variable])

        self.assertValue()
        self.assertNumberOfContents(1)
        self.assertIsDir("namespace")
        self.assertIsDir("namespace/sub_a")
        self.assertIsDir("namespace/sub_b")
        self.assertIsLink("namespace/__init__.py")
        self.assertReadlink("namespace/__init__.py", os.path.join(item1, "namespace/__init__.py"))
        self.assertReadlink("namespace/sub_a/__init__.py", os.path.join(item1, "namespace/sub_a/__init__.py"))
        self.assertReadlink("namespace/sub_b/__init__.py", os.path.join(item2, "namespace/sub_b/__init__.py"))


def get_test_suites():

    suites = []
    tests = [TestRex, TestRexFlattenEnvironment, TestRexDefaultFlattener]

    for test in tests:
        suites.append(unittest.TestLoader().loadTestsFromTestCase(test))

    return suites


if __name__ == '__main__':
    unittest.main()
