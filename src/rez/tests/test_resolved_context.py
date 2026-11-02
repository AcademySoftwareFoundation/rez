# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project

"""Ensure specific functionality of :mod:`rez.resolved_context` works."""

from rez import resolved_context
from rez.tests import util


class ContextDiff(util.TestBase):
    """Make sure :meth:`.ResolvedContext.get_resolved_diff` works."""

    def test_diff_custom_paths(self):
        """Get a proper diff, even if the packages_path is non-default."""
        packages_path = [self.data_path("builds", "packages")]

        one = resolved_context.ResolvedContext(
            package_requests=["foo==1.0.0"],
            package_paths=packages_path,
        )

        two = resolved_context.ResolvedContext(
            package_requests=["foo==1.1.0"],
            package_paths=packages_path,
        )

        diff = one.get_resolve_diff(two)

        self.assertEqual(
            ["1.0.0", "1.1.0"],
            [str(package.version) for package in diff["newer_packages"]["foo"]],
        )
