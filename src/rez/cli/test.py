'''
Run unit tests
'''

def setup_parser(parser):
    parser.add_argument("--shells", action="store_true",
                        help="test shell invocation")
    parser.add_argument("--solver", action="store_true",
                        help="test package resolving algorithm")
    parser.add_argument("--formatter", action="store_true",
                        help="test rex string formatting")
    parser.add_argument("--commands", action="store_true",
                        help="test package commands")
    parser.add_argument("--rex", action="store_true",
                        help="test the rex command generator API")
    parser.add_argument("--build", action="store_true",
                        help="test the build system")
    parser.add_argument("--context", action="store_true",
                        help="test resolved contexts")
    parser.add_argument("--resources", action="store_true",
                        help="test resource iteration and serialization")
    # TODO: add this to top-level parser
    parser.add_argument("-v", "--verbosity", type=int, default=2,
                        help="set verbosity level")


def get_suites(opts):
    suites = []
    test_all = \
        (not opts.shells) and \
        (not opts.solver) and \
        (not opts.formatter) and \
        (not opts.commands) and \
        (not opts.rex) and \
        (not opts.build) and \
        (not opts.context) and \
        (not opts.resources)

    if opts.shells or test_all:
        from rez.tests.test_shells import get_test_suites
        suites += get_test_suites()

    if opts.solver or test_all:
        from rez.tests.test_solver import get_test_suites
        suites += get_test_suites()

    if opts.formatter or test_all:
        from rez.tests.test_formatter import get_test_suites
        suites += get_test_suites()

    if opts.commands or test_all:
        from rez.tests.test_commands import get_test_suites
        suites += get_test_suites()

    if opts.rex or test_all:
        from rez.tests.test_rex import get_test_suites
        suites += get_test_suites()

    if opts.build or test_all:
        from rez.tests.test_build import get_test_suites
        suites += get_test_suites()

    if opts.context or test_all:
        from rez.tests.test_context import get_test_suites
        suites += get_test_suites()

    if opts.resources or test_all:
        from rez.tests.test_resources import get_test_suites
        suites += get_test_suites()

    return suites


def command(opts, parser):
    import unittest
    import sys
    import os

    os.environ["__REZ_TEST_RUNNING"] = "1"

    suites = get_suites(opts)
    test_suite = unittest.TestSuite(suites)
    result = unittest.TextTestRunner(verbosity=opts.verbosity).run(test_suite)
    if not result.wasSuccessful():
        sys.exit(1)
