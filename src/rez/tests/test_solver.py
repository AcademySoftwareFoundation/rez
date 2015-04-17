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
