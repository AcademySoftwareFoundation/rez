"""
Test directive requirement request/build
"""
import os
import shutil
import unittest
from rez.tests.util import TestBase, TempdirMixin
from rez.resolved_context import ResolvedContext
from rez.build_process import create_build_process
from rez.build_system import create_build_system
from rez.package_repository import package_repository_manager
from rez.package_py_utils import expand_requirement
from rez.packages import get_package
from rez.utils.request_directives import \
    parse_directive, anonymous_directive_string


class TestBuildDirectives(TestBase, TempdirMixin):
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

    def test_build_soft(self):
        self._test_build("soft_dep", "1.0.0")
        self._test_build("soft_dep", "1.1.0")
        self._test_build("soft_var", "2.1")
        self._test_build("soft_var", "3.0")
        self._test_build("soft")

        soft = get_package("soft", "1", paths=[self.install_root])
        self.assertEqual("soft_dep-1.0", str(soft.requires[0]))
        self.assertEqual(["soft_var-2.1"], list(map(str, soft.variants[0])))
        self.assertEqual(["soft_var-3.0"], list(map(str, soft.variants[1])))

    def test_build_soft_early(self):
        self._test_build("soft_dep", "1.0.0")
        self._test_build("soft_dep", "1.1.0")
        self._test_build("soft_var", "2.1")
        self._test_build("soft_var", "3.0")
        self._test_build("soft_early")

        soft = get_package("soft_early", "1", paths=[self.install_root])
        self.assertEqual("soft_dep-1.0", str(soft.requires[0]))
        self.assertEqual(["soft_var-2.1"], list(map(str, soft.variants[0])))
        self.assertEqual(["soft_var-3.0"], list(map(str, soft.variants[1])))


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

    def test_wildcard_to_directive(self):
        requests = [
            ("foo-**", "foo//harden", None),
            ("foo==**", "foo//harden", None),
            ("foo-*", "foo//harden(1)", None),
            ("foo-1.**", "foo-1//harden", None),
            ("foo-1.0.*", "foo-1.0//harden(3)", None),
            ("foo==*", "foo//harden(1)", None),
            ("foo==1.*", "foo==1//harden(2)", None),
            ("foo-1.*+", "foo-1+//harden(2)", None),
            ("foo>1.*", "foo>1//harden(2)", None),
            ("foo>=1.*", "foo-1+//harden(2)", None),
            ("foo<**", "foo//harden", None),  # but meaningless
            # unsupported
            ("foo-2.*|1", None, "multi-rank hardening"),
            ("foo<=4,>2.*", None, "multi-rank hardening"),
            ("foo-1..2.*", None, "multi-rank hardening"),
            ("foo-1|2.*", None, "multi-rank hardening"),
            ("foo-1.*+<2.*.*", None, "multi-rank hardening"),
            ("foo-1.*+<3|==5.*.*", None, "multi-rank hardening"),
        ]

        for case, expected, message in requests:
            request = parse_directive(case)

            if expected is None:
                self.assertEqual(case, request, message)
            else:
                directive = anonymous_directive_string(request) or ""
                self.assertEqual(expected, "//".join([request, directive]), case)


if __name__ == '__main__':
    unittest.main()
