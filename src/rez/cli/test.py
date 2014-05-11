'''
Run unit tests
'''

def setup_parser(parser):
    parser.add_argument("--shells", action="store_true",
                        help="test shell invocation")
    parser.add_argument("--solver", action="store_true",
                        help="test package resolving algorithm")
    parser.add_argument("--cli", action="store_true",
                        help="test commandline tools")
    parser.add_argument("--formatter", action="store_true",
                        help="test rex string formatting")
    parser.add_argument("--commands", action="store_true",
                        help="test package commands")
    parser.add_argument("--rex", action="store_true",
                        help="test the rex command generator API")
    parser.add_argument("--build", action="store_true",
                        help="test the build system")
    # TODO: add this to top-level parser
    parser.add_argument("-v", "--verbosity", type=int, default=2,
                        help="set verbosity level")


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
    # FIXME: leaving this here from Allan's branch, but this import seems unused...
    from rez.settings import settings
    import unittest
    import sys
    suites = get_suites(opts)
    test_suite = unittest.TestSuite(suites)
    result = unittest.TextTestRunner(verbosity=opts.verbosity).run(test_suite)
    if not result.wasSuccessful():
        sys.exit(1)
