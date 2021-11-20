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


"""
test resolved contexts
"""
from rez.tests.util import restore_os_environ, restore_sys_path, TempdirMixin, \
    TestBase
from rez.resolved_context import ResolvedContext
from rez.bundle_context import bundle_context
from rez.bind import hello_world
from rez.utils.platform_ import platform_
from rez.utils.filesystem import is_subdirectory
import unittest
import subprocess
import platform
import shutil
import os.path
import os


class TestContext(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls):
        TempdirMixin.setUpClass()

        cls.packages_path = os.path.join(cls.root, "packages")
        os.makedirs(cls.packages_path)
        hello_world.bind(cls.packages_path)

        cls.settings = dict(
            packages_path=[cls.packages_path],
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

    # TODO make shell-dependent (wait until port to pytest)
    def test_execute_command(self):
        """Test command execution in context."""
        if platform_.name == "windows":
            self.skipTest("This test does not run on Windows due to problems"
                          " with the automated binding of the 'hello_world'"
                          " executable.")

        r = ResolvedContext(["hello_world"])
        p = r.execute_command(["hello_world"], stdout=subprocess.PIPE, text=True)
        stdout, _ = p.communicate()
        stdout = stdout.strip()
        self.assertEqual(stdout, "Hello Rez World!")

    def test_execute_command_environ(self):
        """Test that execute_command properly sets environ dict."""
        r = ResolvedContext(["hello_world"])
        self._test_execute_command_environ(r)

    def _test_execute_command_environ(self, r):
        pycode = ("import os; "
                  "print(os.getenv(\"BIGLY\")); "
                  "print(os.getenv(\"OH_HAI_WORLD\"))")

        args = ["python", "-c", pycode]

        parent_environ = {"BIGLY": "covfefe"}
        p = r.execute_command(args, parent_environ=parent_environ,
                              stdout=subprocess.PIPE)
        stdout, _ = p.communicate()
        stdout = stdout.strip()
        parts = [x.strip() for x in stdout.decode("utf-8").split('\n')]

        self.assertEqual(parts, ["covfefe", "hello"])

    def test_serialize(self):
        """Test context serialization."""

        # save
        file = os.path.join(self.root, "test.rxt")
        r = ResolvedContext(["hello_world"])
        r.save(file)

        # load
        r2 = ResolvedContext.load(file)
        self.assertEqual(r.resolved_packages, r2.resolved_packages)

        # verify
        env = r2.get_environ()
        self.assertEqual(env.get("OH_HAI_WORLD"), "hello")

    def test_retarget(self):
        """Test that a retargeted context behaves identically."""

        # make a copy of the pkg repo
        packages_path2 = os.path.join(self.root, "packages2")
        shutil.copytree(self.packages_path, packages_path2)

        # create a context, retarget to pkg repo copy
        r = ResolvedContext(["hello_world"])
        r2 = r.retargeted(package_paths=[packages_path2])

        # check the pkg we contain is in the copied pkg repo
        variant = r2.resolved_packages[0]
        self.assertTrue(is_subdirectory(variant.root, packages_path2))

        self._test_execute_command_environ(r2)

    def test_bundled(self):
        """Test that a bundled context behaves identically."""

        def _test_bundle(path):
            # load the bundled context
            r2 = ResolvedContext.load(os.path.join(path, "context.rxt"))

            # check the pkg we contain is in the bundled pkg repo
            variant = r2.resolved_packages[0]
            self.assertTrue(
                is_subdirectory(variant.root, path),
                "Expected variant root %r of variant %r to be a subdirectory of %r"
                % (variant.root, variant.uri, path)
            )

            self._test_execute_command_environ(r2)

        bundle_path = os.path.join(self.root, "bundle")

        # create context and bundle it
        r = ResolvedContext(["hello_world"])
        bundle_context(
            context=r,
            dest_dir=bundle_path,
            force=True,
            verbose=True
        )

        # test the bundle
        _test_bundle(bundle_path)

        # copy the bundle and test the copy
        bundle_path2 = os.path.join(self.root, "bundle2")
        shutil.copytree(bundle_path, bundle_path2)
        _test_bundle(bundle_path2)

        # Create a bundle in a symlinked dest path. Bugs can arise where the
        # real path is used in some places and not others.
        #
        if platform.system().lower() in ("linux", "darwin"):
            hard_path = os.path.join(self.root, "foo")
            bundles_path = os.path.join(self.root, "bundles")
            bundle_path3 = os.path.join(bundles_path, "bundle3")

            os.mkdir(hard_path)
            os.symlink(hard_path, bundles_path)

            r = ResolvedContext(["hello_world"])
            bundle_context(
                context=r,
                dest_dir=bundle_path3,
                force=True,
                verbose=True
            )

            _test_bundle(bundle_path3)


if __name__ == '__main__':
    unittest.main()
