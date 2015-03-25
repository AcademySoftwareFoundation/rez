from rez.packages_ import iter_package_families, iter_packages, get_package, \
    create_package, get_developer_package
from rez.package_repository import create_memory_package_repository
from rez.tests.util import TestBase, TempdirMixin
from rez.utils.formatting import PackageRequest
from rez.utils.data_utils import SourceCode
import rez.vendor.unittest2 as unittest
from rez.vendor.version.version import Version
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
    # variant solver
    'variable_variant_package_in_single_column',
    'package_name_in_require_and_variant',
    'bar-4.8.5', 'bar-4.8.2', 'bar-4.5.3',
    'three_packages_in_variant',
    'multi_version_variant_higher_to_lower_version_order',
    'multi_version_variant_lower_to_higher_version_order',
    'asymmetric_variants',
    'permuted_family_names_same_position_weight',
    'variant_with_antipackage',
    'multi_packages_variant_unsorted',
    'eek-2.0.0', 'eek-1.0.1', 'eek-1.0.0',
    'variant_with_weak_package_in_variant',
    'permuted_family_names',
    'foo-1.0.0', 'foo-1.1.0',
    'multi_packages_variant_sorted',
    'bah-2.0.0', 'bah-1.0.1', 'bah-1.0.0',
    'two_packages_in_variant_unsorted',
    # packages from data/packages
    'unversioned',
    'unversioned_py',
    'versioned-1.0', 'versioned-2.0', 'versioned-3.0',
    'variants_py-2.0',
    'single_unversioned',
    'single_versioned-3.5',
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

        cls.settings = dict(
            packages_path=[cls.solver_packages_path,
                           cls.yaml_packages_path,
                           cls.py_packages_path])

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

    def test_6(self):
        """test variant iteration."""
        expected_data_ = dict(
            name="variants_py",
            version=Version("2.0"),
            description="package with variants",
            base=os.path.join(self.py_packages_path, "variants_py", "2.0"),
            commands=SourceCode('env.PATH.append("{root}/bin")'))

        requires_ = ["platform-linux", "platform-osx"]

        package = get_package("variants_py", "2.0")
        for i, variant in enumerate(package.iter_variants()):
            expected_data = expected_data_.copy()
            expected_data["requires"] = [PackageRequest('python-2.7'),
                                         PackageRequest(requires_[i])]
            data = variant.validated_data()
            self.assertDictEqual(data, expected_data)
            self.assertEqual(variant.index, i)
            self.assertEqual(variant.parent, package)

    def test_7(self):
        """test variant installation."""
        repo_path = os.path.join(self.root, "packages")
        os.makedirs(repo_path)

        path = os.path.join(self.packages_base_path, "developer")
        package = get_developer_package(path)

        def _data(obj):
            d = obj.validated_data()
            if "base" in d:
                del d["base"]
            if "timestamp" in d:
                del d["timestamp"]
            return d

        # we loop twice here to make sure the second round of variant installs
        # have no effect (they're already installed into new repo package)
        for i in range(2):
            # install variants into new repo
            for variant in package.iter_variants():
                test_ = variant.install(repo_path, dry_run=True)
                if i:
                    self.assertNotEqual(test_, None)
                else:
                    self.assertEqual(test_, None)

                variant_ = variant.install(repo_path)
                data = _data(variant)
                data_ = _data(variant_)
                self.assertDictEqual(data, data_)

            # now there should be a package that matches the dev package
            package_ = get_package(package.name, package.version, paths=[repo_path])
            self.assertNotEqual(package_, None)
            data = _data(package)
            data_ = _data(package_)
            self.assertDictEqual(data, data_)


def get_test_suites():
    suites = []
    suite = unittest.TestSuite()
    suite.addTest(TestPackages("test_1"))
    suite.addTest(TestPackages("test_2"))
    suite.addTest(TestPackages("test_3"))
    suite.addTest(TestPackages("test_4"))
    suite.addTest(TestPackages("test_5"))
    suite.addTest(TestPackages("test_6"))
    suite.addTest(TestPackages("test_7"))
    suites.append(suite)
    return suites


if __name__ == '__main__':
    unittest.main()
