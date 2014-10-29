'''
Run unit tests.
'''


def setup_parser(parser, completions=False):
    parser.add_argument(
        "--persistent-file-store", action="store_true",
        help="test persistent file store")


def command(opts, parser, extra_arg_groups=None):
    from rez.cli._util import get_test_suites
    import unittest
    import sys
    import os

    os.environ["__REZ_SELFTEST_RUNNING"] = "1"

    tests = ["persistent_file_store"]

    suites = get_test_suites(opts, tests, "soma")
    test_suite = unittest.TestSuite(suites)
    result = unittest.TextTestRunner(verbosity=opts.verbose).run(test_suite)
    if not result.wasSuccessful():
        sys.exit(1)
