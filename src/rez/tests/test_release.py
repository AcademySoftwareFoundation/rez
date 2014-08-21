from rez.build_process import LocalSequentialBuildProcess
from rez.build_system import create_build_system
from rez.resolved_context import ResolvedContext
from rez.release_vcs import create_release_vcs
from rez.packages import iter_packages
from rez.vendor import yaml
from rez.exceptions import BuildError, ReleaseError, ReleaseVCSError
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
        cls.src_path = os.path.join(path, "data", "release")
        cls.src_root = os.path.join(cls.root, "src")
        cls.install_root = os.path.join(cls.root, "packages")

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

    @classmethod
    def _create_context(cls, *pkgs):
        # cache clear is needed to clear Resource._listdir cache, which hides
        # newly added packages
        clear_caches()
        return ResolvedContext(pkgs)

    @shell_dependent
    @install_dependent
    def test_1(self):
        """Basic release."""

        # start fresh
        clear_caches()
        if os.path.exists(self.install_root):
            shutil.rmtree(self.install_root)
        if os.path.exists(self.src_root):
            shutil.rmtree(self.src_root)
        shutil.copytree(self.src_path, self.src_root)

        working_dir = self.src_root
        packagefile = os.path.join(working_dir, "package.yaml")
        with open(packagefile) as f:
            package_data = yaml.load(f.read())

        def _write_package():
            with open(packagefile, 'w') as f:
                f.write(yaml.dump(package_data))
            clear_caches()

        # create the build system
        buildsys = create_build_system(working_dir, verbose=True)
        self.assertEqual(buildsys.name(), "bez")

        # create the vcs
        with self.assertRaises(ReleaseVCSError):
            vcs = create_release_vcs(working_dir)

        stubfile = os.path.join(working_dir, ".stub")
        with open(stubfile, 'w'):
            pass
        vcs = create_release_vcs(working_dir)
        self.assertEqual(vcs.name(), "stub")

        def _create_builder(ensure_latest=True):
            return LocalSequentialBuildProcess(working_dir,
                                               buildsys=buildsys,
                                               vcs=vcs,
                                               ensure_latest=ensure_latest)

        # do a release
        builder = _create_builder()
        with self.assertRaises(ReleaseError):
            builder.release()

        os.mkdir(self.install_root)
        builder.release()

        # check a file to see the release made it
        filepath = os.path.join(self.install_root,
                                "foo", "1.0", "data", "data.txt")
        self.assertTrue(os.path.exists(filepath))

        # failed release (same version release again)
        clear_caches()
        builder = _create_builder()
        with self.assertRaises(ReleaseError):
            builder.release()

        # update package version and release again
        package_data["version"] = "1.1"
        _write_package()
        builder = _create_builder()
        builder.release()

        # change version to earlier and do failed release attempt
        package_data["version"] = "1.0.1"
        _write_package()
        builder = _create_builder()
        with self.assertRaises(ReleaseError):
            builder.release()

        # release again, this time allow not latest
        builder = _create_builder(ensure_latest=False)
        builder.release()

        # change uuid and do failed release attempt
        package_data["version"] = "1.2"
        package_data["uuid"] += "_CHANGED"
        _write_package()
        builder = _create_builder()
        with self.assertRaises(ReleaseError):
            builder.release()

        # check the vcs contains the tags we expect
        expected_value = set(["foo-1.0", "foo-1.0.1", "foo-1.1"])
        with open(stubfile) as f:
            stub_data = yaml.load(f.read())
        tags = set(stub_data.get("tags", {}).keys())
        self.assertEqual(tags, expected_value)

        # check the package install path contains the packages we expect
        clear_caches()
        it = iter_packages(paths=[self.install_root])
        qnames = set(x.qualified_name for x in it)
        self.assertEqual(qnames, expected_value)


def get_test_suites():
    suites = []
    suite = unittest.TestSuite()
    suite.addTest(TestRelease("test_1"))
    suites.append(suite)
    return suites


if __name__ == '__main__':
    unittest.main()
