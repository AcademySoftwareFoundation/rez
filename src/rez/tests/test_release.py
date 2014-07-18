from rez.build_process import LocalSequentialBuildProcess
from rez.build_system import create_build_system
from rez.resolved_context import ResolvedContext
from rez.exceptions import BuildError, BuildContextResolveError
import rez.vendor.unittest2 as unittest
from rez.tests.util import TestBase, TempdirMixin, shell_dependent, \
    install_dependent
from rez.resources import clear_caches
import rez.bind.platform
import rez.bind.arch
import rez.bind.os
import rez.bind.python
import shutil
import os.path


class TestRelease(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls):
        TempdirMixin.setUpClass()

        path = os.path.dirname(__file__)
        packages_path = os.path.join(path, "data", "release", "packages")
        cls.src_root = os.path.join(cls.root, "src", "packages")
        cls.install_root = os.path.join(cls.root, "packages")
        shutil.copytree(packages_path, cls.src_root)

        cls.settings = dict(
            packages_path=[cls.install_root],
            release_packages_path=cls.install_root,
            add_bootstrap_path=False,
            resolve_caching=False,
            warn_untimestamped=False,
            implicit_packages=[])

    @classmethod
    def tearDownClass(cls):
        TempdirMixin.tearDownClass()


def get_test_suites():
    suites = []
    suite = unittest.TestSuite()
    suite.addTest(TestRelease("test_1"))
    suites.append(suite)
    return suites


if __name__ == '__main__':
    unittest.main()
