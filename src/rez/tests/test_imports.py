# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
test importing of all source
"""
from rez.tests.util import TestBase
import unittest


class TestImports(TestBase):
    def test_1(self):
        """import every file in rez."""
        import rez  # noqa
        import rez.build_process  # noqa
        import rez.build_system  # noqa
        import rez.bundle_context  # noqa
        import rez.config  # noqa
        import rez.developer_package  # noqa
        import rez.exceptions  # noqa
        import rez.package_cache  # noqa
        import rez.package_copy  # noqa
        import rez.package_filter  # noqa
        import rez.package_help  # noqa
        import rez.package_maker  # noqa
        import rez.package_order  # noqa
        import rez.package_repository  # noqa
        import rez.package_resources  # noqa
        import rez.package_search  # noqa
        import rez.package_serialise  # noqa
        import rez.package_test  # noqa
        import rez.packages  # noqa
        import rez.plugin_managers  # noqa
        import rez.release_hook  # noqa
        import rez.release_vcs  # noqa
        import rez.resolved_context  # noqa
        import rez.resolver  # noqa
        import rez.rex  # noqa
        import rez.rex_bindings  # noqa
        import rez.serialise  # noqa
        import rez.shells  # noqa
        import rez.solver  # noqa
        import rez.status  # noqa
        import rez.suite  # noqa
        import rez.system  # noqa
        import rez.wrapper  # noqa

        import rez.utils._version  # noqa
        import rez.utils.backcompat  # noqa
        import rez.utils.colorize  # noqa
        import rez.utils.data_utils  # noqa
        import rez.utils.filesystem  # noqa
        import rez.utils.graph_utils  # noqa
        import rez.utils.lint_helper  # noqa
        import rez.utils.logging_  # noqa
        import rez.utils.platform_  # noqa
        import rez.utils.resources  # noqa
        import rez.utils.schema  # noqa
        import rez.utils.scope  # noqa
        import rez.utils.memcached  # noqa
        import rez.utils.yaml  # noqa


if __name__ == '__main__':
    unittest.main()
