"""
test dependency resolving algorithm
"""
from __future__ import print_function

from rez.vendor.version.requirement import Requirement
from rez.solver import Solver, Cycle, SolverStatus
from rez.config import config
import unittest
from rez.tests.util import TestBase
import itertools


solver_verbosity = 1


class TestSolver(TestBase):
    @classmethod
    def setUpClass(cls):
        packages_path = cls.data_path("solver", "packages")
        cls.packages_path = [packages_path]
        cls.settings = dict(
            packages_path=cls.packages_path,
            package_filter=None)

    def _create_solvers(self, reqs):
        s1 = Solver(reqs,
                    self.packages_path,
                    optimised=True,
                    verbosity=solver_verbosity)
        s2 = Solver(reqs,
                    self.packages_path,
                    optimised=False,
                    verbosity=solver_verbosity)

        s_perms = []
        perms = itertools.permutations(reqs)
        for reqs_ in perms:
            s = Solver(reqs_,
                       self.packages_path,
                       optimised=True,
                       verbosity=solver_verbosity)
            s_perms.append(s)

        return (s1, s2, s_perms)

    def _solve(self, packages, expected_resolve):
        print()
        reqs = [Requirement(x) for x in packages]
        s1, s2, s_perms = self._create_solvers(reqs)

        s1.solve()
        self.assertEqual(s1.status, SolverStatus.solved)

        # ephemeral order doesn't matter, hence the sort
        resolve = (
            [str(x) for x in s1.resolved_packages]
            + sorted(str(x) for x in s1.resolved_ephemerals)
        )

        print()
        print("request: %s" % ' '.join(packages))
        print("expecting: %s" % ' '.join(expected_resolve))
        print("result: %s" % ' '.join(str(x) for x in resolve))
        self.assertEqual(resolve, expected_resolve)

        print("checking that unoptimised solve matches optimised...")
        s2.solve()
        self.assertEqual(s2.status, SolverStatus.solved)
        resolve2 = (
            [str(x) for x in s2.resolved_packages]
            + sorted(str(x) for x in s2.resolved_ephemerals)
        )
        self.assertEqual(resolve2, resolve)

        print("checking that permutations also succeed...")
        for s in s_perms:
            s.solve()
            self.assertEqual(s.status, SolverStatus.solved)

        return s1

    def _fail(self, *packages):
        print()
        reqs = [Requirement(x) for x in packages]
        s1, s2, s_perms = self._create_solvers(reqs)

        s1.solve()
        print()
        print("request: %s" % ' '.join(packages))
        print("expecting failure")
        self.assertEqual(s1.status, SolverStatus.failed)
        print("result: %s" % str(s1.failure_reason()))

        print("checking that unoptimised solve fail matches optimised...")
        s2.solve()
        self.assertEqual(s2.status, SolverStatus.failed)
        self.assertEqual(s1.failure_reason(), s2.failure_reason())

        print("checking that permutations also fail...")
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
        self._solve([".foo-1"],
                    [".foo-1"])
        self._solve(["!.bah"],
                    [])
        self._solve(["!.bah-2.5+"],
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
        self._fail(".foo-1", ".foo-2")
        self._fail(".foo-2.5", "!.foo-2")

    def test_04(self):
        """Basic failures."""
        self._fail("pybah", "!python")
        self._fail("pyfoo-3.1", "python-2.7+")
        self._fail("pyodd<2", "python-2.7")
        self._fail("nopy", "python-2.5.2")

    def test_05(self):
        """More complex failures."""
        self._fail("bahish", "pybah<5")
        self._fail("pybah-4", "pyfoo-3.0")

    def test_06(self):
        """Basic solves involving multiple packages."""
        self._solve(["nada", "nopy"],
                    ["nada[]", "nopy-2.1[]"])
        self._solve(["pyfoo"],
                    ["python-2.6.8[]", "pyfoo-3.1.0[]"])
        self._solve(["pyfoo-3.0"],
                    ["python-2.5.2[]", "pyfoo-3.0.0[]", ".eek-3+"])
        self._solve(["pyfoo-3.0", ".eek-4.5"],
                    ["python-2.5.2[]", "pyfoo-3.0.0[]", ".eek-4.5"])
        self._solve(["pybah"],
                    ["python-2.5.2[]", "pybah-5[]"])
        self._solve(["nopy", "python"],
                    ["nopy-2.1[]", "python-2.7.0[]"])
        self._solve(["pybah", "!python-2.5"],
                    ["python-2.6.8[]", "pybah-4[]", ".eek-1"])
        self._solve(["pybah", "!python-2.5", "python<2.6.8"],
                    ["python-2.6.0[]", "pybah-4[]", ".eek-1"])
        self._solve(["python", "pybah"],
                    ["python-2.6.8[]", "pybah-4[]", ".eek-1"])

    def test_07(self):
        """More complex solves."""
        self._solve(["python", "pyodd"],
                    ["python-2.6.8[]", "pybah-4[]", "pyodd-2[]", ".eek-1"])
        self._solve(["pybah", "pyodd"],
                    ["python-2.5.2[]", "pybah-5[]", "pyodd-2[]"])
        self._solve(["pysplit", "python-2.5"],
                    ["pysplit-5[]", "python-2.5.2[]"])
        self._solve(["~python<2.6", "pysplit"],
                    ["pysplit-5[]"])
        self._solve(["python", "bahish", "pybah"],
                    ["python-2.5.2[]", "pybah-5[]", "bahish-2[]"])
        self._solve([".foo-2.5+", ".foo-2"],
                    [".foo-2.5+<2_"])

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

    def test_11_variant_splitting(self):
        self._solve(["test_variant_split_start"],
                    ["test_variant_split_end-1.0[1]",
                     "test_variant_split_mid2-2.0[0]",
                     "test_variant_split_start-1.0[1]"])


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
