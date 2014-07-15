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
    parser.add_argument("--packages", action="store_true",
                        help="test package iteration and serialization")
    parser.add_argument("--animallogic", action="store_true",
                        help="test animal logic customisations")


def get_suites(opts):
    from rez.backport.importlib import import_module

    tests = ["shells", "solver", "formatter", "commands", "rex", "build",
             "context", "resources", "packages", "animallogic"]
    suites = []
    test_all = all([not getattr(opts, test) for test in tests])

    for test in tests:
        if test_all or getattr(opts, test):
            module = import_module('rez.tests.test_%s' % test)
            get_test_suites_func = getattr(module, 'get_test_suites')
            suites += get_test_suites_func()

    return suites


def command(opts, parser):
    import unittest
    import sys
    import os

    os.environ["__REZ_TEST_RUNNING"] = "1"

    suites = get_suites(opts)
    test_suite = unittest.TestSuite(suites)
    result = unittest.TextTestRunner(verbosity=opts.verbose).run(test_suite)
    if not result.wasSuccessful():
        sys.exit(1)
