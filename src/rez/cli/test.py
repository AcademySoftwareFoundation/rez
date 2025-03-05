# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


'''
Run tests listed in a package's definition file.
'''


def setup_parser(parser, completions=False):
    parser.add_argument(
        "-l", "--list", action="store_true",
        help="list package's tests and exit")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="dry-run mode: show what tests would have been run, but do not "
        "run them")
    parser.add_argument(
        "-s", "--stop-on-fail", action="store_true",
        help="stop on first test failure")
    parser.add_argument(
        "--inplace", action="store_true",
        help="run tests in the current environment. Any test whose requirements "
        "are not met by the current environment is skipped")
    PKG_action = parser.add_argument(
        "--extra-packages", nargs='+', metavar="PKG",
        help="extra packages to add to test environment")
    parser.add_argument(
        "--paths", type=str, default=None,
        help="set package search path")
    parser.add_argument(
        "--nl", "--no-local", dest="no_local", action="store_true",
        help="don't load local packages")
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

    # note that argparse doesn't support mutually exclusive arg groups
    if opts.inplace and (opts.extra_packages or opts.paths or opts.no_local):
        parser.error(
            "Cannot use --inplace in combination with "
            "--extra-packages/--paths/--no-local"
        )

    if opts.paths is None:
        pkg_paths = (config.nonlocal_packages_path
                     if opts.no_local else None)
    else:
        pkg_paths = opts.paths.split(os.pathsep)
        pkg_paths = [os.path.expanduser(x) for x in pkg_paths if x]

    if extra_arg_groups:
        if not opts.TEST or len(opts.TEST) > 1:
            parser.error(
                "You can only pass extra arguments to a single, specified test. "
                "Please rerun the command and specify a single test to run."
            )
        extra_arg_groups = extra_arg_groups[0]

    # run test(s)
    runner = PackageTestRunner(
        package_request=opts.PKG,
        package_paths=pkg_paths,
        extra_package_requests=opts.extra_packages,
        dry_run=opts.dry_run,
        stop_on_fail=opts.stop_on_fail,
        use_current_env=opts.inplace,
        verbose=2
    )

    test_names = runner.get_test_names()
    uri = runner.get_package().uri

    if not test_names:
        print("No tests found in %s" % uri, file=sys.stderr)
        sys.exit(0)

    if opts.list:
        if sys.stdout.isatty():
            print("Tests defined in %s:" % uri)

        print('\n'.join(test_names))
        sys.exit(0)

    run_test_names = runner.find_requested_test_names(opts.TEST)

    if not run_test_names:
        print(
            "No tests with 'default' run_on tag found in %s" % uri,
            file=sys.stderr
        )
        sys.exit(0)

    exitcode = 0

    for test_name in run_test_names:
        if not runner.stopped_on_fail:
            ret = runner.run_test(test_name, extra_test_args=extra_arg_groups)
            if ret and not exitcode:
                exitcode = ret

    print("\n")
    runner.print_summary()
    print('')

    sys.exit(exitcode)
