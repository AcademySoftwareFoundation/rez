"""
test package iteration, serialization etc
"""
from rez.packages import iter_package_families, iter_packages, get_package, \
    create_package, get_developer_package, get_variant_from_uri
from rez.package_py_utils import expand_requirement
from rez.package_resources import package_release_keys
from rez.tests.util import TestBase, TempdirMixin
from rez.utils.formatting import PackageRequest
from rez.utils.sourcecode import SourceCode
import unittest
from rez.vendor.version.version import Version
from rez.vendor.version.util import VersionError
from rez.utils.filesystem import canonical_path
import os.path
import os


ALL_PACKAGES = set([
    # packages from data/solver
    'bahish-1', 'bahish-2',
    'nada',
    'nopy-2.1',
    'pybah-4', 'pybah-5',
    'pydad-1', 'pydad-2', 'pydad-3',
    'pyfoo-3.0.0', 'pyfoo-3.1.0',
    'pymum-1', 'pymum-2', 'pymum-3',
    'pyodd-1', 'pyodd-2',
    'pyson-1', 'pyson-2',
    'pysplit-5', 'pysplit-6', 'pysplit-7',
    'python-2.5.2', 'python-2.6.0', 'python-2.6.8', 'python-2.7.0',
    'pyvariants-2',
    'test_variant_split_start-1.0', 'test_variant_split_start-2.0',
    'test_variant_split_mid1-1.0', 'test_variant_split_mid1-2.0',
    'test_variant_split_mid2-1.0', 'test_variant_split_mid2-2.0',
    'test_variant_split_end-1.0', 'test_variant_split_end-2.0',
    'test_variant_split_end-3.0', 'test_variant_split_end-4.0',
    # packages from data/packages/py_packages and .../yaml_packages
    'unversioned',
    'unversioned_py',
    'versioned-1.0', 'versioned-2.0', 'versioned-3.0',
    'variants_py-2.0',
    'single_unversioned',
    'single_versioned-3.5',
    'late_binding-1.0',
    'timestamped-1.0.5', 'timestamped-1.0.6', 'timestamped-1.1.0', 'timestamped-1.1.1',
    'timestamped-1.2.0', 'timestamped-2.0.0', 'timestamped-2.1.0', 'timestamped-2.1.5',
    'multi-1.0', 'multi-1.1', 'multi-1.2', 'multi-2.0'])


ALL_FAMILIES = set(x.split('-')[0] for x in ALL_PACKAGES)


def _to_names(it):
    return set(p.name for p in it)


def _to_qnames(it):
    return set(p.qualified_name for p in it)


class TestPackages(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls):
        TempdirMixin.setUpClass()

        cls.solver_packages_path = cls.data_path("solver", "packages")
        cls.packages_base_path = cls.data_path("packages")
        cls.yaml_packages_path = os.path.join(cls.packages_base_path, "yaml_packages")
        cls.py_packages_path = os.path.join(cls.packages_base_path, "py_packages")

        cls.package_definition_build_python_paths = [
            cls.data_path("python", "early_bind"),
            cls.data_path("python", "preprocess")
        ]

        cls.settings = dict(
            packages_path=[cls.solver_packages_path,
                           cls.yaml_packages_path,
                           cls.py_packages_path],
            package_definition_build_python_paths=cls.package_definition_build_python_paths,
            package_filter=None)

    @classmethod
    def tearDownClass(cls):
        TempdirMixin.tearDownClass()

    def test_1(self):
        """package family iteration."""
        all_fams = _to_names(iter_package_families())
        self.assertEqual(all_fams, ALL_FAMILIES)

    def test_2(self):
        """package iteration."""
        all_packages = set()
        all_fams = iter_package_families()
        for fam in all_fams:
            packages = _to_qnames(iter_packages(fam.name))
            all_packages.update(packages)
        self.assertEqual(all_packages, ALL_PACKAGES)

        res = _to_qnames(iter_packages('nada'))
        self.assertEqual(res, set(['nada']))

        res = _to_qnames(iter_packages('python'))
        self.assertEqual(res, set(['python-2.5.2', 'python-2.6.0',
                                   'python-2.6.8', 'python-2.7.0']))

        res = _to_qnames(iter_packages('pydad', "<3"))
        self.assertEqual(res, set(['pydad-1', 'pydad-2']))

        for fam_name in ALL_FAMILIES:
            for package in iter_packages(fam_name):
                family = package.parent
                self.assertEqual(family.name, fam_name)
                it = family.iter_packages()
                self.assertTrue(package in it)

    def test_3(self):
        """check package contents."""
        # a py-based package
        package = get_package("versioned", "3.0")
        expected_data = dict(
            name="versioned",
            version=Version("3.0"),
            base=canonical_path(os.path.join(self.py_packages_path, "versioned", "3.0")),
            commands=SourceCode('env.PATH.append("{root}/bin")'))
        data = package.validated_data()
        self.assertDictEqual(data, expected_data)

        # a yaml-based package
        package = get_package("versioned", "2.0")
        expected_uri = canonical_path(os.path.join(self.yaml_packages_path,
                                            "versioned", "2.0", "package.yaml"))
        self.assertEqual(package.uri, expected_uri)

        # a py-based package with late binding attribute functions
        package = get_package("late_binding", "1.0")
        self.assertEqual(package.tools, ["util"])

        # a 'combined' type package
        package = get_package("multi", "1.0")
        expected_uri = canonical_path(os.path.join(self.yaml_packages_path, "multi.yaml<1.0>"))
        self.assertEqual(package.uri, expected_uri)
        expected_data = dict(
            name="multi",
            version=Version("1.0"),
            tools=["tweak"])
        data = package.validated_data()
        self.assertDictEqual(data, expected_data)

        # a 'combined' type package, with version overrides
        package = get_package("multi", "1.1")
        expected_uri = canonical_path(os.path.join(self.yaml_packages_path, "multi.yaml<1.1>"))
        self.assertEqual(package.uri, expected_uri)
        expected_data = dict(
            name="multi",
            version=Version("1.1"),
            tools=["twerk"])
        data = package.validated_data()
        self.assertDictEqual(data, expected_data)

        # check that visibility of 'combined' packages is correct
        package = get_package("multi", "2.0")
        expected_uri = canonical_path(os.path.join(self.py_packages_path, "multi.py<2.0>"))
        self.assertEqual(package.uri, expected_uri)

    def test_4(self):
        """test package creation."""
        package_data = {
            "name":             "foo",
            "version":          "1.0.0",
            "description":      "something foo-like",
            "requires":         ["python-2.6+"]}

        package = create_package("foo", package_data)
        self.assertEqual(package.version, Version("1.0.0"))
        self.assertEqual(package.description, "something foo-like")
        self.assertEqual(package.requires, [PackageRequest("python-2.6+")])

        family = package.parent
        self.assertEqual(family.name, package.name)
        packages = list(family.iter_packages())
        self.assertEqual(len(packages), 1)
        self.assertEqual(package, packages[0])

    def test_developer(self):
        """test developer package."""
        path = os.path.join(self.packages_base_path, "developer")
        package = get_developer_package(path)
        expected_data = dict(
            name="foo",
            version=Version("3.0.1"),
            description="a foo type thing.",
            authors=["joe.bloggs"],
            requires=[PackageRequest('bah-1.2+<2')],
            variants=[[PackageRequest('floob-4.1')],
                      [PackageRequest('floob-2.0')]],
            uuid="28d94bcd1a934bb4999bcf70a21106cc")
        data = package.validated_data()
        self.assertDictEqual(data, expected_data)

    def test_developer_dynamic_local_preprocess(self):
        """test developer package with a local preprocess function"""
        # a developer package with features such as expanding requirements,
        # early-binding attribute functions, and preprocessing

        # Here we will also verifies that the local preprocess function wins over
        # the global one.
        self.update_settings(
            {
                "package_preprocess_function": "global_preprocess.inject_data"
            }
        )

        path = os.path.join(self.packages_base_path, "developer_dynamic_local_preprocess")
        package = get_developer_package(path)

        self.assertEqual(package.description, "This.")
        self.assertEqual(package.requires, [PackageRequest('versioned-3')])
        self.assertEqual(package.authors, ["tweedle-dee", "tweedle-dum"])
        self.assertFalse(hasattr(package, "added_by_global_preprocess"))
        self.assertEqual(package.added_by_local_preprocess, True)

    def test_developer_dynamic_global_preprocess_string(self):
        """test developer package with a global preprocess function as string"""
        # a developer package with features such as expanding requirements,
        # global preprocessing
        self.update_settings(
            {
                "package_preprocess_function": "global_preprocess.inject_data"
            }
        )

        path = os.path.join(self.packages_base_path, "developer_dynamic_global_preprocess")
        package = get_developer_package(path)

        self.assertEqual(package.description, "This.")
        self.assertEqual(package.added_by_global_preprocess, True)

    def test_developer_dynamic_global_preprocess_func(self):
        """test developer package with a global preprocess function as function"""
        # a developer package with features such as expanding requirements,
        # global preprocessing
        def preprocess(this, data):
            data["dynamic_attribute_added"] = {'test': True}

        self.update_settings(
            {
                "package_preprocess_function": preprocess
            }
        )

        path = os.path.join(self.packages_base_path, "developer_dynamic_global_preprocess")
        package = get_developer_package(path)

        self.assertEqual(package.description, "This.")
        self.assertEqual(package.dynamic_attribute_added, {'test': True})

    def test_developer_dynamic_before(self):
        """test developer package with both global and local preprocess in before mode"""
        # a developer package with features such as expanding requirements,
        # global preprocessing
        def preprocess(this, data):
            data["dynamic_attribute_added"] = {'value_set_by': 'global'}
            data["added_by_global_preprocess"] = True

        self.update_settings(
            {
                "package_preprocess_function": preprocess,
                "package_preprocess_mode": "before"
            }
        )

        path = os.path.join(self.packages_base_path, "developer_dynamic_local_preprocess_additive")
        package = get_developer_package(path)

        self.assertEqual(package.description, "This.")
        self.assertEqual(package.authors, ["tweedle-dee", "tweedle-dum"])
        self.assertEqual(package.dynamic_attribute_added, {'value_set_by': 'global'})
        self.assertEqual(package.added_by_global_preprocess, True)
        self.assertEqual(package.added_by_local_preprocess, True)

    def test_developer_dynamic_after(self):
        """test developer package with both global and local preprocess in after mode"""
        # a developer package with features such as expanding requirements,
        # global preprocessing
        def preprocess(this, data):
            data["dynamic_attribute_added"] = {'value_set_by': 'global'}
            data["added_by_global_preprocess"] = True

        self.update_settings(
            {
                "package_preprocess_function": preprocess,
                "package_preprocess_mode": "after"
            }
        )

        path = os.path.join(self.packages_base_path, "developer_dynamic_local_preprocess_additive")
        package = get_developer_package(path)

        self.assertEqual(package.description, "This.")
        self.assertEqual(package.authors, ["tweedle-dee", "tweedle-dum"])
        self.assertEqual(package.dynamic_attribute_added, {'value_set_by': 'local'})
        self.assertEqual(package.added_by_global_preprocess, True)
        self.assertEqual(package.added_by_local_preprocess, True)

    def test_6(self):
        """test variant iteration."""
        base = canonical_path(os.path.join(self.py_packages_path, "variants_py", "2.0"))
        expected_data = dict(
            name="variants_py",
            version=Version("2.0"),
            description="package with variants",
            base=base,
            requires=[PackageRequest("python-2.7")],
            commands=SourceCode('env.PATH.append("{root}/bin")'))

        requires_ = ["platform-linux", "platform-osx"]

        package = get_package("variants_py", "2.0")
        for i, variant in enumerate(package.iter_variants()):
            data = variant.validated_data()
            self.assertDictEqual(data, expected_data)
            self.assertEqual(variant.index, i)
            self.assertEqual(variant.parent, package)

    def test_7(self):
        """test variant installation."""
        repo_path = os.path.join(self.root, "packages")
        if not os.path.exists(repo_path):
            os.makedirs(repo_path)

        def _data(obj):
            d = obj.validated_data()
            keys = package_release_keys + ("base",)
            for key in keys:
                d.pop(key, None)
            return d

        # package with variants and package without
        dev_pkgs_list = (("developer", "developer_changed"),
                         ("developer_novar", "developer_novar_changed"))

        for path1, path2 in dev_pkgs_list:
            path = os.path.join(self.packages_base_path, path1)
            package = get_developer_package(path)

            # install variants of the developer package into new repo
            variant = next(package.iter_variants())
            result = variant.install(repo_path, dry_run=True)
            self.assertEqual(result, None)

            for variant in package.iter_variants():
                variant.install(repo_path)

            variant = next(package.iter_variants())
            result = variant.install(repo_path, dry_run=True)
            self.assertNotEqual(result, None)

            # now there should be a package that matches the dev package
            installed_package = get_package(package.name, package.version, paths=[repo_path])
            data = _data(package)
            data_ = _data(installed_package)
            self.assertDictEqual(data, data_)

            # make a change in the dev pkg, outside of the variants.
            path = os.path.join(self.packages_base_path, path2)
            package = get_developer_package(path)

            # install a variant again. Even though the variant is already installed,
            # this should update the package, because data outside the variant changed.
            variant = next(package.iter_variants())
            result = variant.install(repo_path, dry_run=True)
            self.assertEqual(result, None)
            variant.install(repo_path)

            # check that the change was applied. This effectively also checks that the
            # variant order hasn't changed.
            installed_package = get_package(package.name, package.version, paths=[repo_path])
            data = _data(package)
            data_ = _data(installed_package)
            self.assertDictEqual(data, data_)

    def test_8(self):
        """test expand_requirement function."""
        tests = (
            ("pyfoo", "pyfoo"),
            ("pyfoo-3", "pyfoo-3"),
            ("pyfoo-3.0", "pyfoo-3.0"),
            ("pyfoo-*", "pyfoo-3"),
            ("pyfoo-**", "pyfoo-3.1.0"),
            ("pysplit==**", "pysplit==7"),
            ("python-*+<**", "python-2+<2.7.0"),
            ("python-2.6.*+<**", "python-2.6.8+<2.7.0"),
            ("python-2.5|**", "python-2.5|2.7.0"),
            ("notexist-1.2.3", "notexist-1.2.3"),
            ("pysplit-6.*", "pysplit-6"),
            ("pyfoo-3.0.0.**", "pyfoo-3.0.0"),
            ("python-55", "python-55"),

            # some trickier cases, VersionRange construction rules still apply
            ("python-**|2.5", "python-2.5|2.7.0"),
            ("python-2.*|**", "python-2.7")
        )

        bad_tests = (
            "python-*.**",
            "python-1.*.**",
            "python-1.*.1",
            "python-1.v*",
            "python-1.**.*",
            "python-1.**.1"
        )

        for req, expanded_req in tests:
            result = expand_requirement(req)
            self.assertEqual(result, expanded_req)

        for req in bad_tests:
            self.assertRaises(VersionError, expand_requirement, req)

    def test_variant_from_uri(self):
        """Test getting a variant from its uri."""
        package = get_package("variants_py", "2.0")
        for variant in package.iter_variants():
            variant2 = get_variant_from_uri(variant.uri)
            self.assertEqual(variant, variant2)


class TestMemoryPackages(TestBase):
    def test_1_memory_variant_parent(self):
        """Test that a package's variant's parent is the original package
        """
        desc = 'the foo package'
        package = create_package('foo', {'description': desc})
        self.assertEqual(package.description, desc)
        variant = next(package.iter_variants())
        parent_package = variant.parent
        self.assertEqual(package.description, desc)


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
