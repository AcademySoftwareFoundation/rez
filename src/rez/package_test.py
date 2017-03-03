from rez.config import config
from rez.resolved_context import ResolvedContext
from rez.packages_ import get_latest_package_from_string, Variant
from rez.exceptions import PackageNotFoundError, PackageTestError
from rez.utils.colorize import heading, Printer
from pipes import quote
import subprocess
import sys


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
    """
    def __init__(self, package_request, use_current_env=False,
                 extra_package_requests=None, package_paths=None, stdout=None,
                 stderr=None, verbose=False, **context_kwargs):
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
        self.context_kwargs = context_kwargs

        self.package_paths = (config.packages_path if package_paths is None
                              else package_paths)

        self.package = None
        self.contexts = {}

    def get_package(self):
        """Get the target package.

        Returns:
            `Package`: Package to run tests on.
        """
        if self.package is not None:
            return self.package

        if self.use_current_env:
            pass
        else:
            package = get_latest_package_from_string(str(self.package_request),
                                                     self.package_paths)
            if package is None:
                raise PackageNotFoundError("Could not find package to test - %s"
                                           % str(self.package_request))

        self.package = package
        return self.package

    def get_test_names(self):
        """Get the names of tests in this package.

        Returns:
            List of str: Test names.
        """
        package = self.get_package()
        return sorted((package.tests or {}).keys())

    def can_run_test(self, test_name):
        """See if test can be run.

        The only time a test cannot be run is when `self.use_current_env` is
        True, and the current env does not have the necessary requirements.

        Returns:
            2-tuple:
            - bool: True if test can be run;
            - str: Description of why test cannot be run (or empty string).
        """
        if not self.use_current_env:
            return True, ''

        return False, "TODO"

    def run_test(self, test_name):
        """Run a test.

        Runs the test in its correct environment. Note that if tests share the
        same requirements, the contexts will be reused.

        Returns:
            subprocess.Popen: Test process.
        """
        package = self.get_package()
        test_info = self._get_test_info(test_name)
        command = test_info["command"]
        requires = test_info["requires"]

        def print_header(txt, *nargs):
            pr = Printer(sys.stdout)
            pr(txt % nargs, heading)

        def print_command_header():
            if self.verbose:
                if isinstance(command, basestring):
                    cmd_str = command
                else:
                    cmd_str = ' '.join(map(quote, command))

                print_header("\n\nRunning test '%s'\nCommand: %s\n",
                             test_name, cmd_str)

        def expand_command(context, command):
            variant = context.get_resolved_package(package.name)
            if isinstance(command, basestring):
                return variant.format(command)
            else:
                return map(variant.format, command)

        if self.use_current_env:
            can_run, descr = self.can_run_test(test_name)
            if not can_run:
                raise PackageTestError(
                    "Cannot run test '%s' of package %s in the current "
                    "environment: %s" % (test_name, package.uri, descr))

            context = ResolvedContext.get_current()
            command = expand_command(context, command)

            print_command_header()

            # run directly as subprocess
            p = subprocess.Popen(command, shell=isinstance(command, basestring),
                                 stdout=self.stdout, stderr=self.stderr)
            return p

        # create/reuse context to run test within
        key = tuple(requires)
        context = self.contexts.get(key)

        if context is None:
            if self.verbose:
                print_header("\nResolving environment for test '%s': %s\n%s\n",
                             test_name, ' '.join(map(quote, requires)), '-' * 80)

            context = ResolvedContext(package_requests=requires,
                                      package_paths=self.package_paths,
                                      buf=self.stdout,
                                      **self.context_kwargs)

            if not context.success:
                context.print_info(buf=self.stderr)
                raise PackageTestError(
                    "Cannot run test '%s' of package %s: the environment "
                    "failed to resolve" % (test_name, package.uri))

            self.contexts[key] = context

        command = expand_command(context, command)

        if self.verbose:
            context.print_info(self.stdout)
            print_command_header()

        return context.execute_shell(command=command,
                                     stdout=self.stdout,
                                     stderr=self.stderr)

    def _get_test_info(self, test_name):
        package = self.get_package()

        tests_dict = package.tests or {}
        test_entry = tests_dict.get(test_name)

        if not test_entry:
            raise PackageTestError("Test '%s' not found in package %s"
                                   % (test_name, package.uri))

        if not isinstance(test_entry, dict):
            test_entry = {
                "command": test_entry
            }

        # construct env request
        requires = []

        if len(package.version):
            req = "%s==%s" % (package.name, str(package.version))
            requires.append(req)
        else:
            requires.append(str(package))

        reqs = test_entry.get("requires") or []
        requires.extend(reqs)

        if self.extra_package_requests:
            reqs = map(str, self.extra_package_requests)
            requires.extend(reqs)

        return {
            "command": test_entry["command"],
            "requires": requires
        }
