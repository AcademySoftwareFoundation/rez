import shutil
import tempfile
from rez.packages import load_developer_package
from rez.resolved_context import ResolvedContext
from rez.vendor.version.requirement import Requirement
from rez.solver import Solver, Cycle, SolverStatus
import rez.vendor.unittest2 as unittest
from rez.tests.util import TestBase
import itertools
import os.path


class TestSolver(TestBase):
    @classmethod
    def setUpClass(cls):
        path = os.path.dirname(__file__)
        packages_path = os.path.join(path, "data", "solver", "packages")
        cls.settings = dict(
            packages_path=[packages_path])

    def _create_solvers(self, reqs):
        s1 = Solver(reqs,
                    optimised=True,
                    verbose=True)
        s2 = Solver(reqs,
                    optimised=False,
                    verbose=False)

        s_perms = []
        perms = itertools.permutations(reqs)
        for reqs_ in perms:
            s = Solver(reqs_,
                       optimised=True,
                       verbose=False)
            s_perms.append(s)

        return (s1, s2, s_perms)

    def _solve(self, packages, expected_resolve):
        print
        reqs = [Requirement(x) for x in packages]
        s1, s2, s_perms = self._create_solvers(reqs)

        s1.solve()
        self.assertEqual(s1.status, SolverStatus.solved)
        resolve = [str(x) for x in s1.resolved_packages]

        print
        print "request: %s" % ' '.join(packages)
        print "expecting: %s" % ' '.join(expected_resolve)
        print "result: %s" % ' '.join(str(x) for x in resolve)
        self.assertEqual(resolve, expected_resolve)

        print "checking that unoptimised solve matches optimised..."
        s2.solve()
        self.assertEqual(s2.status, SolverStatus.solved)
        resolve2 = [str(x) for x in s2.resolved_packages]
        self.assertEqual(resolve2, resolve)

        print "checking that permutations also succeed..."
        for s in s_perms:
            s.solve()
            self.assertEqual(s.status, SolverStatus.solved)

        return s1

    def _fail(self, *packages):
        print
        reqs = [Requirement(x) for x in packages]
        s1, s2, s_perms = self._create_solvers(reqs)

        s1.solve()
        print
        print "request: %s" % ' '.join(packages)
        print "expecting failure"
        self.assertEqual(s1.status, SolverStatus.failed)
        print "result: %s" % str(s1.failure_reason())

        print "checking that unoptimised solve fail matches optimised..."
        s2.solve()
        self.assertEqual(s2.status, SolverStatus.failed)
        self.assertEqual(s1.failure_reason(), s2.failure_reason())

        print "checking that permutations also fail..."
        for s in s_perms:
            s.solve()
            self.assertEqual(s.status, SolverStatus.failed)

        return s1

    def test_1(self):
        """Extremely basic solves involving a single package."""
        self._solve([],
                    [])
        self._solve(["nada"],
                    ["nada[]"])
        self._solve(["!nada"],
                    [])
        self._solve(["~nada"],
                    [])
        self._solve(["python"],
                    ["python-2.7.0[]"])
        self._solve(["~python-2+"],
                    [])
        self._solve(["~python"],
                    [])
        self._solve(["!python-2.5"],
                    [])
        self._solve(["!python"],
                    [])

    def test_2(self):
        """Basic solves involving a single package."""
        self._solve(["nada", "~nada"],
                    ["nada[]"])
        self._solve(["nopy"],
                    ["nopy-2.1[]"])
        self._solve(["python-2.6"],
                    ["python-2.6.8[]"])
        self._solve(["python-2.6", "!python-2.6.8"],
                    ["python-2.6.0[]"])
        self._solve(["python-2.6", "python-2.6.5+"],
                    ["python-2.6.8[]"])
        self._solve(["python", "python-0+<2.6"],
                    ["python-2.5.2[]"])
        self._solve(["python", "python-0+<2.6.8"],
                    ["python-2.6.0[]"])
        self._solve(["python", "~python-2.7+"],
                    ["python-2.7.0[]"])
        self._solve(["!python-2.6+", "python"],
                    ["python-2.5.2[]"])

    def test_3(self):
        """Failures in the initial request."""
        self._fail("nada", "!nada")
        self._fail("python-2.6", "~python-2.7")
        self._fail("pyfoo", "nada", "!nada")

    def test_4(self):
        """Basic failures."""
        self._fail("pybah", "!python")
        self._fail("pyfoo-3.1", "python-2.7+")
        self._fail("pyodd<2", "python-2.7")
        self._fail("nopy", "python-2.5.2")

    def test_5(self):
        """More complex failures."""
        self._fail("bahish", "pybah<5")

    def test_6(self):
        """Basic solves involving multiple packages."""
        self._solve(["nada", "nopy"],
                    ["nada[]", "nopy-2.1[]"])
        self._solve(["pyfoo"],
                    ["python-2.6.8[]", "pyfoo-3.1.0[]"])
        self._solve(["pybah"],
                    ["python-2.5.2[]", "pybah-5[]"])
        self._solve(["nopy", "python"],
                    ["nopy-2.1[]", "python-2.7.0[]"])
        self._solve(["pybah", "!python-2.5"],
                    ["python-2.6.8[]", "pybah-4[]"])
        self._solve(["pybah", "!python-2.5", "python<2.6.8"],
                    ["python-2.6.0[]", "pybah-4[]"])
        self._solve(["python", "pybah"],
                    ["python-2.6.8[]", "pybah-4[]"])

    def test_7(self):
        """More complex solves."""
        self._solve(["python", "pyodd"],
                    ["python-2.6.8[]", "pybah-4[]", "pyodd-2[]"])
        self._solve(["pybah", "pyodd"],
                    ["python-2.5.2[]", "pybah-5[]", "pyodd-2[]"])
        self._solve(["pysplit", "python-2.5"],
                    ["pysplit-5[]", "python-2.5.2[]"])
        self._solve(["~python<2.6", "pysplit"],
                    ["pysplit-5[]"])
        self._solve(["python", "bahish", "pybah"],
                    ["python-2.5.2[]", "pybah-5[]", "bahish-2[]"])

    def test_8(self):
        """Cyclic failures."""
        def _test(*pkgs):
            s = self._fail(*pkgs)
            self.assertTrue(isinstance(s.failure_reason(), Cycle))

        _test("pymum-1")
        _test("pydad-1")
        _test("pyson-1")
        _test("pymum-3")
        _test("pydad-3")
        s = self._fail("pymum-2")
        self.assertFalse(isinstance(s.failure_reason(), Cycle))


class TempdirMixin(object):
    """Mixin that adds tmpdir create/delete."""
    @classmethod
    def setUpClass(cls):
        cls.root = tempfile.mkdtemp(prefix="rez_test_")

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.root):
            shutil.rmtree(cls.root)


class TestVariantResolutionOrder(TestBase, TempdirMixin):

    class FakeArgParseOpts(object):

        def __getattr__(self, key):
            return None

    @classmethod
    def setUpClass(cls):
        TempdirMixin.setUpClass()

        path = os.path.dirname(__file__)
        packages_path = os.path.join(path, "data", "solver", "packages")

        cls.install_root = os.path.join(cls.root, "packages")

        cls.settings = dict(
            packages_path=[cls.install_root],
            add_bootstrap_path=False,
            resolve_caching=False,
            warn_untimestamped=False,
            implicit_packages=[])

        shutil.copytree(packages_path, cls.install_root)

    @classmethod
    def tearDownClass(cls):
        TempdirMixin.tearDownClass()

    def test_resolve_higher_to_lower_version_ordered_variants(self):
        """
        Test we pick up the higher version of the dependant package when the variants are from higher to lower
        """
        expected_package_version = self.getPackageVersion('bar', '4.8.5')
        request = ['multi_version_variant_higher_to_lower_version_order']
        context = ResolvedContext(request)
        resolved_package_version = TestVariantResolutionOrder.getResolvedPackageVersion(context, 'bar')

        self.assertEqual(resolved_package_version, expected_package_version, 'wrong bar version selected')

    def test_resolve_lower_to_higher_version_ordered_variants(self):
        """
        Test we pick up the higher version of the dependant package when the variants are ordered from lower to higher
        """
        expected_package_version = self.getPackageVersion('bar', '4.8.5')

        request = ['multi_version_variant_lower_to_higher_version_order']
        context = ResolvedContext(request)
        resolved_package_version = TestVariantResolutionOrder.getResolvedPackageVersion(context, 'bar')

        self.assertEqual(resolved_package_version, expected_package_version, 'wrong bar version selected')

    def test_variant_selection_variant_default_order(self):
        """
        Test that the variants are sorted based on the positional weight if no
        """
        expected_bah_package_version = self.getPackageVersion("bah", "2.0.0")
        expected_eek_package_version = self.getPackageVersion("eek", "1.0.1")

        request = ['two_packages_in_variant_unsorted']
        context = ResolvedContext(request)
        resolved_bah_package_version = TestVariantResolutionOrder.getResolvedPackageVersion(context, 'bah')
        resolved_eek_package_version = TestVariantResolutionOrder.getResolvedPackageVersion(context, 'eek')

        self.assertEqual(resolved_bah_package_version, expected_bah_package_version, 'wrong bah version selected')
        self.assertEqual(resolved_eek_package_version, expected_eek_package_version, 'wrong eek version selected')

    def test_variant_selection_requested_priority(self):
        """
        Test that the higher version of the package requested is selected first
        """

        expected_bah_package_version = self.getPackageVersion("bah", "2.0.0")
        expected_eek_package_version = self.getPackageVersion("eek", "1.0.1")

        request = ['two_packages_in_variant_unsorted', 'bah']
        context = ResolvedContext(request)
        resolved_bah_package_version = TestVariantResolutionOrder.getResolvedPackageVersion(context, 'bah')
        resolved_eek_package_version = TestVariantResolutionOrder.getResolvedPackageVersion(context, 'eek')

        self.assertEqual(resolved_bah_package_version, expected_bah_package_version, 'wrong bah version selected')
        self.assertEqual(resolved_eek_package_version, expected_eek_package_version, 'wrong eek version selected')

    def test_variant_selection_requested_priority_2(self):
        """
        Test that a particular variant gets selected if it is part of the requirements
        """
        expected_bah_package_version = self.getPackageVersion("bah", "1.0.1")
        expected_eek_package_version = self.getPackageVersion("eek", "2.0.0")

        request = ['two_packages_in_variant_unsorted', 'eek']
        context = ResolvedContext(request)
        resolved_bah_package_version = TestVariantResolutionOrder.getResolvedPackageVersion(context, 'bah')
        resolved_eek_package_version = TestVariantResolutionOrder.getResolvedPackageVersion(context, 'eek')

        self.assertEqual(resolved_bah_package_version, expected_bah_package_version, 'wrong bah version selected')
        self.assertEqual(resolved_eek_package_version, expected_eek_package_version, 'wrong eek version selected')

    def test_variant_selection_requested_priority_3(self):
        """
        Test that a particular variant gets selected if it is part of the requirements and the package contains
        diff packages families in the same column
        """

        ###################### 1 #########################
        expected_foo_package_version = self.getPackageVersion("foo", "1.0.0")
        expected_bah_package_version = self.getPackageVersion("bah", "1.0.1")

        request = ['variable_variant_package_in_single_column', 'bah']
        context = ResolvedContext(request)
        resolved_bah_package_version = TestVariantResolutionOrder.getResolvedPackageVersion(context, 'bah')
        resolved_foo_package_version = TestVariantResolutionOrder.getResolvedPackageVersion(context, 'foo')

        self.assertEqual(resolved_bah_package_version, expected_bah_package_version, 'wrong bah version selected')
        self.assertEqual(resolved_foo_package_version, expected_foo_package_version, 'wrong foo version selected')

        ###################### 2 #########################
        expected_eek_package_version = self.getPackageVersion("eek", "1.0.1")
        expected_foo_package_version = self.getPackageVersion("foo", "1.1.0")

        request2 = ['variable_variant_package_in_single_column', 'eek']
        context2 = ResolvedContext(request2)
        resolved_eek_package_version = TestVariantResolutionOrder.getResolvedPackageVersion(context2, 'eek')
        resolved_foo_package_version = TestVariantResolutionOrder.getResolvedPackageVersion(context2, 'foo')

        self.assertEqual(resolved_eek_package_version, expected_eek_package_version, 'wrong eek version selected')
        self.assertEqual(resolved_foo_package_version, expected_foo_package_version, 'wrong foo version selected')

        ###################### 3 #########################
        expected_eek_package_version = self.getPackageVersion("eek", "2.0.0")
        expected_bah_package_version = self.getPackageVersion("bah", "1.0.1")
        expected_foo_package_version = self.getPackageVersion("foo", "1.0.0")

        request3 = ['variable_variant_package_in_single_column', 'eek-2']
        context3 = ResolvedContext(request3)
        resolved_eek_package_version = TestVariantResolutionOrder.getResolvedPackageVersion(context3, 'eek')
        resolved_foo_package_version = TestVariantResolutionOrder.getResolvedPackageVersion(context3, 'foo')
        resolved_bah_package_version = TestVariantResolutionOrder.getResolvedPackageVersion(context3, 'bah')

        self.assertEqual(resolved_eek_package_version, expected_eek_package_version, 'wrong eek version selected')
        self.assertEqual(resolved_foo_package_version, expected_foo_package_version, 'wrong foo version selected')
        self.assertEqual(resolved_bah_package_version, expected_bah_package_version, 'wrong bah version selected')

        ###################### 4 #########################
        expected_eek_package_version = self.getPackageVersion("eek", "2.0.0")
        expected_bah_package_version = self.getPackageVersion("bah", "1.0.1")
        expected_foo_package_version = self.getPackageVersion("foo", "1.0.0")

        request3 = ['variable_variant_package_in_single_column', 'eek-2', 'bah']
        context3 = ResolvedContext(request3)
        resolved_eek_package_version = TestVariantResolutionOrder.getResolvedPackageVersion(context3, 'eek')
        resolved_foo_package_version = TestVariantResolutionOrder.getResolvedPackageVersion(context3, 'foo')
        resolved_bah_package_version = TestVariantResolutionOrder.getResolvedPackageVersion(context3, 'bah')

        self.assertEqual(resolved_eek_package_version, expected_eek_package_version, 'wrong eek version selected')
        self.assertEqual(resolved_foo_package_version, expected_foo_package_version, 'wrong foo version selected')
        self.assertEqual(resolved_bah_package_version, expected_bah_package_version, 'wrong bah version selected')

    def test_variant_selection_resolved_priority(self):
        """
        Test that a particular variant gets selected if it is already resolved
        """
        expected_bah_package_version = self.getPackageVersion("bah", "2.0.0")
        expected_eek_package_version = self.getPackageVersion("eek", "1.0.1")

        request = ['two_packages_in_variant_unsorted', 'eek-1']
        context = ResolvedContext(request)
        resolved_bah_package_version = TestVariantResolutionOrder.getResolvedPackageVersion(context, 'bah')
        resolved_eek_package_version = TestVariantResolutionOrder.getResolvedPackageVersion(context, 'eek')

        self.assertEqual(resolved_bah_package_version, expected_bah_package_version, 'wrong bah version selected')
        self.assertEqual(resolved_eek_package_version, expected_eek_package_version, 'wrong eek version selected')

    def test_variant_repeatable_ambiguous_selection(self):
        """
        Test the variant selection is repeatable when the selection is ambiguous
        """

        request = ['multi_packages_variant_sorted', 'bah']
        context1 = ResolvedContext(request)
        contextToCompare1 = []
        for resolve_package in context1.resolved_packages:
            if resolve_package.name != 'multi_packages_variant_sorted':
                contextToCompare1.append(resolve_package)

        request = ['multi_packages_variant_unsorted', 'bah']
        context2 = ResolvedContext(request)
        contextToCompare2 = []
        for resolve_package in context2.resolved_packages:
            if resolve_package.name != 'multi_packages_variant_unsorted':
                contextToCompare2.append(resolve_package)

        self.assertEqual(contextToCompare1, contextToCompare2, 'resolved packages differ not repeatable selection')

    def test_variant_with_permuted_family_names(self):
        """
        Test that the Version range has more weight than the order of the packages on the variant
        """

        expected_eek_package_version = self.getPackageVersion("eek", "1.0.1")
        expected_bah_package_version = self.getPackageVersion("bah", "2.0.0")

        request = ['permuted_family_names', 'eek', 'bah']
        context = ResolvedContext(request)
        resolved_bah_package_version = TestVariantResolutionOrder.getResolvedPackageVersion(context, 'bah')
        resolved_eek_package_version = TestVariantResolutionOrder.getResolvedPackageVersion(context, 'eek')

        self.assertEqual(resolved_bah_package_version, expected_bah_package_version, 'wrong bah version selected')
        self.assertEqual(resolved_eek_package_version, expected_eek_package_version, 'wrong eek version selected')

        expected_bah_package_version = self.getPackageVersion("bah", "2.0.0")
        expected_eek_package_version = self.getPackageVersion("eek", "1.0.1")

        request2 = ['permuted_family_names',  'bah', 'eek']
        context2 = ResolvedContext(request2)
        resolved_bah_package_version = TestVariantResolutionOrder.getResolvedPackageVersion(context2, 'bah')
        resolved_eek_package_version = TestVariantResolutionOrder.getResolvedPackageVersion(context2, 'eek')

        self.assertEqual(resolved_bah_package_version, expected_bah_package_version, 'wrong bah version selected')
        self.assertEqual(resolved_eek_package_version, expected_eek_package_version, 'wrong eek version selected')

    def test_asymmetric_variant_selection(self):
        """
        Test we can resolve packages that have asymmetric variants, variants with different number of packages
        """
        expected_eek_package_version = self.getPackageVersion("eek", "1.0.1")
        expected_bah_package_version = self.getPackageVersion("bah", "1.0.0")

        request = ['asymmetric_variants', 'eek']
        context = ResolvedContext(request)
        resolved_bah_package_version = TestVariantResolutionOrder.getResolvedPackageVersion(context, 'bah')
        resolved_eek_package_version = TestVariantResolutionOrder.getResolvedPackageVersion(context, 'eek')

        self.assertEqual(resolved_bah_package_version, expected_bah_package_version, 'wrong bah version selected')
        self.assertEqual(resolved_eek_package_version, expected_eek_package_version, 'wrong eek version selected')

        expected_eek_package_version = self.getPackageVersion("eek", "1.0.1")
        expected_bah_package_version = self.getPackageVersion("bah", "1.0.0")

        request2 = ['asymmetric_variants',  'bah', 'eek']
        context2 = ResolvedContext(request2)
        resolved_bah_package_version = TestVariantResolutionOrder.getResolvedPackageVersion(context2, 'bah')
        resolved_eek_package_version = TestVariantResolutionOrder.getResolvedPackageVersion(context2, 'eek')

        self.assertEqual(resolved_bah_package_version, expected_bah_package_version, 'wrong bah version selected')
        self.assertEqual(resolved_eek_package_version, expected_eek_package_version, 'wrong eek version selected')

        expected_bah_package_version = self.getPackageVersion("bah", "2.0.0")

        request3 = ['asymmetric_variants',  'bah']
        context3 = ResolvedContext(request3)
        resolved_bah_package_version = TestVariantResolutionOrder.getResolvedPackageVersion(context3, 'bah')

        self.assertEqual(resolved_bah_package_version, expected_bah_package_version, 'wrong bah version selected')
        for package in context3.resolved_packages:
            self.assertNotEquals(package.name, "eek", 'eek should not be in the resolved packages')

    def test_variant_with_antipackage(self):
        """
        Test the antipackage does not show up in the resolved context
        """
        expected_bah_package_version = self.getPackageVersion("bah", "2.0.0")

        request = ['asymmetric_variants', '!eek', 'bah']
        context = ResolvedContext(request)
        resolved_bah_package_version = TestVariantResolutionOrder.getResolvedPackageVersion(context, 'bah')

        self.assertEqual(resolved_bah_package_version, expected_bah_package_version, 'wrong bah version selected')
        for package in context.resolved_packages:
            self.assertNotEquals(package.name, "eek", 'eek should not be in the resolved packages')

        expected_eek_package_version = self.getPackageVersion("eek", "1.0.1")
        expected_bah_package_version = self.getPackageVersion("bah", "1.0.0")

        request2 = [ 'variant_with_antipackage', 'asymmetric_variants', 'bah']
        context2 = ResolvedContext(request2)
        resolved_bah_package_version = TestVariantResolutionOrder.getResolvedPackageVersion(context2, 'bah')
        resolved_eek_package_version = TestVariantResolutionOrder.getResolvedPackageVersion(context2, 'eek')

        self.assertEqual(resolved_bah_package_version, expected_bah_package_version, 'wrong bah version selected')
        self.assertEqual(resolved_eek_package_version, expected_eek_package_version, 'wrong eek version selected')



    def getPackageVersion(self, package_name, package_version):
        package_path = os.path.join(self.install_root, package_name, package_version)
        package = load_developer_package(package_path)
        return package.version

    @staticmethod
    def getResolvedPackageVersion(context, package_name):
        for package in context.resolved_packages:
            if package.name == package_name:
                return package.version
def get_test_suites():
    suites = []
    suite = unittest.TestSuite()
    suite.addTest(TestSolver("test_1"))
    suite.addTest(TestSolver("test_2"))
    suite.addTest(TestSolver("test_3"))
    suite.addTest(TestSolver("test_4"))
    suite.addTest(TestSolver("test_5"))
    suite.addTest(TestSolver("test_6"))
    suite.addTest(TestSolver("test_7"))
    suite.addTest(TestSolver("test_8"))
    suites.append(suite)
    return suites

if __name__ == '__main__':
    unittest.main()
