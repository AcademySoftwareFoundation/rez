"""
test package copying
"""
import shutil
import time
import os.path
import os

from rez.system import system
from rez.build_process import create_build_process
from rez.build_system import create_build_system
from rez.resolved_context import ResolvedContext
from rez.packages import get_latest_package
from rez.package_copy import copy_package
from rez.vendor.version.version import VersionRange
from rez.tests.util import TestBase, TempdirMixin


class TestCopyPackage(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls):
        TempdirMixin.setUpClass()

        packages_path = cls.data_path("builds", "packages")
        cls.src_root = os.path.join(cls.root, "src", "packages")
        cls.install_root = os.path.join(cls.root, "packages")
        shutil.copytree(packages_path, cls.src_root)

        # repo we will copy packages into
        cls.dest_install_root = os.path.join(cls.root, "dest_packages")

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

    def setup_once(self):
        # build packages used by this test
        self._build_package("build_util", "1")
        self._build_package("floob")
        self._build_package("foo", "1.0.0")
        self._build_package("foo", "1.1.0")
        self._build_package("bah", "2.1")

    @classmethod
    def _create_builder(cls, working_dir):
        buildsys = create_build_system(working_dir)
        return create_build_process(process_type="local",
                                    working_dir=working_dir,
                                    build_system=buildsys)

    @classmethod
    def _build_package(cls, name, version=None):
        # create the builder
        working_dir = os.path.join(cls.src_root, name)
        if version:
            working_dir = os.path.join(working_dir, version)
        builder = cls._create_builder(working_dir)

        builder.build(install_path=cls.install_root, install=True, clean=True)

    def _reset_dest_repository(self):
        system.clear_caches()
        if os.path.exists(self.dest_install_root):
            shutil.rmtree(self.dest_install_root)

        os.makedirs(self.dest_install_root)

    def _get_src_pkg(self, name, version):
        return get_latest_package(
            name,
            range_=VersionRange("==" + version),
            paths=[self.install_root],
            error=True
        )

    def _get_dest_pkg(self, name, version):
        return get_latest_package(
            name,
            range_=VersionRange("==" + version),
            paths=[self.dest_install_root],
            error=True
        )

    def _assert_copied(self, result, copied, skipped):
        self.assertEqual(len(result["copied"]), copied)
        self.assertEqual(len(result["skipped"]), skipped)

    def test_1(self):
        """Simple package copy, no variants, no overwrite."""
        self._reset_dest_repository()

        # make a copy of a package
        src_pkg = self._get_src_pkg("floob", "1.2.0")
        result = copy_package(
            package=src_pkg,
            dest_repository=self.dest_install_root
        )

        self._assert_copied(result, 1, 0)

        # check the copied package exists and matches
        dest_pkg = self._get_dest_pkg("floob", "1.2.0")
        result_variant = result["copied"][0][1]
        dest_variant = next(dest_pkg.iter_variants())
        self.assertEqual(dest_variant.handle, result_variant.handle)

        pyfile = os.path.join(dest_pkg.base, "python", "floob", "__init__.py")
        ctime = os.stat(pyfile).st_ctime

        # copy again but with overwrite=False; should do nothing
        result = copy_package(
            package=src_pkg,
            dest_repository=self.dest_install_root
        )

        self._assert_copied(result, 0, 1)

        # check that package payload wasn't overwritten
        self.assertEqual(os.stat(pyfile).st_ctime, ctime)

    def test_2(self):
        """Package copy, no variants, overwrite."""
        self._reset_dest_repository()

        # make a copy of a package
        src_pkg = self._get_src_pkg("floob", "1.2.0")
        copy_package(
            package=src_pkg,
            dest_repository=self.dest_install_root
        )

        dest_pkg = self._get_dest_pkg("floob", "1.2.0")

        pyfile = os.path.join(dest_pkg.base, "python", "floob", "__init__.py")
        ctime = os.stat(pyfile).st_ctime

        # overwrite same package copy
        result = copy_package(
            package=src_pkg,
            dest_repository=self.dest_install_root,
            overwrite=True
        )

        self._assert_copied(result, 1, 0)

        # check that package payload was overwritten
        self.assertNotEqual(os.stat(pyfile).st_ctime, ctime)

    def test_3(self):
        """Package copy, variants, overwrite and non-overwrite."""
        self._reset_dest_repository()

        # make a copy of a varianted package
        src_pkg = self._get_src_pkg("bah", "2.1")
        result = copy_package(
            package=src_pkg,
            dest_repository=self.dest_install_root
        )

        self._assert_copied(result, 2, 0)  # 2 variants

        # check the copied variants exist and match
        dest_pkg = self._get_dest_pkg("bah", "2.1")
        ctimes = []

        for index in (0, 1):
            result_variant = result["copied"][index][1]
            dest_variant = dest_pkg.get_variant(index)
            self.assertEqual(dest_variant.handle, result_variant.handle)

            pyfile = os.path.join(dest_variant.root, "python", "bah", "__init__.py")
            ctime = os.stat(pyfile).st_ctime
            ctimes.append(ctime)

        # copy variant with no overwrite, should do nothing
        result = copy_package(
            package=src_pkg,
            dest_repository=self.dest_install_root,
            variants=[1]
        )

        self._assert_copied(result, 0, 1)

        # copy variant with overwrite
        result = copy_package(
            package=src_pkg,
            dest_repository=self.dest_install_root,
            variants=[1],
            overwrite=True
        )

        self._assert_copied(result, 1, 0)

        # check copied variant is the one we expect
        dest_pkg = self._get_dest_pkg("bah", "2.1")
        result_variant = result["copied"][0][1]
        dest_variant = dest_pkg.get_variant(1)
        self.assertEqual(dest_variant.handle, result_variant.handle)

        # check copied variant payload was overwritten
        pyfile = os.path.join(dest_variant.root, "python", "bah", "__init__.py")
        self.assertNotEqual(os.stat(pyfile).st_ctime, ctimes[1])

        # check non-copied variant payload was not written
        skipped_variant = dest_pkg.get_variant(0)
        pyfile = os.path.join(skipped_variant.root, "python", "bah", "__init__.py")
        self.assertEqual(os.stat(pyfile).st_ctime, ctimes[0])

    def test_4(self):
        """Package copy with rename, reversion."""
        self._reset_dest_repository()

        # copy a package to a different name and version
        src_pkg = self._get_src_pkg("floob", "1.2.0")
        result = copy_package(
            package=src_pkg,
            dest_repository=self.dest_install_root,
            dest_name="flaab",
            dest_version="5.4.1"
        )

        self._assert_copied(result, 1, 0)

        # check copied variant is the one we expect
        dest_pkg = self._get_dest_pkg("flaab", "5.4.1")
        result_variant = result["copied"][0][1]
        dest_variant = next(dest_pkg.iter_variants())
        self.assertEqual(dest_variant.handle, result_variant.handle)

    def test_5(self):
        """Package copy with standard, new timestamp."""
        self._reset_dest_repository()

        # wait 1 second to guarantee newer timestamp in copied pkg
        time.sleep(1)

        # copy package and overwrite timestamp
        src_pkg = self._get_src_pkg("floob", "1.2.0")
        copy_package(
            package=src_pkg,
            dest_repository=self.dest_install_root
        )

        # check copied variant contains expected timestamp
        dest_pkg = self._get_dest_pkg("floob", "1.2.0")
        self.assertTrue(dest_pkg.timestamp > src_pkg.timestamp)

    def test_6(self):
        """Package copy with keep_timestamp."""
        self._reset_dest_repository()

        # wait 1 second to ensure we don't just accidentally get same timestamp
        time.sleep(1)

        # copy package and overwrite timestamp
        src_pkg = self._get_src_pkg("floob", "1.2.0")
        copy_package(
            package=src_pkg,
            dest_repository=self.dest_install_root,
            keep_timestamp=True
        )

        # check copied variant contains expected timestamp
        dest_pkg = self._get_dest_pkg("floob", "1.2.0")
        self.assertEqual(dest_pkg.timestamp, src_pkg.timestamp)

    def test_7(self):
        """Package copy with overrides."""
        self._reset_dest_repository()

        overrides = {
            "timestamp": 10000,
            "description": "this is a copy",
            "some_extra_key": True
        }

        # copy package and overwrite timestamp
        src_pkg = self._get_src_pkg("floob", "1.2.0")
        copy_package(
            package=src_pkg,
            dest_repository=self.dest_install_root,
            overrides=overrides
        )

        # check copied variant contains expected timestamp
        dest_pkg = self._get_dest_pkg("floob", "1.2.0")

        for k, v in list(overrides.items()):
            self.assertEqual(getattr(dest_pkg, k), v)

    def test_8(self):
        """Ensure that include modules are copied."""
        self._reset_dest_repository()

        src_pkg = self._get_src_pkg("foo", "1.1.0")
        copy_package(
            package=src_pkg,
            dest_repository=self.dest_install_root,
        )

        dest_pkg = self._get_dest_pkg("foo", "1.1.0")
        dest_variant = next(dest_pkg.iter_variants())

        # do a resolve
        ctxt = ResolvedContext(
            ["foo==1.1.0"],
            package_paths=[self.dest_install_root, self.install_root]
        )

        resolved_variant = ctxt.get_resolved_package("foo")
        self.assertEqual(dest_variant.handle, resolved_variant.handle)

        # this can only match if the include module was copied with the package
        environ = ctxt.get_environ(parent_environ={})
        self.assertEqual(environ.get("EEK"), "2")
