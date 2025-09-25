# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
test the build system
"""
from rez.config import config
from rez.build_process import create_build_process, BuildType
from rez.build_system import create_build_system, BuildSystem
from rez.resolved_context import ResolvedContext
from rez.exceptions import BuildError, BuildContextResolveError, \
    PackageFamilyNotFoundError
import unittest
from rez.tests.util import TestBase, TempdirMixin, find_file_in_path, \
    per_available_shell, install_dependent, program_dependent
from rez.utils.platform_ import platform_
from rez.shells import create_shell
from rez.packages import get_developer_package
from rez.rex import RexExecutor
import shutil
import os.path


class TestBuild(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls):
        TempdirMixin.setUpClass()

        packages_path = cls.data_path("builds", "packages")
        cls.src_root = os.path.join(cls.root, "src", "packages")
        cls.install_root = os.path.join(cls.root, "packages")
        shutil.copytree(packages_path, cls.src_root)

        # include modules
        pypath = cls.data_path("python", "late_bind")

        cls.settings = dict(
            packages_path=[cls.install_root],
            package_filter=None,
            package_definition_python_path=pypath,
            resolve_caching=False,
            warn_untimestamped=False,
            warn_old_commands=False,
            implicit_packages=[])

    @classmethod
    def tearDownClass(cls):
        TempdirMixin.tearDownClass()

    @classmethod
    def _create_builder(cls, working_dir):
        buildsys = create_build_system(working_dir)
        return create_build_process(process_type="local",
                                    working_dir=working_dir,
                                    build_system=buildsys)

    @classmethod
    def _create_context(cls, *pkgs):
        return ResolvedContext(pkgs)

    def _test_build(self, name, version=None):
        # create the builder
        working_dir = os.path.join(self.src_root, name)
        if version:
            working_dir = os.path.join(working_dir, version)
        builder = self._create_builder(working_dir)

        # build the package from a clean build dir, then build it again
        builder.build(clean=True)
        builder.build()

        # build and install it from a clean dir, then build and install it again
        builder.build(install_path=self.install_root, install=True, clean=True)
        builder.build(install_path=self.install_root, install=True)

    def _test_build_build_util(self):
        """Build, install, test the build_util package."""
        self._test_build("build_util", "1")
        self._create_context("build_util==1")

    def _test_build_floob(self):
        """Build, install, test the floob package."""
        self._test_build("floob")
        self._create_context("floob==1.2.0")

    def _test_build_foo(self):
        """Build, install, test the foo package."""
        self._test_build("foo", "1.0.0")
        self._create_context("foo==1.0.0")

        self._test_build("foo", "1.1.0")
        rxt = self._create_context("foo==1.1.0")

        # test that expected env-var is set by foo's commands
        environ = rxt.get_environ(parent_environ={})
        self.assertEqual(environ.get("FOO_IN_DA_HOUSE"), "1")

        # test that include modules are working
        self.assertEqual(environ.get("EEK"), "2")

    def _test_build_loco(self):
        """Test that a package with conflicting requirements fails correctly.
        """
        working_dir = os.path.join(self.src_root, "loco", "3")
        builder = self._create_builder(working_dir)
        self.assertRaises(BuildContextResolveError, builder.build, clean=True)

    def _test_build_bah(self):
        """Build, install, test the bah package."""
        self._test_build("bah", "2.1")
        self._create_context("bah==2.1", "foo==1.0.0")
        self._create_context("bah==2.1", "foo==1.1.0")

    def _test_build_anti(self):
        """Build, install, test the anti package."""
        self._test_build("anti", "1.0.0")
        self._create_context("anti==1.0.0")

    def _test_build_translate_lib(self):
        """Build, install, test the translate_lib package."""
        self._test_build("translate_lib", "2.2.0")
        context = self._create_context("translate_lib==2.2.0")
        environ = context.get_environ()
        root = environ['REZ_TRANSLATE_LIB_ROOT']
        self.assertTrue(find_file_in_path('translate_lib.cmake', environ['CMAKE_MODULE_PATH']))
        # is testing symlinks
        self.assertTrue(find_file_in_path('an_unspaced_document', os.path.join(root, 'docs')))
        # is testing spaces in symlinks per issue #553
        self.assertTrue(find_file_in_path('a spaced document', os.path.join(root, 'docs')))

    def _test_build_sup_world(self):
        """Build, install, test the sup_world package."""
        from subprocess import PIPE
        self._test_build("sup_world", "3.8")
        context = self._create_context("sup_world==3.8")
        proc = context.execute_command(['greeter'], stdout=PIPE, text=True)
        stdout = proc.communicate()[0]
        self.assertEqual('hola amigo', stdout.strip())

    @per_available_shell()
    @install_dependent()
    def test_build_whack(self, shell):
        """Test that a broken build fails correctly.
        """
        config.override("default_shell", shell)
        self.inject_python_repo()

        working_dir = os.path.join(self.src_root, "whack")
        builder = self._create_builder(working_dir)
        self.assertRaises(BuildError, builder.build, clean=True)

    @per_available_shell()
    @install_dependent()
    def test_builds(self, shell):
        """Test an interdependent set of builds.
        """
        config.override("default_shell", shell)
        self.inject_python_repo()

        self._test_build_build_util()
        self._test_build_floob()
        self._test_build_foo()
        self._test_build_loco()
        self._test_build_bah()

    @per_available_shell()
    @install_dependent()
    def test_builds_anti(self, shell):
        """Test we can build packages that contain anti packages
        """
        config.override("default_shell", shell)
        self.inject_python_repo()

        self._test_build_build_util()
        self._test_build_floob()
        self._test_build_anti()

    @program_dependent("cmake")
    @install_dependent()
    def test_build_cmake(self):
        """Test a cmake-based package."""
        if platform_.name == "windows":
            self.skipTest("This test does not run on Windows due to temporary"
                          "limitations of the cmake build_system plugin"
                          " implementation.")

        self.assertRaises(PackageFamilyNotFoundError, self._create_context,
                          "sup_world==3.8")
        self._test_build_translate_lib()
        self._test_build_sup_world()

    @unittest.skipIf(platform_.name == "windows", "Skipping because make and GCC are not common on Windows")
    @program_dependent("make", "g++")
    def test_build_custom(self):
        """Test a make-based package that uses the custom_build attribute."""
        from subprocess import PIPE

        self._test_build("hello", "1.0")
        context = self._create_context("hello==1.0")

        proc = context.execute_command(['hai'], stdout=PIPE)
        stdout = proc.communicate()[0]
        self.assertEqual('Oh hai!', stdout.decode("utf-8").strip())

    def test_set_standard_vars_escaping(self):
        """Test that set_standard_vars properly escapes environment variables."""
        # Create a test package directory with special characters in description
        temp_pkg_dir = os.path.join(self.root, "test_special_package")
        os.makedirs(temp_pkg_dir)

        # Create a package.py file with special characters
        package_py_content = """
name = "test_special_chars"
version = "1.0.0"
description = 'A test package with "quotes" and $pecial characters & more!'
authors = ["test@example.com"]
requires = []
"""

        package_py_path = os.path.join(temp_pkg_dir, "package.py")
        with open(package_py_path, 'w') as f:
            f.write(package_py_content)

        # Get the developer package
        package = get_developer_package(temp_pkg_dir)

        # Get the first variant from the package
        variant = next(package.iter_variants())

        # Create a minimal context for testing - we don't need to resolve packages
        # since we're only testing environment variable escaping
        context = self._create_context()  # Empty context

        # Create a bash shell executor using RexExecutor
        bash_shell = create_shell("bash")
        executor = RexExecutor(interpreter=bash_shell, parent_environ={}, shebang=False)

        build_path = os.path.join(self.root, "build")
        install_path = os.path.join(self.root, "install")

        BuildSystem.set_standard_vars(
            executor=executor,
            context=context,
            variant=variant,
            build_type=BuildType.local,
            install=True,
            build_path=build_path,
            install_path=install_path
        )

        # Get the generated shell script
        script_output = executor.get_output()

        self.assertEqual(
            script_output,
            f"""export REZ_BUILD_ENV="1"
export REZ_BUILD_PATH="{build_path}"
export REZ_BUILD_THREAD_COUNT="{package.config.build_thread_count}"
export REZ_BUILD_VARIANT_INDEX="0"
export REZ_BUILD_VARIANT_REQUIRES=''
export REZ_BUILD_VARIANT_SUBPATH=""
export REZ_BUILD_PROJECT_VERSION='1.0.0'
export REZ_BUILD_PROJECT_NAME='test_special_chars'
export REZ_BUILD_PROJECT_DESCRIPTION='A test package with "quotes" and $pecial characters & more!'
export REZ_BUILD_PROJECT_FILE='{package_py_path}'
export REZ_BUILD_SOURCE_PATH='{temp_pkg_dir}'
export REZ_BUILD_REQUIRES=''
export REZ_BUILD_REQUIRES_UNVERSIONED=''
export REZ_BUILD_TYPE='local'
export REZ_BUILD_INSTALL="1"
export REZ_BUILD_INSTALL_PATH='{install_path}'
"""
        )


if __name__ == '__main__':
    unittest.main()
