from rez.settings import settings
import unittest
import sys



def get_suites(opts):
    suites = []
    test_all = \
        (not opts.shells) and \
        (not opts.solver) and \
        (not opts.cli) and \
        (not opts.formatter) and \
        (not opts.commands) and \
        (not opts.rex) and \
        (not opts.build)

    if opts.shells or test_all:
        from rez.tests.shells import get_test_suites
        suites += get_test_suites()

    if opts.solver or test_all:
        from rez.tests.solver import get_test_suites
        suites += get_test_suites()

    if opts.cli or test_all:
        from rez.tests.cli import get_test_suites
        suites += get_test_suites()

    if opts.formatter or test_all:
        from rez.tests.formatter import get_test_suites
        suites += get_test_suites()

    if opts.commands or test_all:
        from rez.tests.commands import get_test_suites
        suites += get_test_suites()

    if opts.rex or test_all:
        from rez.tests.rex import get_test_suites
        suites += get_test_suites()

    if opts.build or test_all:
        from rez.tests.build import get_test_suites
        suites += get_test_suites()

    return suites


def command(opts, parser=None):
    suites = get_suites(opts)
    test_suite = unittest.TestSuite(suites)
    result = unittest.TextTestRunner(verbosity=opts.verbosity).run(test_suite)
    if not result.wasSuccessful():
        sys.exit(1)
