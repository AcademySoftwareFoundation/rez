"""
test package info extraction
"""

from rez.cli.info import get_package_info
from rez.packages_ import get_developer_package
import os
import rez.vendor.unittest2 as unittest


class InfoOptions:
    path = os.getcwd()
    separator = ' '
    raw = False
    INFO_ARGS = []

    def __init__(self, path, args, separator=" ", raw=False):
        self.path = path
        self.separator = separator
        self.raw = raw
        self.INFO_ARGS = args


class TestInfo(unittest.TestCase):
    package_py = get_developer_package(os.path.join(os.path.dirname(__file__), "data", "info", "py"))
    package_yaml = get_developer_package(os.path.join(os.path.dirname(__file__), "data", "info", "yaml"))

    def test_py_basic(self):
        version = get_package_info(self.package_py, ['version'], " ", False)
        self.assertEqual(version, '0.8.al3.1.0')

        name_description = get_package_info(self.package_py, ['name', 'description'], " ", False)
        self.assertEqual(name_description, 'usdBase\n'
                                           'universal scene description')

    def test_yaml_basic(self):
        version = get_package_info(self.package_yaml, ['version'], " ", False)
        self.assertEqual(version, '2.8.0.11')

        name_description = get_package_info(self.package_yaml, ['name', 'description'], " ", False)
        self.assertEqual(name_description, 'rez\n'
                                           'Rez is a suite of tools for resolving a list of packages')

    def test_py_lists(self):
        requires = get_package_info(self.package_py, ['requires'], " ", False)
        self.assertEqual(requires, 'stdlib-4.8 tbb-4.4 ilmbase-2.2')

        requires_comma_separated = get_package_info(self.package_py, ['requires'], " , ", False)
        self.assertEqual(requires_comma_separated, 'stdlib-4.8 , tbb-4.4 , ilmbase-2.2')

        requires_raw = get_package_info(self.package_py, ['requires'], " ", raw=True)
        self.assertEqual(requires_raw, "['stdlib-4.8', 'tbb-4.4', 'ilmbase-2.2']")

    def test_yaml_lists(self):
        requires = get_package_info(self.package_yaml, ['requires'], " ", False)
        self.assertEqual(requires, 'setuptools python')

        requires_comma_separated = get_package_info(self.package_yaml, ['requires'], " , ", False)
        self.assertEqual(requires_comma_separated, 'setuptools , python')

        requires_raw = get_package_info(self.package_yaml, ['requires'], " ", raw=True)
        self.assertEqual(requires_raw, "['setuptools', 'python']")

    def test_py_nested_lists(self):
        variants = get_package_info(self.package_py, ['variants'], " ", False)
        self.assertEqual(variants, 'AL_boost-1.55.0 AL_boost_python-1.55\n'
                                   'boost-1.55.0 boost_python-1.55')

        variants_comma_separated = get_package_info(self.package_py, ['variants'], " , ", False)
        self.assertEqual(variants_comma_separated, 'AL_boost-1.55.0 , AL_boost_python-1.55\n'
                                                   'boost-1.55.0 , boost_python-1.55')

        variants_raw = get_package_info(self.package_py, ['variants'], " ", raw=True)
        self.assertEqual(variants_raw, "[['AL_boost-1.55.0', 'AL_boost_python-1.55'], "
                                       "['boost-1.55.0', 'boost_python-1.55']]")

    def test_yaml_nested_lists(self):
        variants = get_package_info(self.package_yaml, ['variants'], " ", False)
        self.assertEqual(variants, 'CentOS-6.2+<7 python-2.6\n'
                                   'CentOS-6.2+<7 python-2.7')

        variants_comma_separated = get_package_info(self.package_yaml, ['variants'], " # ", False)
        self.assertEqual(variants_comma_separated, 'CentOS-6.2+<7 # python-2.6\n'
                                                   'CentOS-6.2+<7 # python-2.7')

        variants_raw = get_package_info(self.package_yaml, ['variants'], " ", raw=True)
        self.assertEqual(variants_raw, "[['CentOS-6.2+<7', 'python-2.6'], ['CentOS-6.2+<7', 'python-2.7']]")

    def test_invalid_result(self):
        wrong_field = get_package_info(self.package_yaml, ['wrong_filed'], " ", False)
        self.assertEqual(wrong_field , '')

    def test_source_code(self):
        commands = get_package_info(self.package_py, ['commands'], " ", False)
        self.assertEqual(commands, "prependenv('PATH', '{root}/bin')\n"
                                   "prependenv('PYTHONPATH', '{root}/lib/python')\n"
                                   "prependenv('LD_LIBRARY_PATH', '{root}/lib')")
