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
from rezplugins.build_system.cmake import get_current_variant_index
import rez.vendor.unittest2 as unittest
import os
import shutil


# class TestConvertingOldStyleCommands(TestBase):
#
#     def test_old_style_cmake_module_path_commands_with_separator(self):
#
#         expected = "prependenv('CMAKE_MODULE_PATH', '{root}/cmake')"
#
#         command = "export CMAKE_MODULE_PATH=!ROOT!/cmake';'$CMAKE_MODULE_PATH"
#         self.assertEqual(expected, convert_old_commands([command], annotate=False))
#
#         command = "export CMAKE_MODULE_PATH=!ROOT!/cmake:$CMAKE_MODULE_PATH"
#         self.assertEqual(expected, convert_old_commands([command], annotate=False))
#
#         command = "export CMAKE_MODULE_PATH=!ROOT!/cmake;$CMAKE_MODULE_PATH"
#         self.assertEqual(expected, convert_old_commands([command], annotate=False))
#
#         command = 'export CMAKE_MODULE_PATH=!ROOT!/cmake";"$CMAKE_MODULE_PATH'
#         self.assertEqual(expected, convert_old_commands([command], annotate=False))
#
#     def test_old_style_commands_enclosed_in_quotes(self):
#
#         expected = "setenv('FOO', 'BAR SPAM')"
#
#         command = "export FOO='BAR SPAM'"
#         self.assertEqual(expected, convert_old_commands([command], annotate=False))
#
#         command = 'export FOO="BAR SPAM"'
#         self.assertEqual(expected, convert_old_commands([command], annotate=False))
#
#     def test_old_style_non_pathsep_commands(self):
#
#         test_separators = {"FOO":" ", "BAR":","}
#         config.override("env_var_separators", test_separators)
#
#         command = "export FOO=!ROOT!/cmake $FOO"
#         expected = "prependenv('FOO', '{root}/cmake')"
#         self.assertEqual(expected, convert_old_commands([command], annotate=False))
#
#         command = "export BAR=!ROOT!/cmake,$BAR"
#         expected = "prependenv('BAR', '{root}/cmake')"
#         self.assertEqual(expected, convert_old_commands([command], annotate=False))
#
#
# class TestRex(TestBase):
#
#     def test_non_pathsep_commands(self):
#
#         test_separators = {"FOO":" ", "BAR":","}
#         config.override("env_var_separators", test_separators)
#
#         def _rex():
#             prependenv("FOO", "spam")
#             prependenv("FOO", "ham")
#             prependenv("FOO", "chips")
#             appendenv("BAR", "eggs")
#             appendenv("BAR", "bacon")
#             appendenv("BAR", "beans")
#
#         expected = {"FOO":"chips ham spam",
#                     "BAR":"eggs,bacon,beans"}
#
#         executor = self._create_executor({})
#         executor.execute_function(_rex)
#         self.assertEqual(executor.get_output(), expected)
#
#     def _create_executor(self, env, **kwargs):
#
#         interp = Python(target_environ={}, passive=True)
#
#         return RexExecutor(interpreter=interp,
#                            parent_environ=env,
#                            bind_rez=False,
#                            shebang=False,
#                            **kwargs)
#
#
# class TestVariantPathMunging(TestBase):
#
#     def test_safe_string(self):
#
#         self.assertEqual(Requirement("!foo").safe_str(), "_not_foo")
#         self.assertEqual(Requirement("foo-5+<6").safe_str(), "foo-5_thru_6")
#         self.assertEqual(Requirement("foo-5+").safe_str(), "foo-5_ge_")
#         self.assertEqual(Requirement("foo-<5").safe_str(), "foo_lt_5")
#         self.assertEqual(Requirement("~foo").safe_str(), "_weak_foo")
#
#
# class TestCMakeBuildSystem(TestBase, TempdirMixin):
#
#     class FakeArgParseOpts(object):
#
#         def __getattr__(self, key):
#             return None
#
#     @classmethod
#     def setUpClass(cls):
#         TempdirMixin.setUpClass()
#
#         path = os.path.dirname(__file__)
#         packages_path = os.path.join(path, "data", "builds", "packages", "animallogic")
#
#         cls.src_root = os.path.join(cls.root, "src", "packages")
#         cls.install_root = os.path.join(cls.root, "packages")
#
#         shutil.copytree(packages_path, cls.src_root)
#
#         cls.settings = dict(
#             packages_path=[cls.install_root],
#             add_bootstrap_path=False,
#             resolve_caching=False,
#             warn_untimestamped=False,
#             implicit_packages=[])
#
#         working_dir = os.path.join(cls.src_root, "foo", "1.0.0")
#         builder = cls._create_builder(working_dir)
#         builder.build(install_path=cls.install_root, install=True, clean=True)
#
#         working_dir = os.path.join(cls.src_root, "foo", "1.1.0")
#         builder = cls._create_builder(working_dir)
#         builder.build(install_path=cls.install_root, install=True, clean=True)
#
#     @classmethod
#     def tearDownClass(cls):
#
#         TempdirMixin.tearDownClass()
#
#     @classmethod
#     def _create_builder(cls, working_dir):
#         buildsys = create_build_system(working_dir)
#         return LocalSequentialBuildProcess(working_dir,
#                                            buildsys,
#                                            vcs=None)
#
#     def test_multiple_build_systems_with_cmake(self):
#
#         working_dir = os.path.join(self.src_root, "multiple_build_systems_with_cmake")
#         buildsys = create_build_system(working_dir, opts=TestCMakeBuildSystem.FakeArgParseOpts())
#         self.assertEqual(buildsys.name(), "cmake")
#
#     def test_multiple_build_systems_without_cmake(self):
#
#         working_dir = os.path.join(self.src_root, "multiple_build_systems_without_cmake")
#         self.assertRaises(BuildSystemError, create_build_system, working_dir, opts=TestCMakeBuildSystem.FakeArgParseOpts())
#
#     def test_current_variant_index_with_variants(self):
#
#         working_dir = os.path.join(self.src_root, "current_variant_index_with_variants")
#         package = load_developer_package(working_dir)
#
#         variants = list(package.iter_variants())
#         self.assertEqual(len(variants), 2)
#
#         for i, variant in enumerate(variants):
#             request = variant.get_requires(build_requires=True, private_build_requires=True)
#             context = ResolvedContext(request, building=True)
#             self.assertEqual(get_current_variant_index(context, package), i)
#
#     def test_current_variant_index_without_variants(self):
#
#         working_dir = os.path.join(self.src_root, "current_variant_index_without_variants")
#         package = load_developer_package(working_dir)
#
#         for i, variant in enumerate(package.iter_variants()):
#             self.assertEqual(i, 0)
#             request = variant.get_requires(build_requires=True, private_build_requires=True)
#             context = ResolvedContext(request, building=True)
#             self.assertEqual(get_current_variant_index(context, package), 0)

class TestVariantResolutionOrder(TestBase, TempdirMixin):

    class FakeArgParseOpts(object):

        def __getattr__(self, key):
            return None

    @classmethod
    def setUpClass(cls):
        TempdirMixin.setUpClass()

        path = os.path.dirname(__file__)
        packages_path = os.path.join(path, "data", "builds", "packages", "animallogic")

        cls.install_root = os.path.join(cls.root, "packages")

        cls.settings = dict(
            packages_path=[cls.install_root],
            add_bootstrap_path=False,
            resolve_caching=False,
            warn_untimestamped=False,
            implicit_packages=[])

        shutil.copytree(packages_path, cls.install_root)

    @classmethod
    def tearDownClass(cls):
        TempdirMixin.tearDownClass()

    def test_resolve_higher_to_lower_version_ordered_variants(self):
        """
        Test we pick up the higher version of the dependant package when the variants are from higher to lower
        """
        expected_package_version = self.getPackageVersion('bar', '4.8.5')
        request = ['multi_version_variant_higher_to_lower_version_order']
        context = ResolvedContext(request)
        resolved_package_version = TestVariantResolutionOrder.getResolvedPackageVersion(context, 'bar')

        self.assertEqual(resolved_package_version, expected_package_version, 'wrong bar version selected')

    def test_resolve_lower_to_higher_version_ordered_variants(self):
        """
        Test we pick up the higher version of the dependant package when the variants are ordered from lower to higher
        """
        expected_package_version = self.getPackageVersion('bar', '4.8.5')

        request = ['multi_version_variant_lower_to_higher_version_order']
        context = ResolvedContext(request)
        resolved_package_version = TestVariantResolutionOrder.getResolvedPackageVersion(context, 'bar')

        self.assertEqual(resolved_package_version, expected_package_version, 'wrong bar version selected')

    def test_variant_selection_variant_default_order(self):
        """
        Test that the variant gets selected if based on the order of the variants when no variant package is selected
        """
        expected_bah_package_version = self.getPackageVersion("bah", "2.0.0")
        expected_eek_package_version = self.getPackageVersion("eek", "1.0.1")

        request = ['two_packages_in_variant_unsorted']
        context = ResolvedContext(request)
        resolved_bah_package_version = TestVariantResolutionOrder.getResolvedPackageVersion(context, 'bah')
        resolved_eek_package_version = TestVariantResolutionOrder.getResolvedPackageVersion(context, 'eek')

        self.assertEqual(resolved_bah_package_version, expected_bah_package_version, 'wrong bah version selected')
        self.assertEqual(resolved_eek_package_version, expected_eek_package_version, 'wrong eek version selected')

    def test_variant_selection_requested_priority(self):
        """
        Test that a particular variant gets selected if it is part of the requirements
        """

        expected_bah_package_version = self.getPackageVersion("bah", "2.0.0")
        expected_eek_package_version = self.getPackageVersion("eek", "1.0.1")

        request = ['two_packages_in_variant_unsorted', 'bah']
        context = ResolvedContext(request)
        resolved_bah_package_version = TestVariantResolutionOrder.getResolvedPackageVersion(context, 'bah')
        resolved_eek_package_version = TestVariantResolutionOrder.getResolvedPackageVersion(context, 'eek')

        self.assertEqual(resolved_bah_package_version, expected_bah_package_version, 'wrong bah version selected')
        self.assertEqual(resolved_eek_package_version, expected_eek_package_version, 'wrong eek version selected')

    def test_variant_selection_requested_priority_2(self):
        """
        Test that a particular variant gets selected if it is part of the requirements
        """
        expected_bah_package_version = self.getPackageVersion("bah", "1.0.1")
        expected_eek_package_version = self.getPackageVersion("eek", "2.0.0")

        request = ['two_packages_in_variant_unsorted', 'eek']
        context = ResolvedContext(request)
        resolved_bah_package_version = TestVariantResolutionOrder.getResolvedPackageVersion(context, 'bah')
        resolved_eek_package_version = TestVariantResolutionOrder.getResolvedPackageVersion(context, 'eek')

        self.assertEqual(resolved_bah_package_version, expected_bah_package_version, 'wrong bah version selected')
        self.assertEqual(resolved_eek_package_version, expected_eek_package_version, 'wrong eek version selected')

    def test_variant_selection_requested_priority_3(self):
        """
        Test that a particular variant gets selected if it is part of the requirements and the package contains
        diff packages families in the same column
        """
        expected_foo_package_version = self.getPackageVersion("foo", "1.0.0")
        expected_bah_package_version = self.getPackageVersion("bah", "1.0.1")

        request = ['variable_variant_package_in_single_column', 'bah']
        context = ResolvedContext(request)
        resolved_bah_package_version = TestVariantResolutionOrder.getResolvedPackageVersion(context, 'bah')
        resolved_foo_package_version = TestVariantResolutionOrder.getResolvedPackageVersion(context, 'foo')

        self.assertEqual(resolved_bah_package_version, expected_bah_package_version, 'wrong bah version selected')
        self.assertEqual(resolved_foo_package_version, expected_foo_package_version, 'wrong foo version selected')

        expected_eek_package_version = self.getPackageVersion("eek", "1.0.1")

        request2 = ['variable_variant_package_in_single_column', 'eek']
        context2 = ResolvedContext(request2)
        resolved_eek_package_version = TestVariantResolutionOrder.getResolvedPackageVersion(context2, 'eek')
        resolved_foo_package_version = TestVariantResolutionOrder.getResolvedPackageVersion(context2, 'foo')

        self.assertEqual(resolved_eek_package_version, expected_eek_package_version, 'wrong eek version selected')
        self.assertEqual(resolved_foo_package_version, expected_foo_package_version, 'wrong foo version selected')


    def test_variant_selection_resolved_priority(self):
        """
        Test that a particular variant gets selected if it is already resolved
        """
        expected_bah_package_version = self.getPackageVersion("bah", "2.0.0")
        expected_eek_package_version = self.getPackageVersion("eek", "1.0.1")

        request = ['two_packages_in_variant_unsorted', 'eek-1']
        context = ResolvedContext(request)
        resolved_bah_package_version = TestVariantResolutionOrder.getResolvedPackageVersion(context, 'bah')
        resolved_eek_package_version = TestVariantResolutionOrder.getResolvedPackageVersion(context, 'eek')

        self.assertEqual(resolved_bah_package_version, expected_bah_package_version, 'wrong bah version selected')
        self.assertEqual(resolved_eek_package_version, expected_eek_package_version, 'wrong eek version selected')

    def test_variant_repeatable_ambiguous_selection(self):
        """
        Test the variant selection is repeatable when the selection is ambiguous
        """

        request = ['multi_packages_variant_sorted', 'bah']
        context1 = ResolvedContext(request)
        contextToCompare1 = []
        for resolve_package in context1.resolved_packages:
            if resolve_package.name != 'multi_packages_variant_sorted':
                contextToCompare1.append(resolve_package)

        request = ['multi_packages_variant_unsorted', 'bah']
        context2 = ResolvedContext(request)
        contextToCompare2 = []
        for resolve_package in context2.resolved_packages:
            if resolve_package.name != 'multi_packages_variant_unsorted':
                contextToCompare2.append(resolve_package)

        self.assertEqual(contextToCompare1, contextToCompare2, 'resolved packages differ not repeatable selection')

    def getPackageVersion(self, package_name, package_version):
        package_path = os.path.join(self.install_root, package_name, package_version)
        package = load_developer_package(package_path)
        return package.version

    @staticmethod
    def getResolvedPackageVersion(context, package_name):
        for package in context.resolved_packages:
            if package.name == package_name:
                return package.version


def get_test_suites():

    suites = []
    tests = [TestConvertingOldStyleCommands, TestRex, TestVariantPathMunging, TestCMakeBuildSystem, TestVariantResolutionOrder]
    tests = [TestVariantResolutionOrder]

    for test in tests:
        suites.append(unittest.TestLoader().loadTestsFromTestCase(test))

    return suites


if __name__ == '__main__':

    unittest.main()
