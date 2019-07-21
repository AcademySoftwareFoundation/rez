import shutil

from rez.config import config
from rez.resolved_context import ResolvedContext
from rez.packages_ import get_latest_package_from_string, get_package_from_string, Variant
from rez.exceptions import PackageNotFoundError, PackageTestError
from rez.utils.colorize import heading, Printer
from rez.vendor.six import six
from rez.utils.system import change_dir
from pipes import quote
import subprocess
import os
import time
import sys


basestring = six.string_types[0]


class PackageTestRunner(object):
    """Object for running a package's tests.

    This runs the tests listed in the package's "tests" attribute.

    An example tests entry in a package.py might look like this:

        tests = {
            "unit": "python -m unittest -s {root}/tests",
            "CI": {
                "command": "python {root}/ci_tests/main.py",
                "requires": ["maya-2017"],
                "replace": True
            }
        }

    By default tests are run in an environment containing the current package.

    If a test entry is just a string, then it is treated as the test
    command. If a dict, the "command" string is the command, and the "requires"
    list is added to the test env.

    Command strings automatically expand references such as '{root}', much
    as happens in a *commands* function.

    Commands can also be a list - in this case, the test process is launched
    directly, rather than interpreted via a shell.

    TODO FIXME: Currently a test will not be run over the variants of a
    package. This is because there is no reliable way to resolve to a specific
    variant's env - we can influence the variant chosen, knowing how the
    variant selection mode works, but this is not a guarantee and it would
    be error-prone and complicated to do it this way. For reasons beyond
    package testing, we want to be able to explicitly specify a variant to
    resolve to anyway, so this will be fixed in a separate feature. Once that
    is available, this code will be updated to iterate over a package's
    variants and run tests in each.
    """
    def __init__(self, package_request, use_current_env=False,
                 extra_package_requests=None, package_paths=None, stdout=None,
                 stderr=None, verbose=False, clean=False, **context_kwargs):
        """Create a package tester.

        Args:
            package_request (str or `PackageRequest`): The package to test.
            use_current_env (bool): If True, run the test directly in the current
                rez-resolved environment, if there is one, and if it contains
                packages that meet the test's requirements.
            extra_package_requests (list of str or `PackageRequest`): Extra
                requests, these are appended to the test environment.
            package_paths: List of paths to search for pkgs, defaults to
                config.packages_path.
            stdout (file-like object): Defaults to sys.stdout.
            stderr (file-like object): Defaults to sys.stderr.
            verbose (bool): Verbose mode.
            clean (bool): States whether clean test artifacts before rerunning
            context_kwargs: Extra arguments which are passed to the
                `ResolvedContext` instances used to run the tests within.
                Ignored if `use_current_env` is True.
        """
        self.package_request = package_request
        self.use_current_env = use_current_env
        self.extra_package_requests = extra_package_requests
        self.stdout = stdout or sys.stdout
        self.stderr = stderr or sys.stderr
        self.verbose = verbose
        self.clean = clean
        self.context_kwargs = context_kwargs

        self.package_paths = (config.packages_path if package_paths is None
                              else package_paths)

        self._package = None
        self.contexts = {}

        # use a common timestamp across all tests - this ensures that tests
        # don't pick up new packages halfway through (ie from one test to another)
        self.timestamp = int(time.time())

        if use_current_env:
            raise NotImplementedError

    @property
    def package(self):
        """Get the target package.

        Returns:
            `Package`: Package to run tests on.
        """
        if self._package:
            return self._package

        if self.use_current_env:
            pass
        else:
            package = get_package_from_string(str(self.package_request), self.package_paths)

            if not package:
                package = get_latest_package_from_string(str(self.package_request), self.package_paths)

            if not package:
                raise PackageNotFoundError("Could not find package to test: %s" % str(self.package_request))

            self._package = package
            return package

    def get_test_names(self):
        """Get the names of tests in this package.

        Returns:
            List of str: Test names.
        """
        return sorted((self.package.tests or {}).keys())

    def run_test(self, test_name):
        """Run a test.

        Runs the test in its correct environment. Note that if tests share the
        same requirements, the contexts will be reused.

        TODO: If the package had variants, the test will be run for each
        variant.

        Returns:
            int: Returncode - zero if all test(s) passed, otherwise the return
                code of the failed test.
        """
        def print_header(txt, *nargs):
            pr = Printer(sys.stdout)
            pr(txt % nargs, heading)

        package = self.get_package()

        if test_name not in self.get_test_names():
            raise PackageTestError("Test '%s' not found in package %s"
                                   % (test_name, self.package.uri))

        if self.use_current_env:
            return self._run_test_in_current_env(test_name)

        for variant in self.package.iter_variants():

            # get test info for this variant. If None, that just means that this
            # variant doesn't provide this test. That's ok - 'tests' might be
            # implemented as a late function attribute that provides some tests
            # for some variants and not others
            #
            test_info = self._get_test_info(test_name, variant)
            if not test_info:
                continue

            command = test_info["command"]
            requires = test_info["requires"]

            # expand refs like {root} in commands
            if isinstance(command, basestring):
                command = variant.format(command)
            else:
                command = map(variant.format, command)

            # show progress
            if self.verbose:
                print_header(
                    "\nTest: %s\nPackage: %s\n%s\n",
                    test_name, variant.uri, '-' * 80)

            # create test env
            key = tuple(requires)
            context = self.contexts.get(key)

            if context is None:
                context = self._get_test_context(requires)

                if not context.success:
                    context.print_info(buf=self.stderr)
                    raise PackageTestError(
                        "Cannot run test '%s' of package %s: the environment "
                        "failed to resolve" % (test_name, variant.uri))

                self.contexts[key] = context

            # run the test in the context
            if self.verbose:
                context.print_info(self.stdout)

                if isinstance(command, basestring):
                    cmd_str = command
                else:
                    cmd_str = ' '.join(map(quote, command))

                self._print_header("\nRunning test command: %s\n" % cmd_str)

            test_result_dir = os.path.abspath('build/rez_test_result' if not test_info["run_in_root"] else '.')

            if self.clean and os.path.exists(test_result_dir):
                shutil.rmtree(test_result_dir)

            if not os.path.exists(test_result_dir):
                os.makedirs(test_result_dir)

            with change_dir(test_result_dir):
                retcode, _, _ = context.execute_shell(
                    command=command,
                    stdout=self.stdout,
                    stderr=self.stderr,
                    block=True)

            if retcode:
                return retcode

            # TODO FIXME we don't iterate over all variants yet, because we
            # can't reliably do that (see class docstring)
            break

        return 0  # success

    def run_test_env(self, variant_index, test_name):
        """
        Runs test env which contains all packages required for any test
        Args:
            variant_index (int): chosen variant index
            test_name (string): name of test 
        """
        variant = self.package.get_variant(variant_index)

        if not variant:
            variant = self.package

        test_info = self._get_test_info(test_name, variant)

        requires = test_info['requires']
        context_name = tuple(requires)
        context = self.contexts.get(context_name, self._get_test_context(requires))

        return_code, _, _ = context.execute_shell()

        sys.exit(return_code)

    def _get_test_context(self, requires):
        """
        Resolves context of test environment basing on required packages
        Args:
            requires (list): list of required packages

        Returns:
            Resolved context (ResolvedContext object)
        """
        if self.verbose:
            self._print_header("Resolving test environment: %s\n", ' '.join(map(quote, requires)))

        context = ResolvedContext(package_requests=requires,
                                  package_paths=self.package_paths,
                                  buf=self.stdout,
                                  timestamp=self.timestamp,
                                  **self.context_kwargs)

        return context

    def _print_header(self, txt, *nargs):
        pr = Printer(sys.stdout)
        pr(txt % nargs, heading)

    def _get_test_info(self, test_name, variant):
        tests_dict = variant.tests or {}
        test_entry = tests_dict.get(test_name)

        if not test_entry:
            return None

        if not isinstance(test_entry, dict):
            test_entry = {
                "command": test_entry
            }

        # construct env request
        requires = []

        if len(variant.version):
            req = "%s==%s" % (variant.name, str(variant.version))
            requires.append(req)
        else:
            requires.append(variant.name)

        reqs = test_entry.get("requires") or []
        requires.extend(map(str, reqs))

        if self.extra_package_requests:
            reqs = map(str, self.extra_package_requests)
            requires.extend(reqs)

        return {
            "command": test_entry["command"],
            "requires": requires,
            "run_in_root": test_entry.get("run_in_root", False)
        }
