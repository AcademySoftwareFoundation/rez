from rez.tests.util import TestBase
import rez.vendor.unittest2 as unittest


class TestImports(TestBase):
    def test_1(self):
        """import every file in rez."""
        import rez
        import rez.build_process_
        import rez.build_system
        import rez.config
        import rez.exceptions
        import rez.memcache
        import rez.package_help
        import rez.package_maker__
        import rez.package_repository
        import rez.package_resources_
        import rez.package_search
        import rez.package_serialise
        import rez.packages_
        import rez.plugin_managers
        import rez.release_hook
        import rez.release_vcs
        import rez.resolved_context
        import rez.resolver
        import rez.rex
        import rez.rex_bindings
        import rez.serialise
        import rez.shells
        import rez.solver
        import rez.status
        import rez.suite
        import rez.system
        import rez.wrapper

        import rez.utils._version
        import rez.utils.backcompat
        import rez.utils.colorize
        import rez.utils.data_utils
        import rez.utils.filesystem
        import rez.utils.graph_utils
        import rez.utils.lint_helper
        import rez.utils.logging_
        import rez.utils.platform_
        import rez.utils.resources
        import rez.utils.schema
        import rez.utils.scope
        import rez.utils.yaml

def get_test_suites():
    suites = []
    suite = unittest.TestSuite()
    suite.addTest(TestImports("test_1"))
    suites.append(suite)
    return suites


if __name__ == '__main__':
    unittest.main()
