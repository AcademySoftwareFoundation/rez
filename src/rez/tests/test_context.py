"""
test resolved contexts
"""
from rez.tests.util import TestBase, TempdirMixin
from rez.resolved_context import ResolvedContext
from rez.bind import hello_world
from rez.utils.platform_ import platform_
from rez.config import config
import rez.vendor.unittest2 as unittest
import subprocess
import os.path
import os


class TestContext(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls):
        TempdirMixin.setUpClass()

        packages_path = os.path.join(cls.root, "packages")
        os.makedirs(packages_path)
        hello_world.bind(packages_path)

        cls.settings = dict(
            packages_path=[packages_path],
            package_filter=None,
            implicit_packages=[],
            warn_untimestamped=False,
            resolve_caching=False)

    @classmethod
    def tearDownClass(cls):
        TempdirMixin.tearDownClass()

    def test_create_context(self):
        """Test creation of context."""
        r = ResolvedContext([])
        r.print_info()

        r = ResolvedContext(["hello_world"])
        r.print_info()

    def test_execute_command(self):
        """Test command execution in context."""
        if platform_.name == "windows":
            self.skipTest("This test does not run on Windows due to problems"
                          " with the automated binding of the 'hello_world'"
                          " executable.")

        r = ResolvedContext(["hello_world"])
        p = r.execute_command(["hello_world"], stdout=subprocess.PIPE)
        stdout, _ = p.communicate()
        stdout = stdout.strip()
        self.assertEqual(stdout, "Hello Rez World!")

    def test_serialize(self):
        """Test save/load of context."""
        # save
        file = os.path.join(self.root, "test.rxt")
        r = ResolvedContext(["hello_world"])
        r.save(file)
        # load
        r2 = ResolvedContext.load(file)
        self.assertEqual(r.resolved_packages, r2.resolved_packages)

    def test_orderer(self):
        """Test a resolve with an orderer"""
        from rez.package_order import VersionSplitPackageOrder, OrdererDict
        from rez.vendor.version.version import Version
        path = os.path.dirname(__file__)
        packages_path = os.path.join(path, "data", "solver", "packages")
        config.override("packages_path",
                        [packages_path])
        orderers = OrdererDict([
            VersionSplitPackageOrder(packages=["python"],
                                     first_version=Version("2.6"))])
        r = ResolvedContext(["python", "!python-2.6"],
                            package_orderers=orderers)
        resolved = [x.qualified_package_name for x in r.resolved_packages]
        self.assertEqual(resolved, ["python-2.5.2"])

        # make sure serializing the orderer works
        file = os.path.join(self.root, "test_orderers.rxt")
        r.save(file)
        r2 = ResolvedContext.load(file)
        self.assertEqual(r, r2)
        self.assertEqual(r.package_orderers, r2.package_orderers)


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
