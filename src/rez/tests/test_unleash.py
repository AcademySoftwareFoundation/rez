from rez.tests.util import TestBase
import rez.vendor.unittest2 as unittest


class TestUnleash(TestBase):

    def test_nothing(self):

        pass


def get_test_suites():

    suites = []
    tests = [TestUnleash]

    for test in tests:
        suites.append(unittest.TestLoader().loadTestsFromTestCase(test))

    return suites


if __name__ == '__main__':

    unittest.main()

