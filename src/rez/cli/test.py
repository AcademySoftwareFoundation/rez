'''
Run tests listed in a package's definition file.
'''


def setup_parser(parser, completions=False):
    parser.add_argument(
        "-l", "--list", action="store_true",
        help="list package's tests and exit")
    PKG_action = parser.add_argument(
        "PKG",
        help="package run tests on")
    parser.add_argument(
        "TEST", nargs='*',
        help="tests to run (run all if not provided)")

    if completions:
        from rez.cli._complete_util import PackageCompleter
        PKG_action.completer = PackageCompleter


def command(opts, parser, extra_arg_groups=None):
    from rez.package_test import PackageTestRunner
    import sys

    runner = PackageTestRunner(package_request=opts.PKG,
                               verbose=True)

    test_names = runner.get_test_names()
    if not test_names:
        uri = runner.get_package().uri
        print >> sys.stderr, "No tests found in %s" % uri
        sys.exit(0)

    if opts.list:
        print '\n'.join(test_names)
        sys.exit(0)

    if opts.TEST:
        run_test_names = opts.TEST
    else:
        run_test_names = test_names

    for test_name in run_test_names:
        returncode = runner.run_test(test_name)

        if returncode:
            sys.exit(returncode)
