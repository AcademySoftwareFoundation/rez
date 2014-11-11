"""
Just forwards on unit tests for 'version' module.
"""
import rez.vendor.unittest2 as unittest
from rez.vendor.schema.test_schema import TestSchema


def get_test_suites():
    suites = []
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    tests = loader.loadTestsFromTestCase(TestSchema)
    suite.addTests(tests)
    suites.append(suite)
    return suites


if __name__ == '__main__':
    unittest.main()
