"""
Just forwards on unit tests for 'version' module.
"""
import rez.vendor.unittest2 as unittest
from rez.vendor.version.test import TestVersionSchema


class TestVersions(TestVersionSchema):
    pass


def get_test_suites():
    suites = []
    suite = unittest.TestSuite()
    suite.addTest(TestVersions("test_token_strict_weak_ordering"))
    suite.addTest(TestVersions("test_version_strict_weak_ordering"))
    suite.addTest(TestVersions("test_token_comparisons"))
    suite.addTest(TestVersions("test_version_comparisons"))
    suite.addTest(TestVersions("test_version_range"))
    suite.addTest(TestVersions("test_containment"))
    suite.addTest(TestVersions("test_requirement_list"))
    suites.append(suite)
    return suites


if __name__ == '__main__':
    unittest.main()
