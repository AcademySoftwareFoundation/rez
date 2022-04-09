# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project

import functools
import itertools

from rez.config import config
from rez.resolved_context import ResolvedContext
from rez.packages import get_latest_package_from_string
from rez.exceptions import RezError, PackageNotFoundError, PackageTestError, ResolvedContextError
from rez.utils.data_utils import RO_AttrDictWrapper
from rez.utils.colorize import heading, Printer
from rez.utils.logging_ import print_info, print_warning, print_error
from rez.utils.formatting import PackageRequest
from rez.vendor.six import six
from rez.vendor.version.requirement import Requirement, RequirementList
from pipes import quote
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
    """
    def __init__(self, package_request, use_current_env=False,
                 extra_package_requests=None, package_paths=None, stdout=None,
                 stderr=None, verbose=0, dry_run=False, stop_on_fail=False,
                 cumulative_test_results=None, **context_kwargs):
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
            verbose (int): Verbose mode (valid values: 0, 1, 2)
            dry_run (bool): If True, do everything except actually run tests.
            cumulative_test_results (`PackageTestResults`): If supplied, test
                run results can be stored across multiple runners.
            context_kwargs: Extra arguments which are passed to the
                `ResolvedContext` instances used to run the tests within.
                Ignored if `use_current_env` is True.
        """
        self.package_request = package_request
        self.use_current_env = use_current_env
        self.extra_package_requests = extra_package_requests
        self.stdout = stdout or sys.stdout
        self.stderr = stderr or sys.stderr
        self.dry_run = dry_run
        self.stop_on_fail = stop_on_fail
        self.cumulative_test_results = cumulative_test_results
        self.context_kwargs = context_kwargs

        if isinstance(verbose, bool):
            # backwards compat, verbose used to be bool
            self.verbose = 2 if verbose else 0
        else:
            self.verbose = verbose

        self.package_paths = (config.packages_path if package_paths is None
                              else package_paths)

        self.test_results = PackageTestResults()
        self.package = None
        self.contexts = {}
        self.stopped_on_fail = False

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

    @classmethod
    def get_package_test_names(cls, package, run_on=None, ran_once=None):
        """Get the names of tests in the given package.

        Args:
            run_on (list of str): If provided, only include tests with run_on
                tags that overlap with the given list.
            ran_once (list of str): If provided, skip tests that are in this
                list, and are configured for on_variants=False (ie, just run
                the test on one variant).

        Returns:
            List of str: Test names.
        """
        tests_dict = package.tests or {}

        if run_on:
            def _select(value):
                if isinstance(value, dict):
                    value = value.get("run_on")
                else:
                    value = None

                if value is None:
                    return ("default" in run_on)
                elif isinstance(value, basestring):
                    return (value in run_on)
                else:
                    return bool(set(value) & set(run_on))

            tests_dict = dict(
                (k, v) for k, v in tests_dict.items()
                if _select(v)
            )

        if ran_once:
            def _select(key, value):
                if isinstance(value, dict):
                    value = value.get("on_variants")
                else:
                    value = None

                if value in (None, False):
                    return (key not in ran_once)
                else:
                    return True

            tests_dict = dict(
                (k, v) for k, v in tests_dict.items()
                if _select(k, v)
            )

        return sorted(tests_dict.keys())

    def get_test_names(self, run_on=None):
        """Get the names of tests in this package.

        Args:
            run_on (list of str): If provided, only include tests with run_on
                tags that overlap with the given list.

        Returns:
            List of str: Test names.
        """
        package = self.get_package()

        if package is None:
            return []

        return self.get_package_test_names(package, run_on=run_on)

    @property
    def num_tests(self):
        """Get the number of tests, regardless of stats.
        """
        return self.test_results.num_tests

    @property
    def num_success(self):
        """Get the number of successful test runs.
        """
        return self.test_results.num_success

    @property
    def num_failed(self):
        """Get the number of failed test runs.
        """
        return self.test_results.num_failed

    @property
    def num_skipped(self):
        """Get the number of skipped test runs.
        """
        return self.test_results.num_skipped

    def run_test(self, test_name):
        """Run a test.

        Runs the test in its correct environment. Note that if tests share the
        same requirements, the contexts will be reused.

        Args:
            test_name (str): Name of test to run.

        Returns:
            int: Exit code of first failed test, or 0 if none failed. If the first
                test to fail did so because it was not able to run (eg its
                environment could not be configured), -1 is returned.
        """
        package = self.get_package()
        exitcode = 0

        if test_name not in self.get_test_names():
            raise PackageTestError("Test '%s' not found in package %s"
                                   % (test_name, package.uri))

        if self.use_current_env:
            if package is None:
                self._add_test_result(
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
                self._add_test_result(
                    test_name,
                    variant,
                    "skipped",
                    "The test is not declared in this variant"
                )
                continue

            command = test_info["command"]
            requires = test_info["requires"]
            on_variants = test_info["on_variants"]

            # show progress
            if self.verbose > 1:
                self._print_header(
                    "\nRunning test: %s\nPackage: %s\n%s\n",
                    test_name, variant.uri, '-' * 80
                )
            elif self.verbose:
                self._print_header(
                    "\nRunning test: %s\n%s\n",
                    test_name, '-' * 80
                )

            # apply variant selection filter if specified
            if isinstance(on_variants, dict):
                filter_type = on_variants["type"]
                func = getattr(self, "_on_variant_" + filter_type)
                do_test = func(variant, on_variants)

                if not do_test:
                    reason = (
                        "Test skipped as specified by on_variants '%s' filter"
                        % filter_type
                    )

                    print_info(reason)

                    self._add_test_result(
                        test_name,
                        variant,
                        "skipped",
                        reason
                    )

                    continue

            # add requirements to force the current variant to be resolved.
            # TODO this is not perfect, and will need to be updated when
            # explicit variant selection is added to rez (this is a new
            # feature). Until then, there's no guarantee that we'll resolve to
            # the variant we want, so we take that into account here.
            #
            requires.extend(map(str, variant.variant_requires))

            # create test runtime env
            exc = None
            try:
                context = self._get_context(requires)
            except RezError as e:
                exc = e

            fail_reason = None
            if exc is not None:
                fail_reason = "The test environment failed to resolve: %s" % exc
            elif context is None:
                fail_reason = "The current environment does not meet test requirements"
            elif not context.success:
                fail_reason = "The test environment failed to resolve"

            if fail_reason:
                self._add_test_result(
                    test_name,
                    variant,
                    "failed",
                    fail_reason
                )

                print_error(fail_reason)

                if not exitcode:
                    exitcode = -1

                if self.stop_on_fail:
                    self.stopped_on_fail = True
                    return exitcode

                continue

            # check that this has actually resolved the variant we want
            resolved_variant = context.get_resolved_package(package.name)
            assert resolved_variant

            if resolved_variant.handle != variant.handle:
                print_warning(
                    "Could not resolve environment for this variant (%s). This "
                    "is a known issue and will be fixed once 'explicit variant "
                    "selection' is added to rez.", variant.uri
                )

                self._add_test_result(
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
                if self.verbose > 1:
                    context.print_info(self.stdout)
                    print('')

                if isinstance(command, basestring):
                    cmd_str = command
                else:
                    cmd_str = ' '.join(map(quote, command))

                self._print_header("Running test command: %s", cmd_str)

            if self.dry_run:
                self._add_test_result(
                    test_name,
                    variant,
                    "skipped",
                    "Dry run mode"
                )
                continue

            retcode, _, _ = context.execute_shell(
                command=command,
                actions_callback=functools.partial(
                    _pre_test_commands,
                    test_name,
                    variant,
                ),
                stdout=self.stdout,
                stderr=self.stderr,
                block=True
            )

            if retcode:
                print_warning("Test command exited with code %d", retcode)

                self._add_test_result(
                    test_name,
                    variant,
                    "failed",
                    "Test failed with exit code %d" % retcode
                )

                if not exitcode:
                    exitcode = retcode

                if self.stop_on_fail:
                    self.stopped_on_fail = True
                    return exitcode

                continue

            # test passed
            self._add_test_result(
                test_name,
                variant,
                "success",
                "Test succeeded"
            )

            # just test against one variant in this case
            if on_variants is False:
                break

        return exitcode

    def run_test_env(self, test_name):
        """Open an interactive shell which resolves ``test_names``.

        Args:
            test_name (str):
                The ``tests`` key to get a resolve for. This key must already
                be defined in this instance's Rez package.

        Raises:
            ResolvedContextError:
                If resolving the current package including ``test_name`` /
                extra Rez packages fails, for any reason.

        Returns:
            int: The return code of the interactive shell.

        """

        def _get_test_requests(variant, test_name):
            """Convert ``test_name`` into a Rez package requests.

            Args:
                variant (Variant or Package):
                    The Rez data used to get test requirements.
                test_name (str):
                    The Rez test name  to include in the resolve.

            Raises:
                PackageTestError:
                    If a test name in ``test_names`` is not defined in ``variant``.

            Returns:
                set[str]: All found Rez package requests.

            """
            requires = set(variant.requires or set())
            is_variant = hasattr(variant, "variant_requires")

            if is_variant:
                requires.update(variant.variant_requires)

            data = self._get_test_info(test_name, variant) or dict()

            if not data:
                raise PackageTestError(
                    'Cannot create context. Rez Test "{test_name}" is missing '
                    'in package "{self.package.name}".'.format(
                        test_name=test_name, self=self,
                    )
                )

            test_requires = [PackageRequest(request) for request in data.get("requires", [])]

            return {str(request) for request in test_requires}

        def _get_test_requires_as_requests(test_name):
            """Get the ``requires`` of every Rez test in ``test_names``.

            Args:
                test_name (iter[str]): The Rez test name to query.

            Returns:
                set[PackageRequest]: The found requests in that test.

            """
            data = self._get_test_info(test_name, self.package) or dict()
            requires = {PackageRequest(request) for request in data.get("requires") or []}

            if data and data["on_variants"] and data["on_variants"]["type"] == "requires":
                requires.update(data["on_variants"]["value"])

            return requires

        extra_packages = {PackageRequest(request) for request in self.extra_package_requests or set()}
        test_requires = _get_test_requires_as_requests(test_name)
        test_requires -= extra_packages

        _validate_test_requests(test_requires, extra_packages)

        extra_packages = extra_packages or set()
        variant = _choose_test_object(
            self.package,
            test_requires=test_requires,
            extra_packages=extra_packages,
        )

        requires = _get_test_requests(variant, test_name)
        context = self.contexts.get(tuple(requires)) or self._get_test_context(requires)

        if not context.success:
            context.print_info()

            raise ResolvedContextError(
                "The context failed to resolve. The interactive test shell failed."
            )

        return_code, _, _ = context.execute_shell(
            actions_callback=functools.partial(
                _pre_test_env_commands, test_name, variant,
            ),
        )

        return return_code

    def print_summary(self):
        self.test_results.print_summary()

    def _add_test_result(self, *nargs, **kwargs):
        self.test_results.add_test_result(*nargs, **kwargs)

        if self.cumulative_test_results:
            self.cumulative_test_results.add_test_result(*nargs, **kwargs)

    @classmethod
    def _print_header(cls, txt, *nargs):
        pr = Printer(sys.stdout)
        pr(txt % nargs, heading)

    def _on_variant_requires(self, variant, params):
        """
        Only run test on variants whose direct requirements are a subset of, and
        do not conflict with, the list given in 'value' param.

        For example, if on_variants.value is ['foo', 'bah'] then only variants
        containing both these requirements will be selected; ['!foo', 'bah'] would
        select those variants with bah present and not foo; ['!foo'] would
        select all variants without foo present.
        """
        requires_filter = params["value"]

        reqlist = RequirementList(variant.variant_requires + requires_filter)

        if reqlist.conflict:
            return False

        # If the combined requirements, minus conflict requests, is equal to the
        # variant's requirements, then this variant is selected.
        #
        reqs1 = RequirementList(x for x in reqlist if not x.conflict)
        reqs2 = RequirementList(x for x in variant.variant_requires if not x.conflict)
        return (reqs1 == reqs2)

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

        # construct run_on
        run_on = test_entry.get("run_on")
        if run_on:
            if isinstance(run_on, basestring):
                run_on = [run_on]
        else:
            run_on = ["default"]

        # finish
        return {
            "command": test_entry["command"],
            "requires": requires,
            "run_on": run_on,
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
                RequirementList(current_reqs)
                == RequirementList(current_reqs + reqs)
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
                try:
                    context = self._get_context(requires, quiet=True)
                except RezError:
                    continue

                if context is None or not context.success:
                    continue

                preferred_variant = context.get_resolved_package(package.name)
                assert preferred_variant

                if variant == preferred_variant:
                    return [variant]

        # just iterate over all variants
        return list(package.iter_variants())

    def _get_test_context(self, requires):
        """Generate a Rez context with this Package + ``requires``.

        Args:
            requires (set[str]):
                Each package request to add into the context. e.g. ``{"python-2", }``.

        Returns:
            ResolvedContext: The generated context.

        """
        if self.verbose:
            self._print_header(
                "Resolving test environment: %s\n",
                " ".join(map(quote, requires)),
            )

        kwargs = dict(
            package_requests=requires,
            package_paths=self.package_paths,
            buf=self.stdout,
            timestamp=self.timestamp,
        )
        kwargs.update(self.context_kwargs)

        return ResolvedContext(**kwargs)


class PackageTestResults(object):
    """Contains results of running tests with a `PackageTestRunner`.

    Use this class (and pass it to the `PackageTestRunner` constructor) if you
    need to gather test run results from separate runners, and display them in
    a single table.
    """
    valid_statuses = ("success", "failed", "skipped")

    def __init__(self):
        self.test_results = []

    @property
    def num_tests(self):
        """Get the number of tests, regardless of stats.
        """
        return len(self.test_results)

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

    def add_test_result(self, test_name, variant, status, description):
        if status not in self.valid_statuses:
            raise RuntimeError("Invalid status")

        self.test_results.append({
            "test_name": test_name,
            "variant": variant,
            "status": status,
            "description": description
        })

    def print_summary(self):
        from rez.utils.formatting import columnise

        pr = Printer(sys.stdout)
        txt = "Test results:\n%s" % ('-' * 80)
        pr(txt, heading)

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
                test_result["variant"].root,
                test_result["description"]
            ))

        strs = columnise(rows)
        print('\n'.join(strs))


def _is_conflict(*requires):
    """Check if any of the requirements have a conflict.

    Example:
        >>> _is_conflict([PackageRequest("foo-2")], [PackageRequest("!foo-2")])
        # True
        >>> _is_conflict([PackageRequest("foo-2")], [PackageRequest("foo-1+")])
        # False

    Args:
        requires (tuple[iter[PackageRequest]]):
            A series of Rez packages requests to check for conflicts.

    Returns:
        bool: If conflict, return True, otherwise, return False.

    """
    requirement = RequirementList(itertools.chain(*requires))

    return requirement.conflict


def _choose_test_object(package, test_requires, extra_packages=frozenset()):
    """Find the most appropriate Rez object for ``rez-test --interactive``.

    If ``package`` has variants, find a valid variant, given ``test_requires``
    and ``extra_packages``.

    Args:
        package (Package):
            The installed Rez package to query variant / test data from.
        test_requires (set[PackageRequest]):
            Include these Rez package versions in the check, if provided. If
            the Rez test has no defined ``"requires"``, this parameter is empty.
        extra_packages (set[PackageRequest], optional):
            Include these Rez package versions in the check, if provided.  This
            is usually empty unless the user explicitly asks for them, e.g.
            using ``rez-test foo --interactive bar --extra-packages thing-1``.

    Raises:
        PackageTestError:
            If ``test_requires`` or ``extra_packages`` result in a Rez request conflict.

    Returns:
        Package or Variant:
            Get a specific variant to return. If ``package`` has no variants
            defined then this function returns ``package``, instead.

    """
    variants = package.variants

    if not variants:
        return package

    candidates = []

    for variant_index, package_requests in enumerate(variants):
        if not _is_conflict(package_requests, test_requires, extra_packages):
            candidates.append(package.get_variant(variant_index))

    if not candidates:
        if not extra_packages:
            raise PackageTestError(
                "No valid variant could match your given Rez test requires."
            )

        raise PackageTestError(
            "No valid variant could match your given Rez test requires + extra packages."
        )

    return candidates[0]


def _pre_test_env_commands(test_name, variant, executor):
    """Run package.py:pre_test_commands() if present.

    Args:
        test_name (str):
            The Rez test name which will be ran.
        variant (Package or Variant):
            A Rez object which may define ``pre_test_commands``.
        executor (RexExecutor):
            An interpreter to load commands during the ``rez-env``.

    """
    _pre_test_commands(test_name, variant, executor)

    if hasattr(variant, "index"):
        executor.setenv("REZ_CURRENT_TEST_VARIANT_INDEX", variant.index)


def _pre_test_commands(test_name, variant, executor):
    """Run package.py:pre_test_commands(), if present.

    Args:
        test_name (str):
            The Rez test name to add to ``$REZ_CURRENT_TEST_NAME``, which is
            useful for debugging.
        variant (Package or Variant):
            A Rez object which may define ``pre_test_commands``.
        executor (RexExecutor):
            An interpreter to load commands during the ``rez-env``.

    """
    pre_test_commands = getattr(variant, "pre_test_commands")

    with executor.reset_globals():
        executor.setenv("REZ_CURRENT_TEST_NAME", test_name)

        if not pre_test_commands:
            return

        executor.bind("this", variant)
        executor.bind("test", RO_AttrDictWrapper({"name": test_name}))
        executor.execute_code(pre_test_commands)
        executor.setenv("REZ_CURRENT_TEST_NAME", test_name)


def _validate_test_requests(test_requires, extra_packages):
    """Make sure all requirements from a Rez test don't conflict with ``extra_packages``.

    Args:
        test_requires (container[PackageRequest]):
            The combination of a Rez test's "requires" and "on_variants", if any.
        extra_packages (container[PackageRequest]):
            Extra Rez package requests the user wants to consider, if any.

    Raises:
        PackageTestError: If any conflict between the given parameters was found.

    """
    if _is_conflict(test_requires):
        test_requires_names = ", ".join(str(request) for request in test_requires)

        raise PackageTestError(
            'Test has conflicting requires {test_requires_names!r}.'.format(
                test_requires_names=test_requires_names,
            )
        )

    if not _is_conflict(test_requires, extra_packages):
        return

    test_requires_names = ", ".join(str(request) for request in test_requires)
    extra_package_names = ", ".join(str(request) for request in extra_packages)

    raise PackageTestError(
        'Test requires "{test_requires_names}" conflicts with '
        '"{extra_package_names}" extra packages.'.format(
            test_requires_names=test_requires_names,
            extra_package_names=extra_package_names,
        )
    )
