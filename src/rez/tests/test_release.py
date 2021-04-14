"""
test the release system
"""
from rez.build_process import create_build_process
from rez.build_system import create_build_system
from rez.resolved_context import ResolvedContext
from rez.release_vcs import create_release_vcs
from rez.packages import iter_packages
from rez.vendor import yaml
from rez.system import system
from rez.exceptions import ReleaseError, ReleaseVCSError
import unittest
from rez.tests.util import TestBase, TempdirMixin, per_available_shell, \
    install_dependent
from rez.package_serialise import dump_package_data
from rez.serialise import FileFormat
import shutil
import os.path


class TestRelease(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls):
        TempdirMixin.setUpClass()

        cls.src_path = cls.data_path("release")
        cls.src_root = os.path.join(cls.root, "src")
        cls.install_root = os.path.join(cls.root, "packages")

        cls.settings = dict(
            packages_path=[cls.install_root],
            package_filter=None,
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

    def _setup_release(self):
        # start fresh
        system.clear_caches()
        if os.path.exists(self.install_root):
            shutil.rmtree(self.install_root)
        if os.path.exists(self.src_root):
            shutil.rmtree(self.src_root)
        shutil.copytree(self.src_path, self.src_root)

        self.packagefile = os.path.join(self.src_root, "package.yaml")
        with open(self.packagefile) as f:
            self.package_data = yaml.load(f.read(), Loader=yaml.FullLoader)

        # check build system type
        buildsys = create_build_system(self.src_root, verbose=True)
        self.assertEqual(buildsys.name(), "custom")

        # create the vcs - should error because stub file doesn't exist yet
        with self.assertRaises(ReleaseVCSError):
            create_release_vcs(self.src_root)

        # make the stub file
        self.stubfile = os.path.join(self.src_root, ".stub")
        with open(self.stubfile, 'w'):
            pass

        # create the vcs - should work now
        self.vcs = create_release_vcs(self.src_root)
        self.assertEqual(self.vcs.name(), "stub")

    def _write_package(self):
        with open(self.packagefile, 'w') as f:
            dump_package_data(self.package_data, f, format_=FileFormat.yaml)

    def _create_builder(self, ensure_latest=True):
        buildsys = create_build_system(self.src_root, verbose=True)

        return create_build_process(process_type="local",
                                    working_dir=self.src_root,
                                    build_system=buildsys,
                                    vcs=self.vcs,
                                    ensure_latest=ensure_latest,
                                    ignore_existing_tag=True,
                                    verbose=True)

    def assertVariantsEqual(self, vars1, vars2):
        """Utility function to compare string-variants with formal lists of
        "PackageRequest" objects
        """
        def _standardize_variants(variants):
            return [list(str(req) for req in variant) for variant in variants]

        self.assertEqual(_standardize_variants(vars1),
                         _standardize_variants(vars2))

    @per_available_shell()
    @install_dependent()
    def test_1(self):
        """Basic release."""
        # release should fail because release path does not exist
        self._setup_release()
        builder = self._create_builder()
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
        builder = self._create_builder()
        num_variants = builder.release()
        self.assertEqual(num_variants, 0)

        # update package version and release again
        self.package_data["version"] = "1.1"
        self._write_package()
        builder = self._create_builder()
        builder.release()

        # change version to earlier and do failed release attempt
        self.package_data["version"] = "1.0.1"
        self._write_package()
        builder = self._create_builder()
        with self.assertRaises(ReleaseError):
            builder.release()

        # release again, this time allow not latest
        builder = self._create_builder(ensure_latest=False)
        builder.release()

        # change uuid and do failed release attempt
        self.package_data["version"] = "1.2"
        self.package_data["uuid"] += "_CHANGED"
        self._write_package()
        builder = self._create_builder()
        with self.assertRaises(ReleaseError):
            builder.release()

        # check the vcs contains the tags we expect
        expected_value = set(["foo-1.0", "foo-1.0.1", "foo-1.1"])
        with open(self.stubfile) as f:
            stub_data = yaml.load(f.read(), Loader=yaml.FullLoader)
        tags = set(stub_data.get("tags", {}).keys())
        self.assertEqual(tags, expected_value)

        # check the package install path contains the packages we expect
        it = iter_packages("foo", paths=[self.install_root])
        qnames = set(x.qualified_name for x in it)
        self.assertEqual(qnames, expected_value)

    @per_available_shell()
    @install_dependent()
    def test_2_variant_add(self):
        """Test variant installation on release
        """
        orig_src_path = self.src_path
        self.src_path = os.path.join(self.src_path, "variants")
        try:
            self._setup_release()
        finally:
            # due to per_available_shell, this will run multiple times, don't
            # want to add src_path/variants/variants
            self.src_path = orig_src_path

        # copy the spangle package onto the packages path
        os.mkdir(self.install_root)
        shutil.copytree(os.path.join(self.src_root, 'spangle'),
                        os.path.join(self.install_root, 'spangle'))

        # release the bar package, which has spangle-1.0 and 1.1 variants
        builder = self._create_builder()
        builder.release()

        # check that the released package has two variants, and the "old"
        # description...
        rel_packages = list(iter_packages("bar", paths=[self.install_root]))
        self.assertEqual(len(rel_packages), 1)
        rel_package = rel_packages[0]
        self.assertVariantsEqual(rel_package.variants, [['spangle-1.0'],
                                                        ['spangle-1.1']])
        self.assertEqual(rel_package.description,
                         'a package with two variants')

        # now, change the package so it has a single spangle-2.0 variant...
        self.package_data['variants'] = [['spangle-2.0']]
        new_desc = 'added spangle-2.0 variant'
        self.package_data['description'] = new_desc
        self._write_package()

        # ...then try to re-release
        builder = self._create_builder()
        builder.release()

        # check that the released package now three variants, and the "new"
        # description...
        rel_packages = list(iter_packages("bar", paths=[self.install_root]))
        self.assertEqual(len(rel_packages), 1)
        rel_package = rel_packages[0]
        self.assertVariantsEqual(rel_package.variants, [['spangle-1.0'],
                                                        ['spangle-1.1'],
                                                        ['spangle-2.0']])
        self.assertEqual(rel_package.description, new_desc)

        # finally, release a package that contains a variant already released,
        # but with a different index...
        self.package_data['variants'] = [['spangle-1.1']]
        third_desc = 'releasing with already existing variant'
        self.package_data['description'] = third_desc
        self._write_package()
        builder = self._create_builder()
        builder.release()

        # make sure that the variant indices stayed the same...
        rel_packages = list(iter_packages("bar", paths=[self.install_root]))
        self.assertEqual(len(rel_packages), 1)
        rel_package = rel_packages[0]
        self.assertVariantsEqual(rel_package.variants, [['spangle-1.0'],
                                                        ['spangle-1.1'],
                                                        ['spangle-2.0']])
        # ...but that the description was updated
        self.assertEqual(rel_package.description, third_desc)


if __name__ == '__main__':
    unittest.main()


# Copyright 2013-2016 Allan Johns.
#
# This library is free software: you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.
