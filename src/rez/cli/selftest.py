'''
Run unit tests.
'''

import inspect
import os
import rez.vendor.argparse as argparse
from pkgutil import iter_modules
from fnmatch import fnmatch


cli_dir = os.path.dirname(inspect.getfile(inspect.currentframe()))
src_rez_dir = os.path.dirname(cli_dir)
tests_dir = os.path.join(src_rez_dir, 'tests')

all_tests = []
selected_tests = []


def setup_parser(parser, completions=False):
    # make an Action that will append the appropriate test to the "--test" arg
    class AddTestModuleAction(argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):
            name = option_string.lstrip('-')
            selected_tests.append(name)

    # find unit tests
    tests = []
    prefix = "test_"
    for importer, name, ispkg in iter_modules([tests_dir]):
        if not ispkg and name.startswith(prefix):
            module = importer.find_module(name).load_module(name)
            name_ = name[len(prefix):]
            all_tests.append(name_)
            tests.append((name_, module))

    # create argparse entry for each unit test
    for name, module in sorted(tests):
        parser.add_argument(
            "--%s" % name, action=AddTestModuleAction, nargs=0,
            help=module.__doc__.strip().rstrip('.'))


def command(opts, parser, extra_arg_groups=None):
    import sys
    from rez.vendor.unittest2.main import main

    os.environ["__REZ_SELFTEST_RUNNING"] = "1"
    tests = sorted(selected_tests or all_tests)
    tests = [("rez.tests.test_%s" % x) for x in tests]

    argv = [sys.argv[0]] + tests
    main(module=None, argv=argv, verbosity=opts.verbose)
