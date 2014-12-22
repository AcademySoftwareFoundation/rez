from rez.package_resources import VersionlessPackageResource, \
    VersionlessVariantResource, register_resource, \
    CombinedPackageFamilyResource, CombinedPackageResource
from rez.packages_ import iter_package_families, iter_packages, get_package, \
    create_package
from rez.package_repository import create_memory_package_repository
from rez.tests.util import TestBase
from rez.utils.formatting import PackageRequest
from rez.utils.data_utils import SourceCode
import rez.vendor.unittest2 as unittest
from rez.vendor.version.version import Version
import os.path

register_resource(VersionlessPackageResource, force=True)
register_resource(VersionlessVariantResource, force=True)
register_resource(CombinedPackageFamilyResource, force=True)
register_resource(CombinedPackageResource, force=True)

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
    # packages from data/packages
    'unversioned',
    'versioned-1.0', 'versioned-2.0',
    'single_unversioned',
    'single_versioned-3.5',
    'multi-1.0', 'multi-1.1', 'multi-1.2','bah-2.0.0',
    'multi_packages_variant_sorted-1', 'asymmetric_variants-1', 'bar-4.5.3',
    'permuted_family_names_same_position_weight-1', 'eek-1.0.1', 'bar-4.8.5',
    'multi_packages_variant_unsorted-1', 'package_name_in_require_and_variant-1',
    'multi_version_variant_lower_to_higher_version_order-1', 'bar-4.8.2',
    'variable_variant_package_in_single_column-1', 'three_packages_in_variant-1',
    'multi_version_variant_higher_to_lower_version_order-1', 'eek-2.0.0',
    'two_packages_in_variant_unsorted-1', 'variant_with_weak_package_in_variant-1',
    'foo-1.1.0', 'eek-1.0.0', 'bah-1.0.0', 'bah-1.0.1', 'foo-1.0.0',
    'permuted_family_names-1', 'variant_with_antipackage-1'])


ALL_FAMILIES = set(x.split('-')[0] for x in ALL_PACKAGES)


def _to_names(it):
    return set(p.name for p in it)


def _to_qnames(it):
    return set(p.qualified_name for p in it)


class TestPackages(TestBase):
    @classmethod
    def setUpClass(cls):
        path = os.path.realpath(os.path.dirname(__file__))
        cls.solver_packages_path = os.path.join(
            path, "data", "solver", "packages")
        cls.yaml_packages_path = os.path.join(
            path, "data", "packages", "yaml_packages")
        cls.py_packages_path = os.path.join(
            path, "data", "packages", "py_packages")

        cls.settings = dict(
            packages_path=[cls.solver_packages_path,
                           cls.yaml_packages_path,
                           cls.py_packages_path])

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

    def test_3(self):
        """check package contents."""
        package = get_package("versioned", "3.0")
        expected_data = dict(
             name="versioned",
             version=Version("3.0"),
             base=os.path.join(self.py_packages_path, "versioned", "3.0"),
             commands=SourceCode('env.PATH.append("{root}/bin")'))
        data = package.validated_data()
        self.assertDictEqual(data, expected_data)

        package = get_package("versioned", "2.0")
        expected_uri = os.path.join(self.yaml_packages_path,
                                    "versioned", "2.0", "package.yaml")
        self.assertEqual(package.uri, expected_uri)

    def test_4(self):
        """test package creation."""
        package_data = {
            "version":          "1.0.0",
            "description":      "something foo-like",
            "requires":         ["python-2.6+"]
        }

        package = create_package("foo", package_data)
        self.assertEqual(package.version, Version("1.0.0"))
        self.assertEqual(package.description, "something foo-like")
        self.assertEqual(package.requires, [PackageRequest("python-2.6+")])


def get_test_suites():
    suites = []
    suite = unittest.TestSuite()
    suite.addTest(TestPackages("test_1"))
    suite.addTest(TestPackages("test_2"))
    suite.addTest(TestPackages("test_3"))
    suite.addTest(TestPackages("test_4"))
    suites.append(suite)
    return suites


if __name__ == '__main__':
    unittest.main()
