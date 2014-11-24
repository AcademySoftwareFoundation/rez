from rez.build_system import create_build_system
from rez.build_process import LocalSequentialBuildProcess
from rez.config import config
from rez.exceptions import BuildSystemError
from rez.packages import load_developer_package
from rez.rex import RexExecutor, Python
from rez.resolved_context import ResolvedContext
from rez.tests.util import TestBase, TempdirMixin
from rez.util import convert_old_commands
from rez.vendor.version.requirement import Requirement
from rez.contrib.animallogic.util import get_epoch_datetime_from_str
from rezplugins.build_system.cmake import get_current_variant_index
import rez.vendor.unittest2 as unittest
import datetime
import os
import shutil
import tempfile


class TestConvertingOldStyleCommands(TestBase):

    def test_old_style_cmake_module_path_commands_with_separator(self):

        expected = "prependenv('CMAKE_MODULE_PATH', '{root}/cmake')"

        command = "export CMAKE_MODULE_PATH=!ROOT!/cmake';'$CMAKE_MODULE_PATH"
        self.assertEqual(expected, convert_old_commands([command], annotate=False))

        command = "export CMAKE_MODULE_PATH=!ROOT!/cmake:$CMAKE_MODULE_PATH"
        self.assertEqual(expected, convert_old_commands([command], annotate=False))

        command = "export CMAKE_MODULE_PATH=!ROOT!/cmake;$CMAKE_MODULE_PATH"
        self.assertEqual(expected, convert_old_commands([command], annotate=False))

        command = 'export CMAKE_MODULE_PATH=!ROOT!/cmake";"$CMAKE_MODULE_PATH'
        self.assertEqual(expected, convert_old_commands([command], annotate=False))

    def test_old_style_commands_enclosed_in_quotes(self):

        expected = "setenv('FOO', 'BAR SPAM')"

        command = "export FOO='BAR SPAM'"
        self.assertEqual(expected, convert_old_commands([command], annotate=False))

        command = 'export FOO="BAR SPAM"'
        self.assertEqual(expected, convert_old_commands([command], annotate=False))

    def test_old_style_non_pathsep_commands(self):

        test_separators = {"FOO":" ", "BAR":","}
        config.override("env_var_separators", test_separators)

        command = "export FOO=!ROOT!/cmake $FOO"
        expected = "prependenv('FOO', '{root}/cmake')"
        self.assertEqual(expected, convert_old_commands([command], annotate=False))

        command = "export BAR=!ROOT!/cmake,$BAR"
        expected = "prependenv('BAR', '{root}/cmake')"
        self.assertEqual(expected, convert_old_commands([command], annotate=False))


class TestRexFlattenEnvironment(TestBase):

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

    def assertUndefined(self):

        self.assertFalse(self.executor.defined(self.variable))

    def assertDefined(self):

        self.assertTrue(self.executor.defined(self.variable))

    def assertValue(self, expected=None):

        expected = os.path.join(self.root, self.variable) if expected is None else expected
        self.assertEquals(expected, self.executor.env.get(self.variable).value())

    def assertIsLink(self, target):

        self.assertTrue(os.path.islink(os.path.join(self.root, self.variable, target)))

    def assertReadlink(self, link, target):

        self.assertEqual(os.readlink(os.path.join(self.root, self.variable, link)), target)

    def assertNumberOfContents(self, expected, target=None):

        target = os.path.join(self.root, self.variable) if target is None else target
        self.assertEqual(expected, len(os.listdir(target)))

    def test_variable_undefined(self):

        self.assertUndefined()

        self.executor.flatten(self.root, variables=[self.variable])

        self.assertUndefined()

    def test_variable_defined_but_empty(self):

        self.executor.setenv(self.variable, "")

        self.assertDefined()

        self.executor.flatten(self.root, variables=[self.variable])

        self.assertDefined()
        self.assertValue("")

    def test_variable_defined_containing_missing_path(self):

        self.executor.setenv(self.variable, "/this/path/does/not/exist")

        self.assertDefined()

        self.executor.flatten(self.root, variables=[self.variable])

        self.assertDefined()
        self.assertValue()
        self.assertNumberOfContents(0)

    def test_variable_defined_containing_empty_path(self):

        item = os.path.join(self.root, "item")
        self._makedirs(item)

        self.executor.setenv(self.variable, item)
        self.assertDefined()

        self.executor.flatten(self.root, variables=[self.variable])

        self.assertDefined()
        self.assertValue()
        self.assertNumberOfContents(0)

    def test_variable_defined_containing_path_with_single_file(self):

        item = os.path.join(self.root, "item")
        self._makedirs(item)

        self._touch(os.path.join(item, "test.sh"))

        self.executor.setenv(self.variable, item)

        self.assertDefined()

        self.executor.flatten(self.root, variables=[self.variable])

        self.assertDefined()
        self.assertValue()
        self.assertNumberOfContents(1)
        self.assertIsLink("test.sh")
        self.assertReadlink("test.sh", os.path.join(item, "test.sh"))

    def test_variable_defined_containing_path_with_single_directory(self):

        item = os.path.join(self.root, "item")
        self._makedirs(item)
        self._makedirs(os.path.join(item, "test"))

        self.executor.setenv(self.variable, item)
        self.assertDefined()

        self.executor.flatten(self.root, variables=[self.variable])

        self.assertDefined()

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
        self.assertDefined()

        self.executor.flatten(self.root, variables=[self.variable])

        self.assertDefined()
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

        self.assertDefined()

        self.executor.flatten(self.root, variables=[self.variable])

        self.assertDefined()
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
        self.assertDefined()

        self.executor.flatten(self.root, variables=[self.variable])

        self.assertDefined()
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


class TestRex(TestBase):

    def test_non_pathsep_commands(self):

        test_separators = {"FOO":" ", "BAR":","}
        config.override("env_var_separators", test_separators)

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
                           shebang=False,
                           **kwargs)


class TestVariantPathMunging(TestBase):

    def test_safe_string(self):

        self.assertEqual(Requirement("!foo").safe_str(), "_not_foo")
        self.assertEqual(Requirement("foo-5+<6").safe_str(), "foo-5_thru_6")
        self.assertEqual(Requirement("foo-5+").safe_str(), "foo-5_ge_")
        self.assertEqual(Requirement("foo-<5").safe_str(), "foo_lt_5")
        self.assertEqual(Requirement("~foo").safe_str(), "_weak_foo")


class TestCMakeBuildSystem(TestBase, TempdirMixin):

    class FakeArgParseOpts(object):

        def __getattr__(self, key):
            return None

    @classmethod
    def setUpClass(cls):
        TempdirMixin.setUpClass()

        path = os.path.dirname(__file__)
        packages_path = os.path.join(path, "data", "builds", "packages", "animallogic")

        cls.src_root = os.path.join(cls.root, "src", "packages")
        cls.install_root = os.path.join(cls.root, "packages")

        shutil.copytree(packages_path, cls.src_root)

        cls.settings = dict(
            packages_path=[cls.install_root],
            add_bootstrap_path=False,
            resolve_caching=False,
            warn_untimestamped=False,
            implicit_packages=[])

        working_dir = os.path.join(cls.src_root, "foo", "1.0.0")
        builder = cls._create_builder(working_dir)
        builder.build(install_path=cls.install_root, install=True, clean=True)

        working_dir = os.path.join(cls.src_root, "foo", "1.1.0")
        builder = cls._create_builder(working_dir)
        builder.build(install_path=cls.install_root, install=True, clean=True)

    @classmethod
    def tearDownClass(cls):

        TempdirMixin.tearDownClass()

    @classmethod
    def _create_builder(cls, working_dir):
        buildsys = create_build_system(working_dir)
        return LocalSequentialBuildProcess(working_dir,
                                           buildsys,
                                           vcs=None)

    def test_multiple_build_systems_with_cmake(self):

        working_dir = os.path.join(self.src_root, "multiple_build_systems_with_cmake")
        buildsys = create_build_system(working_dir, opts=TestCMakeBuildSystem.FakeArgParseOpts())
        self.assertEqual(buildsys.name(), "cmake")

    def test_multiple_build_systems_without_cmake(self):

        working_dir = os.path.join(self.src_root, "multiple_build_systems_without_cmake")
        print "!!!!", working_dir
        self.assertRaises(BuildSystemError, create_build_system, working_dir, opts=TestCMakeBuildSystem.FakeArgParseOpts())

    def test_current_variant_index_with_variants(self):

        working_dir = os.path.join(self.src_root, "current_variant_index_with_variants")
        package = load_developer_package(working_dir)

        variants = list(package.iter_variants())
        self.assertEqual(len(variants), 2)

        for i, variant in enumerate(variants):
            request = variant.get_requires(build_requires=True, private_build_requires=True)
            context = ResolvedContext(request, building=True)
            self.assertEqual(get_current_variant_index(context, package), i)

    def test_current_variant_index_without_variants(self):

        working_dir = os.path.join(self.src_root, "current_variant_index_without_variants")
        package = load_developer_package(working_dir)

        for i, variant in enumerate(package.iter_variants()):
            self.assertEqual(i, 0)
            request = variant.get_requires(build_requires=True, private_build_requires=True)
            context = ResolvedContext(request, building=True)
            self.assertEqual(get_current_variant_index(context, package), 0)


class TestGetEpochDatetimeFromStr(TestBase):

    def test_timestamp(self):

        epoch = get_epoch_datetime_from_str("1415237983")
        expected = datetime.datetime.strptime("2014-11-06 12:39:43", "%Y-%m-%d %H:%M:%S")
        self.assertEqual(expected, epoch)

    def test_relative(self):

        epoch = get_epoch_datetime_from_str("-1d")
        expected = datetime.datetime.now() - datetime.timedelta(1)
        self.assertEqual(expected.year, epoch.year)
        self.assertEqual(expected.month, epoch.month)
        self.assertEqual(expected.day, epoch.day)
        self.assertEqual(expected.hour, epoch.hour)
        # We can't compare more than this as execution time is different.

    def test_exact(self):

        epoch = get_epoch_datetime_from_str("2014-11-06 12:39:43")
        expected = datetime.datetime.strptime("2014-11-06 12:39:43", "%Y-%m-%d %H:%M:%S")
        self.assertEqual(expected, epoch)

        epoch = get_epoch_datetime_from_str("2014_11_06_12_39_43", format_="%Y_%m_%d_%H_%M_%S")
        expected = datetime.datetime.strptime("2014-11-06 12:39:43", "%Y-%m-%d %H:%M:%S")
        self.assertEqual(expected, epoch)


def get_test_suites():

    suites = []
    tests = [TestConvertingOldStyleCommands, TestRex, TestVariantPathMunging,
             TestCMakeBuildSystem, TestGetEpochDatetimeFromStr]

    for test in tests:
        suites.append(unittest.TestLoader().loadTestsFromTestCase(test))

    return suites


if __name__ == '__main__':

    unittest.main()
