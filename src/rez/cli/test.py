'''
Run tests listed in a package's definition file.
'''
from __future__ import print_function


def setup_parser(parser, completions=False):
    parser.add_argument(
        "-l", "--list", action="store_true",
        help="list package's tests and exit")
    parser.add_argument(
        "--paths", type=str, default=None,
        help="set package search path")
    parser.add_argument(
        "--nl", "--no-local", dest="no_local", action="store_true",
        help="don't load local packages")
    PKG_action = parser.add_argument(
        "--extra-packages", nargs='+', metavar="PKG",
        help="extra packages to add to test environment")
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
    from rez.config import config
    import os.path
    import sys

    if opts.paths is None:
        pkg_paths = (config.nonlocal_packages_path
                     if opts.no_local else None)
    else:
        pkg_paths = opts.paths.split(os.pathsep)
        pkg_paths = [os.path.expanduser(x) for x in pkg_paths if x]

    runner = PackageTestRunner(package_request=opts.PKG,
                               package_paths=pkg_paths,
                               extra_package_requests=opts.extra_packages,
                               verbose=True)

    test_names = runner.get_test_names()
    if not test_names:
        uri = runner.get_package().uri
        print("No tests found in %s" % uri, file=sys.stderr)
        sys.exit(0)

    if opts.list:
        print('\n'.join(test_names))
        sys.exit(0)

    if opts.TEST:
        run_test_names = opts.TEST
    else:
        run_test_names = test_names

    for test_name in run_test_names:
        returncode = runner.run_test(test_name)

        if returncode:
            sys.exit(returncode)
