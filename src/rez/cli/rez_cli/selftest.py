'''
Run unit tests.
'''


def setup_parser(parser, completions=False):
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
    parser.add_argument("--release", action="store_true",
                        help="test the release system")
    parser.add_argument("--context", action="store_true",
                        help="test resolved contexts")
    parser.add_argument("--resources", action="store_true",
                        help="test resource iteration and serialization")
    parser.add_argument("--packages", action="store_true",
                        help="test package iteration and serialization")
    parser.add_argument("--config", action="store_true",
                        help="test configuration settings")
    parser.add_argument("--completion", action="store_true",
                        help="test completions")
    parser.add_argument("--suites", action="store_true",
                        help="test suites")
    parser.add_argument("--version", action="store_true",
                        help="test versions")


def command(opts, parser, extra_arg_groups=None):
    from rez.cli._util import get_test_suites
    import unittest
    import sys
    import os

    os.environ["__REZ_SELFTEST_RUNNING"] = "1"

    tests = ["shells", "solver", "formatter", "commands", "rex", "build",
             "release", "context", "resources", "packages", "config",
             "completion", "suites", "version"]

    suites = get_test_suites(opts, tests)
    test_suite = unittest.TestSuite(suites)
    result = unittest.TextTestRunner(verbosity=opts.verbose).run(test_suite)
    if not result.wasSuccessful():
        sys.exit(1)
