import unittest


def command(opts, parser=None):
    suites = []
    test_all = \
        (not opts.shells) and \
        (not opts.versions) and \
        (not opts.resolves) and \
        (not opts.cli)

    if opts.shells or test_all:
        from rez.tests.shells import get_test_suites
        suites += get_test_suites()

    if opts.versions or test_all:
        from rez.tests.versions import get_test_suites
        suites += get_test_suites()

    if opts.resolves or test_all:
        from rez.tests.resolves import get_test_suites
        suites += get_test_suites()

    if opts.cli or test_all:
        from rez.tests.cli import get_test_suites
        suites += get_test_suites()

    all_ = unittest.TestSuite(suites)
    unittest.TextTestRunner(verbosity=opts.verbosity).run(all_)
