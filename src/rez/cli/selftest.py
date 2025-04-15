# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Run unit tests. Use pytest if available.
"""

import os
import sys
import inspect
import argparse
import shutil
from pkgutil import iter_modules

try:
    import pytest  # noqa

    use_pytest = True
except ImportError:
    use_pytest = False


cli_dir = os.path.dirname(inspect.getfile(inspect.currentframe()))
src_rez_dir = os.path.dirname(cli_dir)
tests_dir = os.path.join(src_rez_dir, "tests")

all_module_tests = []


def setup_parser(parser, completions=False):
    parser.add_argument(
        "tests",
        metavar="NAMED_TEST",
        default=[],
        nargs="*",
        help="a specific test module/class/method to run; may be repeated "
        "multiple times; if no tests are given, through this or other flags, "
        "all tests are run",
    )
    parser.add_argument(
        "-s",
        "--only-shell",
        metavar="SHELL",
        help="limit shell-dependent tests to the specified shell. Note: This "
        "flag shadowed pytest '–capture=no' shorthand '-s', so the long "
        "name must be used for disabling stdout/err capturing in pytest.",
    )
    parser.add_argument(
        "--keep-tmpdirs", action="store_true", help="Keep temporary directories."
    )

    # make an Action that will append the appropriate test to the "--test" arg
    class AddTestModuleAction(argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):
            name = option_string.lstrip("-")
            if getattr(namespace, "module_tests", None) is None:
                namespace.module_tests = []
            namespace.module_tests.append(name)

    # find unit tests
    tests = []
    prefix = "test_"
    for importer, name, ispkg in iter_modules([tests_dir]):
        if not ispkg and name.startswith(prefix):
            module = importer.find_spec(name).loader.load_module(name)
            name_ = name[len(prefix):]
            all_module_tests.append(name_)
            tests.append((name_, module))

    # create argparse entry for each module's unit test
    for name, module in sorted(tests):
        if not module.__doc__:
            raise RuntimeError(
                "Module {0!r} doesn't have a docstring. Please add one.".format(
                    module.__file__
                )
            )

        parser.add_argument(
            "--%s" % name,
            action=AddTestModuleAction,
            nargs=0,
            dest="module_tests",
            default=[],
            help=module.__doc__.strip().rstrip("."),
        )


def command(opts, parser, extra_arg_groups=None):
    os.environ["__REZ_SELFTEST_RUNNING"] = "1"

    if opts.only_shell:
        os.environ["__REZ_SELFTEST_SHELL"] = opts.only_shell

    if opts.keep_tmpdirs:
        os.environ["REZ_KEEP_TMPDIRS"] = "1"

    if not opts.module_tests and not opts.tests:
        module_tests = all_module_tests
    else:
        module_tests = opts.module_tests

    repo = os.path.join(os.getcwd(), "__tests_pkg_repo")
    os.makedirs(repo, exist_ok=True)
    create_python_package(os.path.join(os.getcwd(), "__tests_pkg_repo"))

    os.environ["__REZ_SELFTEST_PYTHON_REPO"] = repo

    try:
        if use_pytest:
            run_pytest(module_tests, opts.tests, opts.verbose, extra_arg_groups)
        else:
            run_unittest(module_tests, opts.tests, opts.verbose)
    finally:
        shutil.rmtree(repo)


def run_unittest(module_tests, tests, verbosity):
    from unittest.main import main

    module_tests = [("rez.tests.test_%s" % x) for x in sorted(module_tests)]
    tests = module_tests + tests

    argv = [sys.argv[0]] + tests
    main(module=None, argv=argv, verbosity=verbosity)


def run_pytest(module_tests, tests, verbosity, extra_arg_groups):
    from pytest import main

    tests_dir = os.path.abspath(os.path.join(__file__, "..", "..", "tests"))

    # parse test name, e.g.
    #   "rez.tests.test_solver.TestSolver.test_01"
    # into
    #   "test_solver.py::TestSolver::test_01"
    test_specifications = []
    for test in tests:
        specifier = ""
        for part in test.split("."):
            if specifier:
                specifier += "::" + part
                continue
            if os.path.isfile(part + ".py"):
                specifier = os.path.join(tests_dir, f"{part}.py")
        if specifier:
            test_specifications.append(specifier)

    module_tests = [
        os.path.join(tests_dir, f"test_{x}.py") for x in sorted(module_tests)
    ]
    tests = module_tests + test_specifications

    argv = tests[:]

    if verbosity:
        argv += ["-" + ("v" * verbosity)]
    if extra_arg_groups:
        argv += extra_arg_groups[0]

    exitcode = main(args=argv)
    sys.exit(exitcode)


def create_python_package(repo):
    from rez.package_maker import make_package
    from rez.utils.lint_helper import env, system
    import venv

    print("Creating python package in {0!r}".format(repo))

    def make_root(variant, root):
        venv.create(root)

    def commands():
        if system.platform == "windows":
            env.PATH.prepend("{this.root}/Scripts")
        else:
            env.PATH.prepend("{this.root}/bin")

    with make_package("python", repo, make_root=make_root, warn_on_skip=False) as pkg:
        pkg.version = ".".join(map(str, sys.version_info[:3]))
        pkg.tools = ["python"]
        pkg.commands = commands
