"""
Test directive requirement request/build
"""
import os
import unittest
from rez.build_process import create_build_process
from rez.build_system import create_build_system
from rez.package_repository import package_repository_manager
from rez.package_py_utils import expand_requirement
from rez.packages import get_package
from rez.exceptions import BuildContextResolveError
from rez.tests.util import TestBase, TempdirMixin
from rez.tests.ghostwriter import DeveloperRepository, early


class _TestBuildDirectivesBase(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls):
        TempdirMixin.setUpClass()
        cls.base = cls.root
        cls.root = os.path.join(cls.root, "test_directives")

    def setUp(self):
        install_root = os.path.join(self.root, "install")
        src_root = os.path.join(self.root, "developer")

        self.install_root = install_root
        self.src_root = src_root
        self.dev_repo = DeveloperRepository(src_root)
        self.settings = dict(
            packages_path=[install_root],
            package_filter=None,
            resolve_caching=False,
            warn_untimestamped=False,
            warn_old_commands=False,
            implicit_packages=[],
        )
        super(_TestBuildDirectivesBase, self).setUp()

    def tearDown(self):
        TempdirMixin.tearDownClass()

    def _create_builder(self, working_dir):
        buildsys = create_build_system(working_dir)
        return create_build_process(process_type="local",
                                    working_dir=working_dir,
                                    build_system=buildsys,
                                    quiet=True)

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


class TestBuildDirectives(_TestBuildDirectivesBase):

    def test_build_soft(self):
        _k = {"build_command": False}

        self.dev_repo.add("dep", version="1.0.0", **_k)
        self.dev_repo.add("dep", version="1.1.0", **_k)
        self.dev_repo.add("var", version="2.1", **_k)
        self.dev_repo.add("var", version="3.0", **_k)
        self.dev_repo.add("lock", version="1", requires=["dep-1.0.0"], **_k)
        self.dev_repo.add("soft",
                          version="1",
                          requires=["dep-1//harden(2)", "lock"],
                          variants=[["var-2//harden(2)"], ["var-3.*"]],
                          **_k)

        self._test_build("dep", "1.0.0")
        self._test_build("dep", "1.1.0")
        self._test_build("var", "2.1")
        self._test_build("var", "3.0")
        self._test_build("lock", "1")
        self._test_build("soft", "1")

        soft = get_package("soft", "1", paths=[self.install_root])
        self.assertEqual("dep-1.0", str(soft.requires[0]))

        self.assertEqual(["var-2.1"], list(map(str, soft.variants[0])))
        self.assertEqual(["var-3.0"], list(map(str, soft.variants[1])))

    def test_build_soft_early(self):
        _k = {"build_command": False}

        self.dev_repo.add("dep", version="1.0.0", **_k)
        self.dev_repo.add("dep", version="1.1.0", **_k)
        self.dev_repo.add("lock", version="1", requires=["dep-1.0.0"], **_k)

        @early()
        def requires():
            return (["dep-1//harden(2)", "lock"]
                    if building else ["dep-1//harden(2)"])

        self.dev_repo.add("soft", version="1", requires=requires, **_k)

        self._test_build("dep", "1.0.0")
        self._test_build("dep", "1.1.0")
        self._test_build("lock", "1")
        self._test_build("soft", "1")

        soft = get_package("soft", "1", paths=[self.install_root])
        self.assertEqual("dep-1.0", str(soft.requires[0]))

    def test_empty_early_requires(self):
        _k = {"build_command": False}

        @early()
        def requires():
            return [] if building else ["bar-1//harden"]

        self.dev_repo.add("bar", version="1.0.0", **_k)
        self.dev_repo.add("foo", version="1.0.0", requires=requires, **_k)

        self._test_build("bar", "1.0.0")
        self._test_build("foo", "1.0.0")
        foo = get_package("foo", "1.0.0", paths=[self.install_root])
        # no harden, because there were no requires when building is True
        self.assertEqual("bar-1", str(foo.requires[0]))


class TestBuildNoLateExpansion(_TestBuildDirectivesBase):

    def test_build_soft_without_late_expand(self):
        _k = {"build_command": False}

        self.dev_repo.add("dep", version="1.0.0", **_k)
        self.dev_repo.add("dep", version="1.1.0", **_k)
        self.dev_repo.add("lock", version="1", requires=["dep-1.0.0"], **_k)
        self.dev_repo.add("soft",
                          version="1",
                          requires=["dep-1.*", "lock"],
                          **_k)

        self._test_build("dep", "1.0.0")
        self._test_build("dep", "1.1.0")
        self._test_build("lock", "1")
        # conflicts occurred: (dep-1.0.0 <--!--> dep==1.1.0)
        self.assertRaises(BuildContextResolveError,
                          self._test_build, "soft", "1")


class TestRequestDirectives(TestBase):

    def test_old_style_expansion(self):
        pkg_data = {
            "bar": {
                "1.2.1": {"name": "bar", "version": "1.2.1"},
                "1.2.2": {"name": "bar", "version": "1.2.2"},
                "2.2.3": {"name": "bar", "version": "2.2.3"},
            },
        }
        mem_path = "memory@%s" % hex(id(pkg_data))
        resolved_repo = package_repository_manager.get_repository(mem_path)
        resolved_repo.data = pkg_data

        def expand_on_mem(request):
            return expand_requirement(request, paths=[mem_path])

        self.assertEqual("bar-1.2+<2", expand_on_mem("bar-1.*+<*"))
        self.assertEqual("bar<2", expand_on_mem("bar<*"))
        self.assertEqual("bar<2.2.3", expand_on_mem("bar<**"))
        self.assertEqual("bar-2.2.3", expand_on_mem("bar-**"))
        self.assertEqual("bar-1.2+", expand_on_mem("bar-1.*+"))


if __name__ == '__main__':
    unittest.main()
