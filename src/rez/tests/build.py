from rez.build_process import LocalSequentialBuildProcess
from rez.build_system import create_build_system
from rez.resolved_context import ResolvedContext
import rez.contrib.unittest2 as unittest
import shutil
import tempfile
import threading
import os.path



class TestBuild(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # copy all the test packages to a temp location, we don't want to
        # pollute the source with 'build' subdirs
        cls.root = tempfile.mkdtemp(suffix="_rez_build_test")

        path = os.path.dirname(__file__)
        packages_path = os.path.join(path, "data", "build", "packages")
        cls.root = tempfile.mkdtemp(suffix="_rez_build_test")
        cls.src_root = os.path.join(cls.root, "src", "packages")
        cls.install_root = os.path.join(cls.root, "packages")

        cls.context_kwargs = dict(
            package_paths=[cls.install_root],
            caching=False,
            add_implicit_packages=False,
            add_bootstrap_path=False)

        shutil.copytree(packages_path, cls.src_root)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.root):
            shutil.rmtree(cls.root)

    @classmethod
    def _create_builder(cls, working_dir):
        buildsys = create_build_system(working_dir)
        return LocalSequentialBuildProcess(working_dir,
                                           buildsys,
                                           vcs=None,
                                           **cls.context_kwargs)

    @classmethod
    def _create_context(cls, *pkgs):
        return ResolvedContext(pkgs, **cls.context_kwargs)

    @classmethod
    def _test_build(cls, name, version=None):
        # create the builder
        working_dir = os.path.join(cls.src_root, name)
        if version:
            working_dir = os.path.join(working_dir, version)
        builder = cls._create_builder(working_dir)

        # build the package, then built it again
        builder.build()
        builder.build()

        # build and install it, then build and install it again
        builder.build(install_path=cls.install_root, install=True)
        builder.build(install_path=cls.install_root, install=True)

        # build and install again, from a clean build
        builder.build(install_path=cls.install_root, clean=True, install=True)

    def test_build_nover(self):
        """Build, install, test the nover package."""
        self._test_build("nover")
        self._create_context("nover==")

    def test_build_foo(self):
        """Build, install, test the foo package."""
        self._test_build("foo", "1.0.0")
        self._create_context("foo==1.0.0")


def get_test_suites():
    suites = []
    suite = unittest.TestSuite()
    suite.addTest(TestBuild("test_build_nover"))
    suite.addTest(TestBuild("test_build_foo"))
    suites.append(suite)
    return suites
