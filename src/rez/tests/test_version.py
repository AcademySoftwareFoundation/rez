"""
unit tests for 'version' module
"""
import rez.vendor.unittest2 as unittest
from rez.vendor.version.test import TestVersionSchema


class TestVersions(TestVersionSchema):
    pass


if __name__ == '__main__':
    unittest.main()


