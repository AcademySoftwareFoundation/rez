import sys
import os
import inspect
import unittest
import utils
utils.setup_pythonpath()
from rez.versions import Version, VersionRange, ExactVersion, ExactVersionSet, VersionError
import rez.versions

class VersionBaseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if cls is VersionBaseTest:
            raise unittest.SkipTest("Skip %s tests, it's a base class" % cls.__name__)
        super(VersionBaseTest, cls).setUpClass()

    def test_valid_init(self):
        for s in self.VALID:
            self.valid_init(s)

    def test_invalid_init(self):
        for s in self.INVALID:
            with self.assertRaises(VersionError):
                self.invalid_init(s)

class TestVersion(VersionBaseTest):
    VALID = ['', '1', '1.2.3', '3.5+', '3.5+<4', '1.2.a']
    INVALID = ['1.02',  # padded
               '3.5+<',  # missing upper bound
               '3.5+4',  # invalid
               '4.0+<3',  # upper bound is lower than lower bound
               '1+<1.0',  # upper bound is lower than lower bound (somewhat confusing case)
               ]

    def valid_init(self, s):
        Version(s)

    def invalid_init(self, s):
        Version(s)

    def test_comparision(self):
        self.assertTrue(Version('1.0') < Version('1.1'))
        self.assertTrue(Version('1') < Version('1.0'))
        self.assertTrue(Version('0') < Version('1'))

        self.assertTrue(Version('1.1') > Version('1.0'))
        self.assertTrue(Version('1.0') > Version('1'))

        self.assertFalse(Version('1.2') < Version('1.0+'))
        # FIXME: shouldn't > test upper bounds?
        self.assertTrue(Version('1.2') > Version('1.0+'))
    
        self.assertTrue(Version('1.0') == Version('1.0'))
        self.assertTrue(Version('') == Version(''))
    
        self.assertTrue(Version('') < Version('1'))
        # FIXME: shouldn't > test upper bounds?
        self.assertFalse(Version('') > Version('1'))

    def test_contains(self):
        self.assertTrue(Version('1.0') in Version('1'))
        self.assertTrue(Version('1') in Version('1'))

        self.assertTrue(Version('1') not in Version('1.0'))
        self.assertTrue(Version('1.2') in Version('1.0+'))

        self.assertTrue(Version('1.0+') not in Version('1.0'))

class TestVersionRange(VersionBaseTest):
    VALID = ['1|2', '1+<1.5|2.1', '1.0|2+<3.0'] + TestVersion.VALID
    INVALID = TestVersion.INVALID

    def valid_init(self, s):
        VersionRange(s)

    def invalid_init(self, s):
        VersionRange(s)

    def test_comparision(self):
        self.assertTrue(VersionRange('1|2') == VersionRange('2|1'))

    def test_contains(self):
        # overlapping
        for cls in [Version, ExactVersion]:
            self.assertTrue(cls('3.0') in VersionRange('2.0|1+<4'))
            self.assertTrue(cls('2') in VersionRange('1|2'))
    
            self.assertFalse(cls('1') in VersionRange('1.0'))
            self.assertTrue(cls('1.2') in VersionRange('1.0+'))
    
            self.assertTrue(cls('1') in VersionRange(''))
            self.assertTrue(cls('') in VersionRange(''))

    def test_boolean(self):
        self.assertEqual(VersionRange('1+<3').get_intersection(VersionRange('2+<4')),
                         VersionRange('2+<3'))
        no_intersect = VersionRange('1+<2').get_intersection(VersionRange('3+<4'))
        self.assertFalse(no_intersect.is_any())
        self.assertTrue(no_intersect.is_none())
        self.assertFalse(no_intersect)

class TestExactVersion(VersionBaseTest):
    VALID = ['1', '1.2.3', '1.2.a', '']
    INVALID = ['3.5+',
               '3.5+<4',
               '1.02',  # padded
               '3.5+<',  # missing upper bound
               '3.5+4',  # invalid
               '4.0+<3',  # upper bound is lower than lower bound
               '1+<1.0',  # upper bound is lower than lower bound (somewhat confusing case)
               ]

    def valid_init(self, s):
        ExactVersion(s)

    def invalid_init(self, s):
        ExactVersion(s)

    def test_comparision(self):
        self.assertTrue(ExactVersion('1.0') < ExactVersion('1.1'))
        self.assertTrue(ExactVersion('1') < ExactVersion('1.0'))
        self.assertTrue(ExactVersion('0') < ExactVersion('1'))

        self.assertTrue(ExactVersion('1.1') > ExactVersion('1.0'))
        self.assertTrue(ExactVersion('1.0') > ExactVersion('1'))

        self.assertTrue(ExactVersion('1.0') == ExactVersion('1.0'))


        self.assertTrue(ExactVersion('1.0') < Version('1.1'))
        self.assertTrue(ExactVersion('1') < Version('1.0'))
        self.assertTrue(ExactVersion('0') < Version('1'))

        self.assertTrue(ExactVersion('1.1') > Version('1.0'))
        self.assertTrue(ExactVersion('1.0') > Version('1'))

        self.assertTrue(ExactVersion('1.0') == Version('1.0'))

    def test_contains(self):
        # an exact version contains only itself
        self.assertFalse(ExactVersion('1.0') in ExactVersion('1'))
        self.assertTrue(ExactVersion('1') in ExactVersion('1'))
        self.assertFalse(ExactVersion('1') in ExactVersion('1.0'))

class TestLabelVersion(VersionBaseTest):
    VALID = ['foo', 'Bar', 'this_that']
    INVALID = ['foo-bar',
               'this.that',
               ]

    def valid_init(self, s):
        ExactVersion(s)

    def invalid_init(self, s):
        ExactVersion(s)

    def test_comparision(self):
        # FIXME: need to add basic comparision for label versions
        self.assertTrue(ExactVersion('aaa') < ExactVersion('bbb'))
        self.assertTrue(ExactVersion('Foo') == ExactVersion('Foo'))

    def test_methods(self):
        self.assertFalse(ExactVersion('aaa').is_inexact())
        self.assertFalse(ExactVersion('aaa').is_any())

#     def test_contains(self):
#         # an exact version contains only itself
#         self.assertFalse(ExactVersion('1.0') in ExactVersion('1'))
#         self.assertTrue(ExactVersion('1') in ExactVersion('1'))
#         self.assertFalse(ExactVersion('1') in ExactVersion('1.0'))

class TestExactVersionSet(VersionBaseTest):
    VALID = ['foo|Bar', ['foo', 'bar']] + TestLabelVersion.VALID + TestExactVersion.VALID
    INVALID = TestLabelVersion.INVALID + TestExactVersion.INVALID

    def valid_init(self, s):
        ExactVersionSet(s)

    def invalid_init(self, s):
        ExactVersionSet(s)

    def test_comparision(self):
        self.assertTrue(ExactVersionSet('foo|Bar') == ExactVersionSet('Bar|foo'))

    def test_contains(self):
        # overlapping
        self.assertTrue(ExactVersion('3.0') in ExactVersionSet('2.0|3.0'))
        self.assertTrue(ExactVersion('2') in ExactVersionSet('1|2'))

        self.assertFalse(ExactVersion('1') in ExactVersionSet('1.0'))
        self.assertTrue(ExactVersion('foo') in ExactVersionSet('foo'))

    def test_boolean(self):
        self.assertEqual(ExactVersionSet('foo|Bar').get_intersection(ExactVersionSet('foo')),
                         ExactVersionSet('foo'))
        no_intersect = ExactVersionSet('foo').get_intersection(ExactVersionSet('bar'))
        self.assertFalse(no_intersect.is_any())
        self.assertTrue(no_intersect.is_none())
        self.assertFalse(no_intersect)

# if __name__ == '__main__':
#     nose.main()
if __name__ == '__main__':
    unittest.main()
