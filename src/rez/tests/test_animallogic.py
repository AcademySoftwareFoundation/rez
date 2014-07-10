from rez.rex import RexExecutor, Python, Setenv, Appendenv, Prependenv, Info, \
    Comment, Alias, Command, Source, Error, Shebang, Unsetenv
from rez.exceptions import RexError, RexUndefinedVariableError, BuildSystemError
import rez.vendor.unittest2 as unittest
from rez.tests.util import TestBase
import inspect
import textwrap
import os


import rez.util
import rez.rex
from rez.util import convert_old_commands
from rez.vendor.version.requirement import Requirement
from rez.tests.util import TestBase, TempdirMixin
import shutil
from rez.build_system import create_build_system





class TestConvertingOldStyleCommands(TestBase):

    def test_old_style_cmake_module_path_commands_with_separator(self):

        command = "export CMAKE_MODULE_PATH=!ROOT!/cmake';'$CMAKE_MODULE_PATH"
        expected = "prependenv('CMAKE_MODULE_PATH', '{root}/cmake')"

        self.assertEqual(expected, convert_old_commands([command], annotate=False))

        command = "export CMAKE_MODULE_PATH=!ROOT!/cmake:$CMAKE_MODULE_PATH"
        expected = "prependenv('CMAKE_MODULE_PATH', '{root}/cmake')"

        self.assertEqual(expected, convert_old_commands([command], annotate=False))

    def test_old_style_commands_enclosed_in_quotes(self):

        command = "export FOO='BAR SPAM'"
        expected = "setenv('FOO', 'BAR SPAM')"

        self.assertEqual(expected, convert_old_commands([command], annotate=False))

        command = 'export FOO="BAR SPAM"'
        expected = "setenv('FOO', 'BAR SPAM')"

        self.assertEqual(expected, convert_old_commands([command], annotate=False))

    def test_old_style_non_pathsep_commands(self):

        test_separators = {"FOO":" ", "BAR":","}

        rez.util.ANIMAL_LOGIC_SEPARATORS = test_separators
        rez.contrib.animallogic.util.ANIMAL_LOGIC_SEPARATORS = test_separators

        command = "export FOO=!ROOT!/cmake $FOO"
        expected = "prependenv('FOO', '{root}/cmake')"

        self.assertEqual(expected, convert_old_commands([command], annotate=False))

        command = "export BAR=!ROOT!/cmake,$BAR"
        expected = "prependenv('BAR', '{root}/cmake')"

        self.assertEqual(expected, convert_old_commands([command], annotate=False))


class TestRex(TestBase):

    def test_non_pathsep_commands(self):

        rez.rex.DEFAULT_ENV_SEP_MAP = {"FOO":" ", "BAR":","}

        def _rex():
            prependenv("FOO", "spam")
            prependenv("FOO", "ham")
            prependenv("FOO", "chips")
            appendenv("BAR", "eggs")
            appendenv("BAR", "bacon")
            appendenv("BAR", "beans")

        expected = {"FOO":"chips ham spam",
                    "BAR":"eggs,bacon,beans"}

        executor = self._create_executor({})
        executor.execute_function(_rex)
        self.assertEqual(executor.get_output(), expected)

    def _create_executor(self, env, **kwargs):

        interp = Python(target_environ={}, passive=True)

        return RexExecutor(interpreter=interp,
                           parent_environ=env,
                           bind_rez=False,
                           shebang=False,
                           **kwargs)


class TestBuild(TestBase, TempdirMixin):

    class FakeArgParseOpts(object):

        def __getattr__(self, key):
            return None

    @classmethod
    def setUpClass(cls):
        TempdirMixin.setUpClass()

        path = os.path.dirname(__file__)
        packages_path = os.path.join(path, "data", "builds", "packages")

        cls.src_root = os.path.join(cls.root, "src", "packages")
        cls.install_root = os.path.join(cls.root, "packages")

        shutil.copytree(packages_path, cls.src_root)

        cls.settings = dict(
            packages_path=[cls.install_root],
            add_bootstrap_path=False,
            resolve_caching=False,
            warn_untimestamped=False,
            implicit_packages=[])

    @classmethod
    def tearDownClass(cls):
        TempdirMixin.tearDownClass()

    def test_multiple_build_systems_with_cmake(self):

        working_dir = os.path.join(self.src_root, "animallogic", "multiple_build_systems_with_cmake")
        buildsys = create_build_system(working_dir, opts=TestBuild.FakeArgParseOpts())
        self.assertEqual(buildsys.name(), "cmake")

    def test_multiple_build_systems_without_cmake(self):

        working_dir = os.path.join(self.src_root, "animallogic", "multiple_build_systems_without_cmake")
        self.assertRaises(BuildSystemError, create_build_system, working_dir, opts=TestBuild.FakeArgParseOpts())


class TestVariantPathMunging(TestBase):

    def test_safe_string(self):

        self.assertEqual(Requirement("!foo").safe_str(), "_not_foo")
        self.assertEqual(Requirement("foo-5+<6").safe_str(), "foo-5_thru_6")
        self.assertEqual(Requirement("foo-5+").safe_str(), "foo-5_ge_")
        self.assertEqual(Requirement("foo-<5").safe_str(), "foo_lt_5")
        self.assertEqual(Requirement("~foo").safe_str(), "_weak_foo")


def get_test_suites():

    suites = []
    tests = [TestConvertingOldStyleCommands, TestRex, TestBuild, TestVariantPathMunging]

    for test in tests:
        suites.append(unittest.TestLoader().loadTestsFromTestCase(test))

    return suites


if __name__ == '__main__':

    unittest.main()
