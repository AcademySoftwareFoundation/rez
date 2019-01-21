"""
test resolved contexts
"""
from rez.tests.util import restore_os_environ, restore_sys_path, TempdirMixin, \
    TestBase
from rez.resolved_context import ResolvedContext
from rez.bind import hello_world
from rez.utils.platform_ import platform_
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

    def test_apply(self):
        """Test apply() function."""
        # Isolate our changes to os.environ and sys.path and return to the
        # original state to not mess with our test environment.
        with restore_os_environ(), restore_sys_path():
            r = ResolvedContext(["hello_world"])
            r.apply()
            self.assertEqual(os.environ.get("OH_HAI_WORLD"), "hello")

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

    def test_execute_command_environ(self):
        """Test that execute_command properly sets environ dict."""
        parent_environ = {"BIGLY": "covfefe"}
        r = ResolvedContext(["hello_world"])

        pycode = ("import os; "
                  "print os.getenv(\"BIGLY\"); "
                  "print os.getenv(\"OH_HAI_WORLD\")")

        args = ["python", "-c", pycode]

        p = r.execute_command(args, parent_environ=parent_environ,
                              stdout=subprocess.PIPE)
        stdout, _ = p.communicate()
        stdout = stdout.strip()
        parts = [x.strip() for x in stdout.split('\n')]

        self.assertEqual(parts, ["covfefe", "hello"])

    def test_serialize(self):
        """Test save/load of context."""
        # save
        file = os.path.join(self.root, "test.rxt")
        r = ResolvedContext(["hello_world"])
        r.save(file)
        # load
        r2 = ResolvedContext.load(file)
        self.assertEqual(r.resolved_packages, r2.resolved_packages)


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
