"""
test importing of all source
"""
from rez.tests.util import TestBase
import unittest


class TestImports(TestBase):
    def test_1(self):
        """import every file in rez."""
        import rez
        import rez.build_process_
        import rez.build_system
        import rez.config
        import rez.exceptions
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
        import rez.utils.memcached
        import rez.utils.yaml


if __name__ == '__main__':
    unittest.main()


# Copyright 2013-2016 Allan Johns.
#
# This library is free software: you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.
