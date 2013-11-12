import sys
import os
import inspect
# hack this until we get a top-level test util module
curr_dir = os.path.dirname(inspect.getfile(inspect.currentframe()))
sys.path.insert(0, os.path.join(curr_dir, '..', 'python'))
from rez.versions import Version, VersionRange, VersionError
import rez.versions
print rez.versions.__file__
import nose
from nose.tools import raises

class TestVersion(object):
    VALID = ['', '1', '1.2.3', '3.5+', '3.5+<4', '1.2.a']
    INVALID = ['1.02',  # padded
               '3.5+<',  # missing upper bound
               '3.5+4',  # invalid
               '4.0+<3',  # upper bound is lower than lower bound
               '1+<1.0',  # upper bound is lower than lower bound (somewhat confusing case)
               ]

    def valid_init(self, s):
        Version(s)

    @raises(VersionError)
    def invalid_init(self, s):
        Version(s)

    def test_valid_init(self):
        for s in self.VALID:
            yield self.valid_init, s

    def test_invalid_init(self):
        for s in self.INVALID:
            yield self.invalid_init, s

    def test_comparision(self):
        assert Version('1.0') < Version('1.1')
        assert Version('1') < Version('1.0')
        assert Version('0') < Version('1')

        assert Version('1.1') > Version('1.0')
        assert Version('1.0') > Version('1')

        assert (Version('1.2') < Version('1.0+')) is False
        # FIXME: shouldn't > test upper bounds?
        assert Version('1.2') > Version('1.0+')
    
        assert Version('1.0') == Version('1.0')
        assert Version('') == Version('')
    
        assert Version('') < Version('1')
        # FIXME: shouldn't > test upper bounds?
        assert (Version('') > Version('1')) is False

    def test_contains(self):
        assert Version('1.0') in Version('1')
        assert Version('1') in Version('1')

        assert Version('1') not in Version('1.0')
        assert Version('1.2') in Version('1.0+')

        assert Version('1.0+') not in Version('1.0')

class TestVersionRange(object):
    VALID = ['1|2', '1+<1.5|2.1', '1.0|2+<3.0']

    def valid_init(self, s):
        VersionRange(s)

    @raises(VersionError)
    def invalid_init(self, s):
        VersionRange(s)

    def test_valid_init(self):
        # valid version strings should be valid for ranges too
        for s in TestVersion.VALID:
            yield self.valid_init, s

        for s in self.VALID:
            yield self.valid_init, s

    def test_invalid_init(self):
        # invalid version strings should be invalid for ranges too
        for s in TestVersion.INVALID:
            yield self.invalid_init, s

    def test_comparision(self):
        assert VersionRange('1|2') == VersionRange('2|1')

    def test_contains(self):
        # overlapping
        assert Version('3.0') in VersionRange('2.0|1+<4')
        assert Version('2') in VersionRange('1|2')

        assert Version('1') not in VersionRange('1.0')
        assert Version('1.2') in VersionRange('1.0+')


if __name__ == '__main__':
    nose.main()