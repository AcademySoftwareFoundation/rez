from rez.config import config
from rez.resolved_context import ResolvedContext
from rez.packages_ import get_latest_package_from_string, Variant
from rez.exceptions import PackageNotFoundError, PackageTestError
from rez.utils.colorize import heading, Printer
from rez.utils.logging_ import print_warning
from rez.vendor.six import six
from rez.vendor.version.requirement import Requirement, RequirementList
from pipes import quote
import subprocess
import time
import sys
import os


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
                 stderr=None, verbose=False, dry_run=False, stop_on_fail=False,
                 **context_kwargs):
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
            dry_run (bool): If True, do everything except actually run tests.
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
        self.dry_run = dry_run
        self.stop_on_fail = stop_on_fail
        self.context_kwargs = context_kwargs

        self.package_paths = (config.packages_path if package_paths is None
                              else package_paths)

        self.package = None
        self.contexts = {}
        self.stopped_on_fail = False
        self.test_results = []

        # use a common timestamp across all tests - this ensures that tests
        # don't pick up new packages halfway through (ie from one test to another)
        self.timestamp = int(time.time())

    def get_package(self):
        """Get the target package.

        Returns:
            `Package`: Package to run tests on.
        """
        if self.package is not None:
            return self.package

        if self.use_current_env:
            # get package from current context, or return None
            current_context = ResolvedContext.get_current()
            if current_context is None:
                return None

            req = Requirement(self.package_request)
            variant = current_context.get_resolved_package(req.name)
            if variant is None:
                return None

            package = variant.parent

            if not req.range.contains_version(package.version):
                return None

        else:
            # find latest package within request
            package = get_latest_package_from_string(str(self.package_request),
                                                     self.package_paths)
            if package is None:
                raise PackageNotFoundError("Could not find package to test: %s"
                                           % str(self.package_request))

        self.package = package
        return self.package

    def get_test_names(self):
        """Get the names of tests in this package.

        Returns:
            List of str: Test names.
        """
        package = self.get_package()

        if package is None:
            return []

        return sorted((package.tests or {}).keys())

    @property
    def num_success(self):
        """Get the number of successful test runs.
        """
        return len([x for x in self.test_results if x["status"] == "success"])

    @property
    def num_failed(self):
        """Get the number of failed test runs.
        """
        return len([x for x in self.test_results if x["status"] == "failed"])

    @property
    def num_skipped(self):
        """Get the number of skipped test runs.
        """
        return len([x for x in self.test_results if x["status"] == "skipped"])

    def run_test(self, test_name):
        """Run a test.

        Runs the test in its correct environment. Note that if tests share the
        same requirements, the contexts will be reused.

        Args:
            test_name (str): Name of test to run.
        """
        package = self.get_package()

        if test_name not in self.get_test_names():
            raise PackageTestError("Test '%s' not found in package %s"
                                   % (test_name, package.uri))

        if self.use_current_env:
            if package is None:
                self._set_test_result(
                    test_name,
                    None,
                    "skipped",
                    "The current environment does not contain a package "
                    "matching the request"
                )
                return

            current_context = ResolvedContext.get_current()
            current_variant = current_context.get_resolved_package(package.name)
            target_variants = [current_variant]

        else:
            target_variants = self._get_target_variants(test_name)

        for variant in target_variants:

            # get test info for this variant. If None, that just means that this
            # variant doesn't provide this test. That's ok - 'tests' might be
            # implemented as a late function attribute that provides some tests
            # for some variants and not others
            #
            test_info = self._get_test_info(test_name, variant)
            if not test_info:
                self._set_test_result(
                    test_name,
                    variant,
                    "skipped",
                    "The test is not declared in this variant"
                )
                continue

            command = test_info["command"]
            requires = test_info["requires"]
            on_variants = test_info["on_variants"]

            # if on_variants is a dict containing "requires", then only run the
            # test on variants whose direct requirements are a subset of, and do
            # not conflict with, this requires list. Variants are silently skipped
            # on mismatch in this case. For example, if on_variants.requires is
            # ['foo', 'bah'] then only variants containing both these requirements
            # will be selected; ['!foo', 'bah'] would select those variants with
            # bah present and not foo.
            #
            # This is different to the test's "requires" - in this case,
            # requires=['foo'] would add this requirement to every test env.
            # This is a requirement addition, whereas on_variants.requires is a
            # variant selection mechanism.
            #
            if isinstance(on_variants, dict) and "requires" in on_variants:
                reqlist = RequirementList(
                    variant.variant_requires + on_variants["requires"])

                if reqlist.conflict:
                    continue

                # test if variant requires is a subset of on_variants.requires.
                # This works because RequirementList merges requirements.
                #
                if RequirementList(variant.variant_requires) != reqlist:
                    continue

            # show progress
            if self.verbose:
                self._print_header(
                    "\nTest: %s\nPackage: %s\n%s\n",
                    test_name, variant.uri, '-' * 80
                )

            # add requirements to force the current variant to be resolved.
            # TODO this is not perfect, and will need to be updated when
            # explicit variant selection is added to rez (this is a new
            # feature). Until then, there's no guarantee that we'll resolve to
            # the variant we want, so we take that into account here.
            #
            requires.extend(map(str, variant.variant_requires))

            # create test runtime env
            context = self._get_context(requires)

            if context is None:
                self._set_test_result(
                    test_name,
                    variant,
                    "skipped",
                    "The current environment does not meet test requirements"
                )

                print("(Skipped)")
                continue

            if not context.success:
                self._set_test_result(
                    test_name,
                    variant,
                    "skipped",
                    "The test environment failed to resolve"
                )
                continue

            # check that this has actually resolved the variant we want
            resolved_variant = context.get_resolved_package(package.name)
            assert resolved_variant

            if resolved_variant.handle != variant.handle:
                print_warning(
                    "Could not resolve environment for this variant. This is a "
                    "known issue and will be fixed once 'explicit variant "
                    "selection' is added to rez."
                )

                self._set_test_result(
                    test_name,
                    variant,
                    "skipped",
                    "Could not resolve to variant (known issue)"
                )
                continue

            # expand refs like {root} in commands
            if isinstance(command, basestring):
                command = variant.format(command)
            else:
                command = map(variant.format, command)

            # run the test in the context
            if self.verbose:
                context.print_info(self.stdout)

                if isinstance(command, basestring):
                    cmd_str = command
                else:
                    cmd_str = ' '.join(map(quote, command))

                self._print_header("\nRunning test command: %s\n", cmd_str)

            if self.dry_run:
                self._set_test_result(
                    test_name,
                    variant,
                    "skipped",
                    "Dry run mode"
                )
                continue

            retcode, _, _ = context.execute_shell(
                command=command,
                stdout=self.stdout,
                stderr=self.stderr,
                block=True
            )

            if retcode:
                self._set_test_result(
                    test_name,
                    variant,
                    "failed",
                    "Test failed with exit code %d" % retcode
                )

                if self.stop_on_fail:
                    self.stopped_on_fail = True
                    return

                continue

            # test passed
            self._set_test_result(
                test_name,
                variant,
                "success",
                "Test succeeded"
            )

            # just test against one variant in this case
            if on_variants is False:
                break

    def print_summary(self):
        from rez.utils.formatting import columnise

        self._print_header(
            "\n\nResults:\n%s",
            '-' * 80
        )

        print(
            "%d succeeded, %d failed, %d skipped\n"
            % (self.num_success, self.num_failed, self.num_skipped)
        )

        rows = [
            ("Test", "Status", "Variant", "Description"),
            ("----", "------", "-------", "-----------")
        ]

        for test_result in self.test_results:
            rows.append((
                test_result["test_name"],
                test_result["status"],
                test_result["variant"].uri,
                test_result["description"]
            ))

        strs = columnise(rows)
        print('\n'.join(strs))
        print('\n')

    def _set_test_result(self, test_name, variant, status, description):
        self.test_results.append({
            "test_name": test_name,
            "variant": variant,
            "status": status,
            "description": description
        })

    @classmethod
    def _print_header(cls, txt, *nargs):
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
            "on_variants": test_entry.get("on_variants", False)
        }

    def _get_context(self, requires, quiet=False):

        # if using current env, only return current context if it meets
        # requirements, otherwise return None
        if self.use_current_env:
            current_context = ResolvedContext.get_current()
            if current_context is None:
                return None

            reqs = map(Requirement, requires)
            current_reqs = current_context.get_resolve_as_exact_requests()

            meets_requirements = (
                RequirementList(current_reqs) ==
                RequirementList(current_reqs + reqs)
            )

            if meets_requirements:
                return current_context
            else:
                return None

        # create context or use cached context
        key = tuple(requires)
        context = self.contexts.get(key)

        if context is None:
            if self.verbose and not quiet:
                self._print_header(
                    "Resolving test environment: %s\n",
                    ' '.join(map(quote, requires))
                )

            with open(os.devnull, 'w') as f:
                context = ResolvedContext(
                    package_requests=requires,
                    package_paths=self.package_paths,
                    buf=(f if quiet else None),
                    timestamp=self.timestamp,
                    **self.context_kwargs
                )

            self.contexts[key] = context

        if not context.success and not quiet:
            context.print_info(buf=self.stderr)

        return context

    def _get_target_variants(self, test_name):
        """
        If the test is not variant-specific, then attempt to find the 'preferred'
        variant (as per setting 'variant_select_mode'). Otherwise, just run tests
        over all variants.
        """
        package = self.get_package()

        for variant in package.iter_variants():
            test_info = self._get_test_info(test_name, variant)

            if not test_info:
                continue

            on_variants = test_info["on_variants"]
            requires = test_info["requires"]

            if on_variants is False:
                # test should be run on one variant, so if the current is also
                # the preferred, then use that. Note that we print to dev/null
                # otherwise the initial stream of (potentially failing) context
                # output would be confusing to the user.
                #
                context = self._get_context(requires, quiet=True)
                if not context.success:
                    continue

                preferred_variant = context.get_resolved_package(package.name)
                assert preferred_variant

                if variant == preferred_variant:
                    return [variant]

        # just iterate over all variants
        return list(package.iter_variants())
