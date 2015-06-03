"""
test dependency resolving algorithm
"""
from rez.vendor.version.requirement import Requirement
from rez.solver import Solver, Cycle, SolverStatus
from rez.config import config
from rez.exceptions import ConfigurationError
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
            packages_path=[cls.packages_path],
            package_filter=None)

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

    def test_01(self):
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

    def test_02(self):
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

    def test_03(self):
        """Failures in the initial request."""
        self._fail("nada", "!nada")
        self._fail("python-2.6", "~python-2.7")
        self._fail("pyfoo", "nada", "!nada")

    def test_04(self):
        """Basic failures."""
        self._fail("pybah", "!python")
        self._fail("pyfoo-3.1", "python-2.7+")
        self._fail("pyodd<2", "python-2.7")
        self._fail("nopy", "python-2.5.2")

    def test_05(self):
        """More complex failures."""
        self._fail("bahish", "pybah<5")

    def test_06(self):
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

    def test_07(self):
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

    def test_08(self):
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

    # variant tests

    def test_09_version_priority_mode(self):
        config.override("variant_select_mode", "version_priority")
        self._solve(["pyvariants", "python"],
                    ["python-2.7.0[]", "pyvariants-2[0]"])
        self._solve(["pyvariants", "python", "nada"],
                    ["python-2.7.0[]", "pyvariants-2[0]", "nada[]"])

    def test_10_intersection_priority_mode(self):
        config.override("variant_select_mode", "intersection_priority")
        self._solve(["pyvariants", "python"],
                    ["python-2.7.0[]", "pyvariants-2[0]"])
        self._solve(["pyvariants", "python", "nada"],
                    ["python-2.6.8[]", "nada[]", "pyvariants-2[1]"])

    # re-prioritization tests

    def test_11_direct_complete(self):
        """Test setting of the version_priority in simple situations, where
        the altered package is a direct request
        """
        # test a complete ordering
        config.override("version_priority",
                        {"python": ["2.6.0", "2.5.2", "2.7.0", "2.6.8"]})
        self._solve(["python"],
                    ["python-2.6.0[]"])
        self._solve(["python", "!python-2.6.0"],
                    ["python-2.5.2[]"])
        self._solve(["python", "!python<=2.6.0"],
                    ["python-2.7.0[]"])
        self._solve(["python", "!python-2.6.0", "!python-2.5.2",
                     "!python-2.7.0"],
                    ["python-2.6.8[]"])

        # check that we can still request a lower-priority version
        self._solve(["python-2.6.8"],
                    ["python-2.6.8[]"])

    def test_12_direct_single(self):
        """check that if you specify only one version, that version is highest
        priority, rest are normal
        """
        config.override("version_priority", {"python": ["2.6.8"]})
        self._solve(["python"],
                    ["python-2.6.8[]"])
        self._solve(["python", "!python-2.6.8"],
                    ["python-2.7.0[]"])
        self._solve(["python<2.6.8"],
                    ["python-2.6.0[]"])
        self._solve(["python<2.6"],
                    ["python-2.5.2[]"])

        # confirm that sorting for version ranges is still normal
        self._solve(["python-2.6+<2.7"],
                    ["python-2.6.8[]"])
        self._solve(["python>2.6.8"],
                    ["python-2.7.0[]"])

    def test_13_empty_string(self):
        """confirm that we can use empty string to match unmatched versions"""
        config.override("version_priority", {"python": ["", "2.7.0"]})
        self._solve(["python"],
                    ["python-2.6.8[]"])
        self._solve(["python", "!python-2.6.8"],
                    ["python-2.6.0[]"])
        self._solve(["python", "!python-2.6"],
                    ["python-2.5.2[]"])
        self._solve(["python>2.6.8"],
                    ["python-2.7.0[]"])

        config.override("version_priority", {"python": ["2.6.0", "",
                                                          "2.7.0"]})
        self._solve(["python"],
                    ["python-2.6.0[]"])
        self._solve(["python", "!python-2.6.0"],
                    ["python-2.6.8[]"])
        self._solve(["python", "!python-2.6"],
                    ["python-2.5.2[]"])
        self._solve(["python>2.6.8"],
                    ["python-2.7.0[]"])

    def test_14_false(self):
        """confirm that we can use False to match unmatched versions"""
        config.override("version_priority", {"python": [False, "2.7.0"]})
        self._solve(["python"],
                    ["python-2.6.8[]"])
        self._solve(["python", "!python-2.6.8"],
                    ["python-2.6.0[]"])
        self._solve(["python", "!python-2.6"],
                    ["python-2.5.2[]"])
        self._solve(["python>2.6.8"],
                    ["python-2.7.0[]"])

        config.override("version_priority", {"python": ["2.6.0", False,
                                                          "2.7.0"]})
        self._solve(["python"],
                    ["python-2.6.0[]"])
        self._solve(["python", "!python-2.6.0"],
                    ["python-2.6.8[]"])
        self._solve(["python", "!python-2.6"],
                    ["python-2.5.2[]"])
        self._solve(["python>2.6.8"],
                    ["python-2.7.0[]"])

    def test_15_requirement_1_deep(self):
        """Test setting of the version_priority for a required package 1 level
        deep
        """
        # python 2.5 is preferred...
        config.override("version_priority", {"python": [2.5]})

        # # so if we request python directly, we get 2.5...
        self._solve(["python"],
                    ["python-2.5.2[]"])

        # ...but if we request pyfoo, IT'S version is more important, and we
        # get 2.6
        self._solve(["pyfoo"],
                    ["python-2.6.8[]", "pyfoo-3.1.0[]"])

        # but if we make specifically python-2.6.0 prioritized, it will be used
        config.override("version_priority", {"python": ["2.6.0"]})
        self._solve(["pyfoo"],
                    ["python-2.6.0[]", "pyfoo-3.1.0[]"])

    def test_16_requirement_2_deep(self):
        """Test setting of the version_priority for a required package 2
        levels deep
        """
        config.override("version_priority", {"python": ["2.6.0", "2.5"]})
        self._solve(["pyodd"],
                    ["python-2.5.2[]", "pybah-5[]", "pyodd-2[]"])
        self._solve(["pyodd-2"],
                    ["python-2.5.2[]", "pybah-5[]", "pyodd-2[]"])
        self._solve(["pyodd-1"],
                    ["python-2.6.0[]", "pyfoo-3.1.0[]", "pyodd-1[]"])

        config.override("version_priority", {"pybah": ["4"],
                                               "pyfoo": ["3.0.0"],
                                               "python": ["2.6.0"]})
        self._solve(["pyodd"],
                    ["python-2.6.0[]", "pybah-4[]", "pyodd-2[]"])
        self._solve(["pyodd-2"],
                    ["python-2.6.0[]", "pybah-4[]", "pyodd-2[]"])
        self._solve(["pyodd-1"],
                    ["python-2.5.2[]", "pyfoo-3.0.0[]", "pyodd-1[]"])

    def test_17_multiple_false(self):
        """Make sure that multiple False / empty values raises an error
        """
        config.override("version_priority", {"python": ["2.6.0", False, False,
                                                          "2.5"]})
        self.assertRaises(ConfigurationError,
                          self._solve, ["python"], ["python-2.6.0[]"])

        config.override("version_priority", {"python": ["2.6.0", "", "",
                                                          "2.5"]})
        self.assertRaises(ConfigurationError,
                          self._solve, ["python"], ["python-2.6.0[]"])
        config.override("version_priority", {"python": ["2.6.0", "", False,
                                                          "2.5"]})
        self.assertRaises(ConfigurationError,
                          self._solve, ["python"], ["python-2.6.0[]"])

    def test_18_multiple_matches(self):
        """Test that if matches more than one, higher-priority is used
        """
        config.override("version_priority", {"python": ["2.7.0|2.6.8",
                                                          "2.5",
                                                          "2.6.8|2.6.0"]})
        self._solve(["python<2.7"],
                    ["python-2.6.8[]"])


if __name__ == '__main__':
    unittest.main()
