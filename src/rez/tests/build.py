from rez.build_process import LocalSequentialBuildProcess
from rez.build_system import create_build_system
from rez.resolved_context import ResolvedContext
import rez.contrib.unittest2 as unittest
from rez.tests.util import ShellDependentTest
from rez.shells import get_shell_types
from rez.settings import settings
import shutil
import tempfile
import os.path



class TestBuild(ShellDependentTest):

    @classmethod
    def setUpClass(cls):
        # copy all the test packages to a temp location, we don't want to
        # pollute the source with 'build' subdirs
        cls.root = tempfile.mkdtemp(prefix="rez_build_test_")

        path = os.path.dirname(__file__)
        packages_path = os.path.join(path, "data", "build", "packages")
        cls.root = tempfile.mkdtemp(suffix="_rez_build_test")
        cls.src_root = os.path.join(cls.root, "src", "packages")
        cls.install_root = os.path.join(cls.root, "packages")

        shutil.copytree(packages_path, cls.src_root)

        cls.settings = dict(
            packages_path=[cls.install_root],
            add_bootstrap_path=False,
            implicit_packages=[])

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.root):
            shutil.rmtree(cls.root)

    @classmethod
    def _create_builder(cls, working_dir):
        buildsys = create_build_system(working_dir)
        return LocalSequentialBuildProcess(working_dir,
                                           buildsys,
                                           vcs=None)

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
        self.assertTrue(builder.build(clean=True))
        self.assertTrue(builder.build())

        # build and install it from a clean dir, then build and install it again
        self.assertTrue(builder.build(install_path=self.install_root, install=True, clean=True))
        self.assertTrue(builder.build(install_path=self.install_root, install=True))

    def test_build_build_util(self):
        """Build, install, test the build_util package."""
        self._test_build("build_util", "1")
        self._create_context("build_util==1")

    def test_build_nover(self):
        """Build, install, test the nover package."""
        self._test_build("nover")
        self._create_context("nover==")

    def test_build_foo(self):
        """Build, install, test the foo package."""
        self._test_build("foo", "1.0.0")
        self._create_context("foo==1.0.0")

        self._test_build("foo", "1.1.0")
        self._create_context("foo==1.1.0")

    def test_build_bah(self):
        """Build, install, test the bah package."""
        self._test_build("bah", "2.1")
        self._create_context("bah==2.1", "foo==1.0.0")
        self._create_context("bah==2.1", "foo==1.1.0")


def get_test_suites():
    suites = []
    suite = unittest.TestSuite()

    for shell in get_shell_types():
        suite.addTest(TestBuild("test_create_shell", shell))
        suite.addTest(TestBuild("test_build_build_util", shell))
        suite.addTest(TestBuild("test_build_nover", shell))
        suite.addTest(TestBuild("test_build_foo", shell))
        suite.addTest(TestBuild("test_build_bah", shell))

    suites.append(suite)
    return suites
