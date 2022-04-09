# Copyright Contributors to the Rez project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Ensure ``rez-test`` works as expected."""

import atexit
import contextlib
import functools
import os
import platform
import shlex
import tempfile

from rez import resolved_context, exceptions as rez_exceptions
from rez.cli import _main
from rez.tests import util


class _Base(util.TestBase):
    """A bootstrap class for unittest classes in this module."""

    @classmethod
    def setUpClass(cls):
        """Save the install path where Rez packages should be sourced from."""
        cls.settings = dict()  # Needed for :class:`.util.TestBase`
        cls._install_path = cls.data_path("packages", "rez_test_packages")


class InteractiveFlagCases(_Base):
    """Ensure ``rez-test --interactive`` works in a variety of situations."""

    def test_default(self):
        """Resolve a test environment satisfying most test environments."""
        result = _test_shell(
            "test package_with_tests --interactive foo",
            packages_path=[self._install_path],
            variable="REZ_CURRENT_TEST_NAME",
        )

        self.assertEqual("foo", result)

    def test_on_variants(self):
        """Consider ``"on_variants"`` while selecting a variant."""
        result = _test_shell(
            "test package_with_tests --interactive on_variants_test_name",
            packages_path=[self._install_path],
            variable="REZ_TEST_VARIANT_INDEX",
        )

        self.assertEqual("1", result)

    def test_pre_test_commands(self):
        """Ensure ``pre_test_commands`` runs in the interactive shell."""
        expected_true = _test_shell(
            "test pre_test_package --interactive foo",
            packages_path=[self._install_path],
            variable="IS_FOO_TEST",
        )

        expected_false = _test_shell(
            "test pre_test_package --interactive bar",
            packages_path=[self._install_path],
            variable="IS_FOO_TEST",
        )

        self.assertEqual("1", expected_true)
        self.assertFalse(expected_false)

    def test_run_on_explicit(self):
        """Resolve a ``"run_on": "explicit"`` Rez test."""
        result = _test_shell(
            "test package_with_tests --interactive lastly",
            packages_path=[self._install_path],
            variable="REZ_CURRENT_TEST_NAME",
        )

        self.assertEqual("lastly", result)


class InteractiveFlagExtraPackages(_Base):
    """Ensure ``--extra-packages`` works with ``rez-test --interactive``."""

    def test_excess_packages(self):
        """Include ``--extra-packages``, even if they don't influence the variant selection.

        In this case ``package_with_tests`` has no variants that includes
        ``dependency`` installed Rez package.  So including ``dependency`` in
        ``--extra-packages`` doesn't narrow the possible variants at all.

        But even still, extra packages should always be in the resolved test
        environment.

        """
        resolved_with = _test_shell(
            "test package_with_tests --interactive fizz --extra-packages dependency-1",
            packages_path=[self._install_path],
            variable="REZ_CURRENT_TEST_NAME",
        )

        contains = _test_shell(
            "test package_with_tests --interactive fizz --extra-packages dependency-1",
            packages_path=[self._install_path],
            variable="REZ_USED_RESOLVE",
        )

        self.assertEqual("fizz", resolved_with)
        self.assertIn("dependency-1.0.0", contains.split(" "))

    def test_match_variant(self):
        """Choose the appropriate variant the matches ``--extra-packages``.

        In this instance, ``fizz`` could run on any variant that
        ``package_with_test`` defines. However ``--extra-packages`` as added
        and its value forces ``package_with_test`` to use the variant that
        requires Python 2.

        """
        result = _test_shell(
            "test package_with_tests --interactive fizz --extra-packages python-2",
            packages_path=[self._install_path],
            variable="REZ_TEST_VARIANT_INDEX",
        )

        self.assertEqual("1", result)

    def test_multiple_variant_candidates(self):
        """Pick any variant if multiple variants match the given ``--extra-packages``."""
        result = _test_shell(
            "test package_with_tests --interactive fizz --extra-packages python",
            packages_path=[self._install_path],
            variable="REZ_TEST_VARIANT_INDEX",
        )

        self.assertIn(result, {"0", "1"})

    def test_no_variants(self):
        """Include ``--extra-packages``, even if the package has no variants."""
        result = _test_shell(
            "test pre_test_package --interactive foo --extra-packages python",
            packages_path=[self._install_path],
            variable="REZ_USED_RESOLVE",
        )

        self.assertEqual(
            {"python-4.0.0", "pre_test_package-1.0.0"},
            set(result.split(" ")),
        )


class InteractiveFlagFails(_Base):
    """Make sure ``rez-test --interactive`` fails gracefully, when needed."""

    def test_bad_extra_packages(self):
        """Fail to resolve the test because extra packages don't match any variant.

        To be specific, the extra Rez package is "python-4". This version is
        installed and exists in Rez's packages_path, but none of the variants
        in ``package_with_tests`` are set up for Python 4 support.

        """
        with self.assertRaises(rez_exceptions.PackageTestError):
            _test_shell(
                "test package_with_tests --interactive fizz --extra-packages python-4",
                packages_path=[self._install_path],
                variable="REZ_RESOLVED_WITH_TESTS",
            )

    def test_conflicting_on_variants(self):
        """Fail to resolve if ``--extra-packages`` matches a variant the test can't use."""
        with self.assertRaises(rez_exceptions.PackageTestError):
            _test_shell(
                "test package_with_tests --interactive on_variants_test_name --extra-packages python-3",
                packages_path=[self._install_path],
                variable="REZ_CURRENT_TEST_NAME",
            )

    def test_conflicting_test_requires(self):
        """Fail to resolve because the test requires conflicts with package requires."""
        with self.assertRaises(rez_exceptions.PackageTestError):
            _test_shell(
                "test package_with_tests --interactive invalid_test",
                packages_path=[self._install_path],
                variable="REZ_RESOLVED_WITH_TESTS",
            )

    def test_missing_argument(self):
        """Fail to run if ``--interactive`` is given without a test name."""
        with self.assertRaises(SystemExit) as found:
            _test_shell(
                "test package_with_tests --interactive",
                packages_path=[self._install_path],
                variable="REZ_RESOLVED_WITH_TESTS",
            )

        self.assertEqual(2, found.exception.code)

    def test_not_found_test_name(self):
        """Fail if the given test name isn't defined in the package."""
        with self.assertRaises(rez_exceptions.PackageTestError):
            _test_shell(
                "test package_with_tests --interactive does_not_exist",
                packages_path=[self._install_path],
                variable="REZ_RESOLVED_WITH_TESTS",
            )


@contextlib.contextmanager
def _override_execute_shell(variable="REZ_RESOLVE"):
    """Change Rez's ResolvedContext.execute_shell to print and return.

    Args:
        variable (str, optional):
            An environment variable to print and return as stdout.

    Yields:
        callable:
            The overwritten
            :meth:`rez.resolved_context.ResolvedContext.execute_shell` method.

    """
    _, path = tempfile.mkstemp(suffix="_override_execute_shell.txt")
    atexit.register(functools.partial(os.remove, path))

    def _simulate_non_interactive(kwargs):
        system = platform.system()
        output = kwargs.copy()

        if system == "Windows":
            output["command"] = "echo %{variable}% >> {path}".format(variable=variable, path=path)
        else:
            output["command"] = "echo ${variable} >> {path}".format(variable=variable, path=path)

        output["block"] = True

        return output

    def _wrap(function):
        @functools.wraps(function)
        def wrapper(*args, **kwargs):
            """Append a command to print the resolved packages, then run ``function``."""
            kwargs = _simulate_non_interactive(kwargs)

            return function(*args, **kwargs)

        return wrapper

    original = resolved_context.ResolvedContext.execute_shell

    try:
        resolved_context.ResolvedContext.execute_shell = _wrap(
            resolved_context.ResolvedContext.execute_shell
        )

        yield path
    finally:
        resolved_context.ResolvedContext.execute_shell = original


def _test(command, packages_path=tuple()):
    """Simulate a user calling ``rez-test`` from the terminal.

    Args:
        command (str):
            The raw terminal request to run. e.g. "(rez-)test foo bar", but
            within the "(rez-)" part.
        packages_path (container[str], optional):
            Override paths used to search for a Rez package.

    """
    parts = shlex.split(command)

    if packages_path:
        parts.append("--paths")
        parts.extend(packages_path)

    subcommand = parts[0]

    run_command, _ = _main.parse_command(subcommand, argv=parts)

    try:
        run_command()
    except SystemExit:
        # Since Rez's CLI functions don't separate their function logic from
        # sys.exit / CLI logic, we have to catch the SystemExit calls so we can
        # ignore them.
        #
        pass


def _test_shell(command, packages_path=tuple(), variable="REZ_RESOLVE"):
    """Simulate an interactive shell and get an output variable.

    Args:
        command (str):
            The raw terminal request to run. e.g. "(rez-)test foo bar", but
            within the "(rez-)" part.
        packages_path (container[str], optional):
            Override paths used to search for a Rez package.
        variable (str, optional):
            An environment variable to print and return as stdout.

    Returns:
        tuple[str, str]: The environment variable output + any potential errors.

    """
    with _override_execute_shell(variable=variable) as path:
        _test(command, packages_path=packages_path)

    with open(path, "r") as handler:
        return handler.read().rstrip()
