from rez.build_process_ import create_build_process
from rez.build_system import create_build_system
from rez.resolved_context import ResolvedContext
from rez.release_vcs import create_release_vcs
from rez.packages_ import iter_packages
from rez.vendor import yaml
from rez.system import system
from rez.exceptions import ReleaseError, ReleaseVCSError
import rez.vendor.unittest2 as unittest
from rez.tests.util import TestBase, TempdirMixin, shell_dependent, \
    install_dependent
from rez.package_serialise import dump_package_data
from rez.serialise import FileFormat
import shutil
import os.path
from rez.config import config


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
            resolve_caching=False,
            warn_untimestamped=False,
            implicit_packages=[])

    @classmethod
    def tearDownClass(cls):
        TempdirMixin.tearDownClass()

    @classmethod
    def _create_context(cls, *pkgs):
        return ResolvedContext(pkgs)

    @shell_dependent
    @install_dependent
    def test_1(self):
        """Basic release."""
        src_path = os.path.join(self.src_path, 'one_dot_zero')

        # start fresh
        system.clear_caches()
        if os.path.exists(self.install_root):
            shutil.rmtree(self.install_root)
        if os.path.exists(self.src_root):
            shutil.rmtree(self.src_root)
        shutil.copytree(src_path, self.src_root)

        working_dir = self.src_root
        packagefile = os.path.join(working_dir, "package.yaml")
        with open(packagefile) as f:
            package_data = yaml.load(f.read())

        def _write_package():
            with open(packagefile, 'w') as f:
                dump_package_data(package_data, f, format_=FileFormat.yaml)

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
            return create_build_process(process_type="local",
                                        working_dir=working_dir,
                                        build_system=buildsys,
                                        vcs=vcs,
                                        ensure_latest=ensure_latest,
                                        verbose=True)

        # release should fail because release path does not exist
        builder = _create_builder()
        with self.assertRaises(ReleaseError):
            builder.release()

        # release should work this time
        os.mkdir(self.install_root)
        builder.release()

        # check a file to see the release made it
        filepath = os.path.join(self.install_root,
                                "foo", "1.0", "data", "data.txt")
        self.assertTrue(os.path.exists(filepath))

        # failed release (same version released again)
        builder = _create_builder()
        num_variants = builder.release()
        self.assertEqual(num_variants, 0)

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
        it = iter_packages("foo", paths=[self.install_root])
        qnames = set(x.qualified_name for x in it)
        self.assertEqual(qnames, expected_value)

    def test_2(self):
        """exclude/include release."""
        src_path = os.path.join(self.src_path, 'one_dot_zero_beta')
        # start fresh
        system.clear_caches()
        if os.path.exists(self.install_root):
            shutil.rmtree(self.install_root)
        if os.path.exists(self.src_root):
            shutil.rmtree(self.src_root)
        shutil.copytree(src_path, self.src_root)

        working_dir = self.src_root

        packagefile = os.path.join(working_dir, "package.yaml")
        with open(packagefile) as f:
            package_data = yaml.load(f.read())

        def _write_package():
            with open(packagefile, 'w') as f:
                dump_package_data(package_data, f, format_=FileFormat.yaml)

        # create the build system
        buildsys = create_build_system(working_dir, verbose=True)

        stubfile = os.path.join(working_dir, ".stub")
        with open(stubfile, 'w'):
            pass
        vcs = create_release_vcs(working_dir)

        def _create_builder(ensure_latest=True):
            return create_build_process(process_type="local",
                                        working_dir=working_dir,
                                        build_system=buildsys,
                                        vcs=vcs,
                                        ensure_latest=ensure_latest,
                                        verbose=True)

        config.override("exclude_packages", ['foo-*beta'])
        config.override("include_packages", ['2*beta'])

        os.mkdir(self.install_root)
        builder = _create_builder()
        builder.release()
        # check a file to see the release made it
        filepath = os.path.join(self.install_root,
                                "foo", "1.0-beta", "data", "data.txt")
        self.assertTrue(os.path.exists(filepath))

        # update package version and release again
        package_data["version"] = "2.1-beta"
        _write_package()
        builder = _create_builder()
        builder.release()

        # update package version and release again
        package_data["version"] = "3.1-beta"
        _write_package()
        builder = _create_builder()
        builder.release()

        # check the vcs contains the tags we expect
        expected_value = set(["foo-1.0-beta", "foo-2.1-beta", "foo-3.1-beta"])
        with open(stubfile) as f:
            stub_data = yaml.load(f.read())
        tags = set(stub_data.get("tags", {}).keys())
        self.assertEqual(tags, expected_value)

        # skip package masking so that all packages are visible
        # effectively exclude/include is skipped
        it = iter_packages("foo", paths=[self.install_root], skip_masking=True)
        qnames = set(x.qualified_name for x in it)
        self.assertEqual(qnames, expected_value)

        expected_visible_value = set(["foo-2.1-beta"])
        # check that the only visible foo package matches '2*beta'
        it = iter_packages("foo", paths=[self.install_root])
        qnames = set(x.qualified_name for x in it)
        self.assertEqual(qnames, expected_visible_value)


def get_test_suites():
    suites = []
    suite = unittest.TestSuite()
    suite.addTest(TestRelease("test_1"))
    suite.addTest(TestRelease("test_2"))
    suites.append(suite)
    return suites


if __name__ == '__main__':
    unittest.main()
