"""
test package iteration, serialization etc
"""
from rez.packages_ import iter_package_families, iter_packages, get_package, \
    create_package, get_developer_package
from rez.package_resources_ import package_release_keys
from rez.package_repository import create_memory_package_repository
from rez.package_py_utils import expand_requirement
from rez.tests.util import TestBase, TempdirMixin
from rez.utils.formatting import PackageRequest
from rez.utils.sourcecode import SourceCode
import rez.vendor.unittest2 as unittest
from rez.vendor.version.version import Version
from rez.vendor.version.util import VersionError
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

        path = os.path.realpath(os.path.dirname(__file__))
        cls.solver_packages_path = os.path.join(path, "data", "solver", "packages")
        cls.packages_base_path = os.path.join(path, "data", "packages")
        cls.yaml_packages_path = os.path.join(cls.packages_base_path, "yaml_packages")
        cls.py_packages_path = os.path.join(cls.packages_base_path, "py_packages")

        cls.package_definition_build_python_paths = [
            os.path.join(path, "data", "python", "early_bind")
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
            base=os.path.join(self.py_packages_path, "versioned", "3.0"),
            commands=SourceCode('env.PATH.append("{root}/bin")'))
        data = package.validated_data()
        self.assertDictEqual(data, expected_data)

        # a yaml-based package
        package = get_package("versioned", "2.0")
        expected_uri = os.path.join(self.yaml_packages_path,
                                    "versioned", "2.0", "package.yaml")
        self.assertEqual(package.uri, expected_uri)

        # a py-based package with late binding attribute functions
        package = get_package("late_binding", "1.0")
        self.assertEqual(package.tools, ["util"])

        # a 'combined' type package
        package = get_package("multi", "1.0")
        expected_uri = os.path.join(self.yaml_packages_path, "multi.yaml<1.0>")
        self.assertEqual(package.uri, expected_uri)
        expected_data = dict(
            name="multi",
            version=Version("1.0"),
            tools=["tweak"])
        data = package.validated_data()
        self.assertDictEqual(data, expected_data)

        # a 'combined' type package, with version overrides
        package = get_package("multi", "1.1")
        expected_uri = os.path.join(self.yaml_packages_path, "multi.yaml<1.1>")
        self.assertEqual(package.uri, expected_uri)
        expected_data = dict(
            name="multi",
            version=Version("1.1"),
            tools=["twerk"])
        data = package.validated_data()
        self.assertDictEqual(data, expected_data)

        # check that visibility of 'combined' packages is correct
        package = get_package("multi", "2.0")
        expected_uri = os.path.join(self.py_packages_path, "multi.py<2.0>")
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

    def test_5(self):
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

        # a developer package with features such as expanding requirements,
        # early-binding attribute functions, and preprocessing
        path = os.path.join(self.packages_base_path, "developer_dynamic")
        package = get_developer_package(path)

        self.assertEqual(package.description, "This.")
        self.assertEqual(package.requires, [PackageRequest('versioned-3')])
        self.assertEqual(package.authors, ["tweedle-dee", "tweedle-dum"])

    def test_6(self):
        """test variant iteration."""
        expected_data = dict(
            name="variants_py",
            version=Version("2.0"),
            description="package with variants",
            base=os.path.join(self.py_packages_path, "variants_py", "2.0"),
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
            variant = package.iter_variants().next()
            result = variant.install(repo_path, dry_run=True)
            self.assertEqual(result, None)

            for variant in package.iter_variants():
                variant.install(repo_path)

            variant = package.iter_variants().next()
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
            variant = package.iter_variants().next()
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

    def test_9(self):
        """test package orderers."""
        from rez.package_order import NullPackageOrder, PerFamilyOrder, \
            VersionSplitPackageOrder, TimestampPackageOrder, SortedOrder, \
            to_pod, from_pod

        def _test(orderer, package_name, expected_order):
            it = iter_packages(package_name)
            descending = sorted(it, key=lambda x: x.version, reverse=True)

            pod = to_pod(orderer)
            orderer2 = from_pod(pod)

            for orderer_ in (orderer, orderer2):
                ordered = orderer_.reorder(descending)
                result = [str(x.version) for x in ordered]
                self.assertEqual(result, expected_order)

        null_orderer = NullPackageOrder()
        split_orderer = VersionSplitPackageOrder(Version("2.6.0"))
        # after v1.1.0 and before v1.1.1
        timestamp_orderer = TimestampPackageOrder(timestamp=3001, rank=3)
        # after v2.1.0 and before v2.1.5
        timestamp2_orderer = TimestampPackageOrder(timestamp=7001, rank=3)

        expected_null_result = ["7", "6", "5"]
        expected_split_result = ["2.6.0", "2.5.2", "2.7.0", "2.6.8"]
        expected_timestamp_result = ["1.1.1", "1.1.0", "1.0.6", "1.0.5",
                                     "1.2.0", "2.0.0", "2.1.5", "2.1.0"]
        expected_timestamp2_result = ["2.1.5", "2.1.0", "2.0.0", "1.2.0",
                                      "1.1.1", "1.1.0", "1.0.6", "1.0.5"]

        _test(null_orderer, "pysplit", expected_null_result)
        _test(split_orderer, "python", expected_split_result)
        _test(timestamp_orderer, "timestamped", expected_timestamp_result)
        _test(timestamp2_orderer, "timestamped", expected_timestamp2_result)

        fam_orderer = PerFamilyOrder(
            order_dict=dict(pysplit=null_orderer,
                            python=split_orderer,
                            timestamped=timestamp_orderer),
            default_order=SortedOrder(descending=False))

        _test(fam_orderer, "pysplit", expected_null_result)
        _test(fam_orderer, "python", expected_split_result)
        _test(fam_orderer, "timestamped", expected_timestamp_result)
        _test(fam_orderer, "pymum", ["1", "2", "3"])


class TestMemoryPackages(TestBase):
    def test_1_memory_variant_parent(self):
        """Test that a package's variant's parent is the original package
        """
        desc = 'the foo package'
        package = create_package('foo', {'description': desc})
        self.assertEqual(package.description, desc)
        variant = package.iter_variants().next()
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
