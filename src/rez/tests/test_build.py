from rez.build_process_ import create_build_process
from rez.build_system import create_build_system
from rez.resolved_context import ResolvedContext
from rez.exceptions import BuildError, BuildContextResolveError,\
    PackageFamilyNotFoundError
import rez.vendor.unittest2 as unittest
from rez.tests.util import TestBase, TempdirMixin, find_file_in_path, \
    shell_dependent, install_dependent, cmake_dependent
import shutil
import os.path


class TestBuild(TestBase, TempdirMixin):

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
            package_filter=None,
            resolve_caching=False,
            warn_untimestamped=False,
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
        self._create_context("foo==1.1.0")

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
        find_file_in_path('translate_lib.cmake', environ['CMAKE_MODULE_PATH'])

    def _test_build_sup_world(self):
        """Build, install, test the sup_world package."""
        from subprocess import PIPE
        self._test_build("sup_world", "3.8")
        context = self._create_context("sup_world==3.8")
        proc = context.execute_command(['test_ghetto'], stdout=PIPE)
        stdout = proc.communicate()[0]
        self.assertEqual('sup dogg - how is dis shizzle doin today?',
                         stdout.strip())

    @shell_dependent()
    @install_dependent
    def test_build_whack(self):
        """Test that a broken build fails correctly."""
        working_dir = os.path.join(self.src_root, "whack")
        builder = self._create_builder(working_dir)
        self.assertRaises(BuildError, builder.build, clean=True)

    @shell_dependent()
    @install_dependent
    def test_builds(self):
        """Test an interdependent set of builds."""
        self._test_build_build_util()
        self._test_build_floob()
        self._test_build_foo()
        self._test_build_loco()
        self._test_build_bah()

    @shell_dependent()
    @install_dependent
    def test_builds_anti(self):
        """Test we can build packages that contain anti packages"""
        self._test_build_build_util()
        self._test_build_floob()
        self._test_build_anti()

    @cmake_dependent
    def test_build_cmake(self):
        self.assertRaises(PackageFamilyNotFoundError, self._create_context,
            "sup_world==3.8")
        self._test_build_translate_lib()
        self._test_build_sup_world()


def get_test_suites():
    # TODO: variant-based test
    suites = []
    suite = unittest.TestSuite()
    suite.addTest(TestBuild("test_build_whack"))
    suite.addTest(TestBuild("test_builds"))
    suite.addTest(TestBuild("test_builds_anti"))
    suite.addTest(TestBuild("test_build_cmake"))
    suites.append(suite)
    return suites

if __name__ == '__main__':
    unittest.main()
