import shutil
from rez.resolved_context import ResolvedContext
from rez.vendor.version.requirement import Requirement
from rez.solver import Solver, Cycle, SolverStatus
import rez.vendor.unittest2 as unittest
from rez.tests.util import TestBase, TempdirMixin
import itertools
import os.path
from rez.vendor.version.version import Version


class TestSolver(TestBase):
    @classmethod
    def setUpClass(cls):
        path = os.path.dirname(__file__)
        packages_path = os.path.join(path, "data", "solver", "packages")
        cls.packages_path = [packages_path]
        cls.settings = dict(
            packages_path=[cls.packages_path])

    def _create_solvers(self, reqs):
        s1 = Solver(reqs,
                    self.packages_path,
                    optimised=True,
                    verbosity=Solver.max_verbosity)
        s2 = Solver(reqs,
                    self.packages_path,
                    optimised=False,
                    verbosity=Solver.max_verbosity)

        s_perms = []
        perms = itertools.permutations(reqs)
        for reqs_ in perms:
            s = Solver(reqs_,
                       self.packages_path,
                       optimised=True,
                       verbosity=Solver.max_verbosity)
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

    def _solve(self, request, expected_packages=[], non_expected_packages=[], fails_to_resolve=False):

        resolved_context = ResolvedContext(request)
        if fails_to_resolve:
            self.assertIsNone(resolved_context.resolved_packages)
            return
        for package in expected_packages:
            expected_package_name, package_version = package.split('-')
            expected_package_version = Version(package_version)
            resolved_package_version = TestVariantResolutionOrder.getResolvedPackageVersion(resolved_context,
                                                                                            expected_package_name)
            self.assertEqual(resolved_package_version, expected_package_version,
                             'wrong %s version selected' % expected_package_name )

        for non_expected in non_expected_packages:
            for package in resolved_context.resolved_packages:
                self.assertNotEquals(package.name, non_expected,
                                     '%s should not be in the resolved packages' % non_expected)

        return resolved_context

    def test_resolve_higher_to_lower_version_ordered_variants(self):
        """
        Test we pick the higher version of the dependant package when the variants are ordered from higher to lower
         version range
        """
        request = ['multi_version_variant_higher_to_lower_version_order']
        expected_packages = ['bar-4.8.5']
        self._solve(request, expected_packages)

    def test_resolve_lower_to_higher_version_ordered_variants(self):
        """
        Test we pick the higher version of the dependant package when the variants are ordered from lower to higher
         version range
        """

        request = ['multi_version_variant_lower_to_higher_version_order']
        expected_packages = ['bar-4.8.5']
        self._solve(request, expected_packages)

    def test_variant_selection_variant_default_order(self):
        """
        Test that we get the variant with the highest version of family with the highest weighted average of
        where they appear in the variants
        """

        request = ['two_packages_in_variant_unsorted']
        expected_packages = ['bah-2.0.0', 'eek-1.0.1']
        self._solve(request, expected_packages)


    def test_variant_selection_requested_priority(self):
        """
        Test that the higher version of the package requested is selected first
        """

        request = ['two_packages_in_variant_unsorted', 'bah']
        expected_packages = ['bah-2.0.0', 'eek-1.0.1']
        self._solve(request, expected_packages)

        request = ['two_packages_in_variant_unsorted', 'eek']
        expected_packages = ['bah-1.0.1', 'eek-2.0.0']
        self._solve(request, expected_packages)


    def test_variant_selection_requested_priority_3(self):
        """
        Test that a particular variant gets selected if it is part of the requirements and the package contains
        diff packages with the same average positional weight
        """

        ##################### 1 #########################
        request = ['variable_variant_package_in_single_column', 'bah-1.0.1']
        expected_packages = ['foo-1.0.0', 'bah-1.0.1']
        self._solve(request, expected_packages)

        ##################### 2 #########################
        request = ['variable_variant_package_in_single_column', 'eek']
        expected_packages = ['foo-1.1.0', 'eek-1.0.1']
        self._solve(request, expected_packages)

        ###################### 3 #########################
        request = ['variable_variant_package_in_single_column', 'eek-2']
        expected_packages = ['foo-1.0.0', 'bah-1.0.1', 'eek-2.0.0']
        self._solve(request, expected_packages)

        ###################### 4 #########################
        request = ['variable_variant_package_in_single_column', 'eek-2', 'bah']
        expected_packages = ['foo-1.0.0', 'bah-1.0.1', 'eek-2.0.0']
        self._solve(request, expected_packages)


    def test_variant_selection_resolved_priority(self):
        """
        Test that a particular variant gets selected by the fam with highest positional weight once it is sorted
         by the fam_requires
        """

        request = ['two_packages_in_variant_unsorted', 'eek-1']
        expected_packages = ['bah-2.0.0', 'eek-1.0.1']
        self._solve(request, expected_packages)

    def test_variant_repeatable_ambiguous_selection(self):
        """
        Test the variant selection is repeatable when the selection is ambiguous
        """

        request = ['multi_packages_variant_sorted', 'bah']
        context1 = self._solve(request)
        contextToCompare1 = []
        for resolve_package in context1.resolved_packages:
            if resolve_package.name != 'multi_packages_variant_sorted':
                contextToCompare1.append(resolve_package)

        request = ['multi_packages_variant_unsorted', 'bah']
        context2 = self._solve(request)
        contextToCompare2 = []
        for resolve_package in context2.resolved_packages:
            if resolve_package.name != 'multi_packages_variant_unsorted':
                contextToCompare2.append(resolve_package)

        self.assertEqual(contextToCompare1, contextToCompare2, 'resolved packages differ not repeatable selection')

    def test_variant_with_permuted_family_names(self):
        """
        Test that the Version range has more weight than the order of the packages on the variant for fam name in the
         fam_requires
        """

        request = ['permuted_family_names', 'eek', 'bah']
        expected_packages = ['bah-2.0.0', 'eek-1.0.1']
        self._solve(request, expected_packages)

        request = ['permuted_family_names',  'bah', 'eek']
        expected_packages = ['bah-2.0.0', 'eek-1.0.1']
        self._solve(request, expected_packages)

    def test_variant_with_same_positional_weight(self):
        """
        Test that when we have a tie on positional average weight we pick the a fam name by alphabetical order
        """

        request = ['permuted_family_names_same_position_weight']
        # All have the same positional average weight
        # It should sort alphabetically first by bah then eek and then foo
        expected_packages = ['bah-2.0.0', 'eek-1.0.1', 'foo-1.0.0']
        self._solve(request, expected_packages)


    def test_asymmetric_variant_selection(self):
        """
        Test we can resolve packages that have asymmetric variants
         variants with different number of packages
        """

        request = ['asymmetric_variants', 'eek']
        expected_packages = ['bah-1.0.0', 'eek-1.0.1']
        self._solve(request, expected_packages)

        request = ['asymmetric_variants',  'bah', 'eek']
        expected_packages = ['bah-1.0.0', 'eek-1.0.1']
        self._solve(request, expected_packages)

        request = ['asymmetric_variants',  'bah']
        expected_packages = ['bah-2.0.0']
        non_expected_packages = ['eek']
        self._solve(request, expected_packages, non_expected_packages)

    def test_variant_with_antipackage(self):
        """
        Test the antipackage does not show up in the resolved context
        """

        request = ['asymmetric_variants', '!eek', 'bah']
        expected_packages = ['bah-2.0.0']
        non_expected_packages = ['eek']
        self._solve(request, expected_packages, non_expected_packages)

        request = [ 'variant_with_antipackage', 'asymmetric_variants', 'bah']
        expected_packages = ['bah-1.0.1', 'eek-1.0.0']
        self._solve(request, expected_packages)

        request = [ 'variant_with_antipackage', 'asymmetric_variants', 'eek']
        expected_packages = ['bah-1.0.1', 'eek-1.0.0']
        self._solve(request, expected_packages)

        request = [ 'asymmetric_variants', 'variant_with_antipackage', 'eek', 'bah']
        expected_packages = ['bah-1.0.0', 'eek-1.0.1']
        self._solve(request, expected_packages)

        request = [ 'asymmetric_variants', 'variant_with_antipackage', 'eek', 'bah-2']
        self._solve(request, [], fails_to_resolve=True)


    def test_variant_with_weak_packages(self):
        """
        Test that the variant with a weak package gets sorted at the end
        """

        request = ['variant_with_weak_package_in_variant', 'bah-1']
        expected_packages = ['bah-1.0.1']
        self._solve(request, expected_packages)

        request = ['variant_with_weak_package_in_variant', 'bah']
        expected_packages = ['bah-1.0.1']
        self._solve(request, expected_packages)

        request = ['variant_with_weak_package_in_variant', 'bah-2']
        expected_packages = ['bah-2.0.0']
        self._solve(request, expected_packages)

        request = ['variant_with_weak_package_in_variant']
        expected_packages = ['bah-1.0.1']
        self._solve(request, expected_packages)

    def test_package_name_in_require_and_variant(self):
        """
        Test weird but valid case where a package family name appears in the requires and also in the variants
        """
        request = ['package_name_in_require_and_variant']
        expected_packages = ['bah-2.0.0', 'eek-1.0.1']
        self._solve(request, expected_packages)

    def test_different_slices_sorting_respect_request_criteria(self):
        """
        Test that the sort of different variants slices get sorted with the same request criteria
        """
        request = ['python-2.7',  'eek', 'three_packages_in_variant']
        expected_packages = ['bah-1.0.1', 'eek-2.0.0', 'python-2.7.0']
        self._solve(request, expected_packages)

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
    suites.append(unittest.TestLoader().loadTestsFromTestCase(TestVariantResolutionOrder))
    return suites

if __name__ == '__main__':
    unittest.main()
