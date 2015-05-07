'''
Run unit tests.
'''

import inspect
import os
import rez.vendor.argparse as argparse

cli_dir = os.path.dirname(inspect.getfile(inspect.currentframe()))
src_rez_dir = os.path.dirname(cli_dir)
src_dir = os.path.dirname(src_rez_dir)
tests_dir = os.path.join(src_rez_dir, 'tests')

def setup_parser(parser, completions=False):
    parser.add_argument("-t", "--test", action="append",
                        help="a specific test module/class/method to run; may "
                             "be repeated multiple times; if not tests are "
                             "given, all tests are run")

    # add shorcut args, so you can do, ie:
    #     rez-selftest --resources
    # instead of:
    #     rez-selftest --test rez.test.test_resources

    # first, build a dict of test_modules, from name to package name
    test_modules = {}

    test_prefix = 'test_'
    for entry in os.listdir(tests_dir):
        if not entry.startswith(test_prefix):
            continue
        module_name = None

        path = os.path.join(tests_dir, entry)
        if os.path.isdir(path):
            if os.path.isfile(os.path.join(path, '__init__.py')):
                # it's a test package, add it
                module_name = entry
        elif entry.endswith('.py'):
            # it's a test module, add it
            module_name = os.path.splitext(entry)[0]

        if module_name:
            name = module_name[len(test_prefix):]
            package_name = 'rez.tests.%s' % module_name
            test_modules[name] = package_name

    # make an Action that will append the appropriate test to the "--test" arg
    class AddTestModuleAction(argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):
            #print '%r %r %r' % (namespace, values, option_string)
            name = option_string.lstrip('-')
            package_name = test_modules[name]
            if namespace.test is None:
                namespace.test = []
            namespace.test.append(package_name)

    # now, create a shortcut arg for each module...
    for name in sorted(test_modules):
        package_name = test_modules[name]
        parser.add_argument("--%s" % name, action=AddTestModuleAction, nargs=0,
                            help="test %s - shortcut for '--test %s'"
                                 % (name, package_name),)


def command(opts, parser, extra_arg_groups=None):
    import sys
    from rez.vendor.unittest2.main import main

    os.environ["__REZ_SELFTEST_RUNNING"] = "1"

    argv = [sys.argv[0]]
    if not opts.test:
        argv.extend(['discover', '--start-directory', src_dir])
    else:
        argv.extend(opts.test)

    main(module=None, argv=argv, verbosity=opts.verbose)
