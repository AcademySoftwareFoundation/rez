from rez.version import Version, VersionRange
#from rez.resolved_context import ResolvedContext
from rez.packages import PackageStatement, PackageRangeStatement
from rez.exceptions import RezError, PkgConflictError
from rez.resolve import PackageRequestList
import unittest
import os.path



class TestResolve(unittest.TestCase):
    def __init__(self, fn):
        unittest.TestCase.__init__(self, fn)
        path = os.path.dirname(__file__)
        self.packages_path = os.path.join(path, "data", "packages")

    def _resolve(self, packages):
        return ResolvedContext(packages,
                               caching=False,
                               add_implicit_packages=False,
                               add_bootstrap_path=False,
                               package_paths=[self.packages_path])

    def _test_resolve(self, packages, expected_resolve=None):
        print
        print "request: %s" % ' '.join(packages)

        if expected_resolve is None:
            exc_type = RezError
        else:
            exc_type = None
            print "expecting: %s" % ' '.join(expected_resolve)

        try:
            r = self._resolve(packages)
        except exc_type as e:
            print str(e)
            raise e

        res_strs = [x.short_name() for x in r.resolved_packages]
        res_pkgs = [PackageStatement(x) for x in res_strs]
        print "resolved: %s" % ' '.join(str(x) for x in res_pkgs)

        exp_res_pkgs = [PackageStatement(x) for x in expected_resolve]
        res_set = set(res_pkgs)
        exp_res_set = set(exp_res_pkgs)
        self.assertTrue(res_set == exp_res_set)

    def test_resolve_1(self):
        self._test_resolve(["python"],
                           ["python-2.7.0"])
        self._test_resolve(["python-2.6"],
                           ["python-2.6.8"])
        self._test_resolve(["python-2.6", "!python-2.6.8"],
                           ["python-2.6.0"])
        self._test_resolve(["python-2.6", "python-2.6.5+"],
                           ["python-2.6.8"])
        self._test_resolve(["python", "python-0+<2.6"],
                           ["python-2.5.2"])
        self._test_resolve(["python", "python-0+<2.6.8"],
                           ["python-2.6.0"])
        self._test_resolve(["python", "~python-2.7+"],
                           ["python-2.7.0"])
        self._test_resolve(["~python-2+"],
                           [])
        self._test_resolve(["~python"],
                           [])

        self.assertRaises(PkgConflictError, self._test_resolve,
                          ["python-2.6", "python-2.7"])
        self.assertRaises(PkgConflictError, self._test_resolve,
                          ["python-2.7", "!python-2.7+"])
        self.assertRaises(PkgConflictError, self._test_resolve,
                          ["python-2.5", "~python-2.6"])

    def test_resolve_2(self):
        self._test_resolve(["pyfoo"],
                           ["pyfoo-3.1.0", "python-2.6.8"])
        self._test_resolve(["python", "pyfoo"],
                           ["pyfoo-3.1.0", "python-2.6.8"])

        self.assertRaises(PkgConflictError, self._test_resolve,
                          ["pyfoo-3.1+", "python-2.5.1"])

    def test_resolve_3(self):
        self._test_resolve(["pybah"],
                           ["pybah-5", "python-2.5.2"])
        self._test_resolve(["pybah", "pyfoo"],
                           ["pybah-5", "pyfoo-3.0.0", "python-2.5.2"])
        self._test_resolve(["pyfoo", "pybah"],
                           ["pyfoo-3.1.0", "pybah-4", "python-2.6.8"])
        self._test_resolve(["pyfoo", "pybah", "!python-2.6.8"],
                           ["pyfoo-3.1.0", "pybah-4", "python-2.6.0"])

        self.assertRaises(PkgConflictError, self._test_resolve,
                          ["pyfoo-3.1", "pybah-5"])
        self.assertRaises(PkgConflictError, self._test_resolve,
                          ["pyfoo", "pybah", "~python-2.7"])


def get_test_suites():
    suites = []
    suite = unittest.TestSuite()
    #suite.addTest(TestResolve("test_resolve_1"))
    #suite.addTest(TestResolve("test_resolve_2"))
    #suite.addTest(TestResolve("test_resolve_3"))
    suites.append(suite)
    return suites
