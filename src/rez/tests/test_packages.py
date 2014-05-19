from rez.vendor.version.requirement import Requirement
from rez.packages import iter_packages
import rez.vendor.unittest2 as unittest
from rez.tests.util import TestBase
import itertools
import os.path

ALL_PACKAGES = [
    'bahish-1', 'bahish-2', 'nada', 'nopy-2.1', 'pybah-4', 'pybah-5',
    'pydad-1', 'pydad-2', 'pydad-3', 'pyfoo-3.0.0', 'pyfoo-3.1.0', 'pymum-1',
    'pymum-2', 'pymum-3', 'pyodd-1', 'pyodd-2', 'pyson-1', 'pyson-2',
    'pysplit-5', 'pysplit-6', 'pysplit-7', 'python-2.5.2', 'python-2.6.0',
    'python-2.6.8', 'python-2.7.0']

def _to_names(it):
    return [p.qualified_name for p in it]

class TestSolver(TestBase):
    @classmethod
    def setUpClass(cls):
        path = os.path.dirname(__file__)
        packages_path = os.path.join(path, "data", "solver", "packages")

        cls.settings = dict(
            packages_path=[packages_path])

    def test_1(self):
        all_packages = _to_names(iter_packages())
        self.assertEqual(all_packages, ALL_PACKAGES)

        res = _to_names(iter_packages(name='nada'))
        self.assertEqual(res, ['nada'])

        res = _to_names(iter_packages(name='python'))
        self.assertEqual(res, ['python-2.5.2', 'python-2.6.0', 'python-2.6.8',
                               'python-2.7.0'])
