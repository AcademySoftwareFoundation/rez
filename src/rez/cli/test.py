'''
Run tests listed in a package's definition file.
'''
import sys

import os

from rez.cli._main import run
from rez.config import config
from rez.exceptions import PackageMetadataError
from rez.package_serialise import dump_package_data
from rez.packages_ import get_developer_package
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
    parser.add_argument(
        "--env", dest="env", default=None,
        help="resolves the environment needed for running the tests and applies it in the current shell."
    )
    parser.add_argument(
        "--variant", dest="variant", default=0, type=int,
        help="variant number which should be used to set env. Works only with --env option"
    )
    PKG_action = parser.add_argument(
        "--extra-packages", nargs='+', metavar="PKG",
        help="extra packages to add to test environment")
    PKG_action = parser.add_argument(
        "PKG", nargs='?',
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

    pkg = get_package(os.getcwd())

    if pkg and is_dev_run(opts.PKG):
        prepare_dev_env_package(pkg)

    if opts.paths is None:
        pkg_paths = (config.nonlocal_packages_path
                     if opts.no_local else None)
    else:
        pkg_paths = opts.paths.split(os.pathsep)
        pkg_paths = [os.path.expanduser(x) for x in pkg_paths if x]

    pkg_request = "{name}-{version}".format(name=pkg.name, version=pkg.version) if pkg else opts.PKG
    runner = PackageTestRunner(package_request=pkg_request,
                               package_paths=pkg_paths,
                               extra_package_requests=opts.extra_packages,
                               verbose=True)

    test_names = runner.get_test_names()
    if not test_names:
        uri = runneir.package.uri
        print("No tests found in %s" % uri, file=sys.stderr)
        sys.exit(0)

    if opts.list:
        print('\n'.join(test_names))
        sys.exit(0)

    if opts.env and opts.env in test_names:
        runner.run_test_env(opts.variant, opts.env)
        sys.exit(0)
    elif opts.env:
        print >> sys.stderr, "Invalid ENV name. Possible choices: {choices}".format(choices=','.join(test_names))
        sys.exit(1)

    if opts.TEST:
        run_test_names = opts.TEST
    else:
        run_test_names = test_names

    for test_name in run_test_names:
        returncode = runner.run_test(test_name)

        if returncode:
            sys.exit(returncode)


def is_dev_run(name):
    """
    Decides if is dev_run, based on package name
    Args:
        name: name of package

    Returns: True or False
    """
    return not name or name == '.'


def get_package(path):
    """
    Function validates pkg name and indicates if tests were run in developer mode
    Args:
        path: path to the package

    Returns: Tuple of values (package_name, is_dev_run)
    """
    try:
        return get_developer_package(path)
    except PackageMetadataError:
        print >> sys.stderr, "Not a valid rez package. Make sure you are in package's root directory"
        return None


def prepare_dev_env_package(package):
    """
    Prepares dev environment for tests. If a package is not installed in in the local packages path
    or the tests on the package[py/yaml] are outdated, it installs the package
    or updates the package file with the new test targets.
    Args:
        package: package to be built
    """
    try:
        local_package_path = os.path.join(config.local_packages_path, package.name, str(package.version))
        local_package = get_developer_package(local_package_path)
    except PackageMetadataError:
        install_package_in_local_packages_path()
    else:
        update_package_in_local_packages_path(package, local_package)


def install_package_in_local_packages_path():
    """
    Installs the package in the local_packages_path (defined in config.local_packages_path)
    """
    original_args = sys.argv
    sys.argv = [original_args[0]] + ['-i']
    try:
        run("build")
    except SystemExit as exit_code:
        if exit_code.code:
            raise
    sys.argv = original_args


def update_package_in_local_packages_path(package, installed_package):
    """
    Updates tests package definition in installed packages path
    Args:
        package: package object of currently processed package
        installed_package: package object of installed package
    """
    if package.tests != installed_package.tests:
        data = installed_package.validated_data()
        data['tests'] = package.tests

        with open(installed_package.filepath, 'w') as f:
            dump_package_data(data, f)
