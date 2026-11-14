# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
test suites
"""
from rez.tests.util import TestBase, TempdirMixin, \
    per_available_shell, install_dependent
from rez.resolved_context import ResolvedContext
from rez.suite import Suite
from rez.config import config
from rez.system import system
import subprocess
import unittest
import uuid
import os.path


class TestRezSuites(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls) -> None:
        TempdirMixin.setUpClass()

        packages_path = cls.data_path("suites", "packages")
        cls.settings = dict(
            packages_path=[packages_path],
            package_filter=None,
            implicit_packages=[],
            warn_untimestamped=False,
            resolve_caching=False)

    @classmethod
    def tearDownClass(cls) -> None:
        TempdirMixin.tearDownClass()

    def _test_serialization(self, suite) -> None:
        name = uuid.uuid4().hex
        path = os.path.join(self.root, name)
        suite.save(path)
        suite2 = Suite.load(path)
        self.assertEqual(suite.get_tools(), suite2.get_tools())
        self.assertEqual(set(suite.context_names), set(suite2.context_names))

    def test_save_over_symlinked_path_resolves_consistently(self) -> None:
        # Regression test (suite save through an alias): with
        # resolve_links_on_windows enabled on Windows, the previous code
        # deleted the RESOLVED suite target, then recreated directories
        # through the now-dangling alias - FileNotFoundError, and the suite
        # was already deleted. Deletion and recreation must operate on the
        # same physical destination.
        #
        # Simulation: on Windows, real_path() is an alias-preserving
        # abspath, while resolve_path() resolves. Patch real_path to its
        # Windows semantic so the mismatch conditions hold on any platform.
        s = Suite()
        physical = os.path.join(self.root, self._testMethodName, "my_suite")
        s.save(physical)

        alias = os.path.join(self.root, self._testMethodName, "suite_alias")
        os.symlink(physical, alias)

        s2 = Suite.load(alias)
        import unittest.mock
        # Model the Windows scenario this regression targets:
        # resolve_links_on_windows enabled (that is when real_path and
        # resolve_path diverge). With the setting off on native Windows,
        # resolve_path leaves the alias unresolved and rmtree refuses a
        # symlink. The setting is a no-op on other platforms.
        self.update_settings({"resolve_links_on_windows": True})
        with unittest.mock.patch("rez.suite.real_path", os.path.abspath):
            s2.save(alias)

        # the suite survived, and the alias still resolves to it
        self.assertTrue(os.path.isfile(os.path.join(physical, "suite.yaml")))
        self.assertTrue(os.path.isdir(os.path.join(physical, "contexts")))
        self.assertTrue(os.path.isfile(os.path.join(alias, "suite.yaml")))

    def test_1(self) -> None:
        """Test empty suite."""
        s = Suite()
        tools = s.get_tools()
        self.assertEqual(tools, {})
        self._test_serialization(s)

    def test_2(self) -> None:
        """Test basic suite."""
        c_foo = ResolvedContext(["foo"])
        c_bah = ResolvedContext(["bah"])
        s = Suite()
        s.add_context("foo", c_foo)
        s.add_context("bah", c_bah)

        expected_tools = set(["fooer", "bahbah", "blacksheep"])
        self.assertEqual(set(s.get_tools().keys()), expected_tools)

        s.set_context_prefix("foo", "fx_")
        expected_tools = set(["fx_fooer", "bahbah", "blacksheep"])
        self.assertEqual(set(s.get_tools().keys()), expected_tools)

        s.set_context_suffix("foo", "_fun")
        s.set_context_suffix("bah", "_anim")
        expected_tools = set(["fx_fooer_fun", "bahbah_anim", "blacksheep_anim"])
        self.assertEqual(set(s.get_tools().keys()), expected_tools)

        s.remove_context("bah")
        expected_tools = set(["fx_fooer_fun"])
        self.assertEqual(set(s.get_tools().keys()), expected_tools)

        s.add_context("bah", c_bah)
        expected_tools = set(["fx_fooer_fun", "bahbah", "blacksheep"])
        self.assertEqual(set(s.get_tools().keys()), expected_tools)

        s.alias_tool("bah", "blacksheep", "whitesheep")
        expected_tools = set(["fx_fooer_fun", "bahbah", "whitesheep"])
        self.assertEqual(set(s.get_tools().keys()), expected_tools)

        # explicit alias takes precedence over prefix/suffix
        s.alias_tool("foo", "fooer", "floober")
        expected_tools = set(["floober", "bahbah", "whitesheep"])
        self.assertEqual(set(s.get_tools().keys()), expected_tools)

        s.unalias_tool("foo", "fooer")
        s.unalias_tool("bah", "blacksheep")
        expected_tools = set(["fx_fooer_fun", "bahbah", "blacksheep"])
        self.assertEqual(set(s.get_tools().keys()), expected_tools)

        s.hide_tool("bah", "bahbah")
        expected_tools = set(["fx_fooer_fun", "blacksheep"])
        self.assertEqual(set(s.get_tools().keys()), expected_tools)

        s.unhide_tool("bah", "bahbah")
        expected_tools = set(["fx_fooer_fun", "bahbah", "blacksheep"])
        self.assertEqual(set(s.get_tools().keys()), expected_tools)

        self._test_serialization(s)

    def test_3(self) -> None:
        """Test tool clashes in a suite."""
        c_foo = ResolvedContext(["foo"])
        c_bah = ResolvedContext(["bah"])
        s = Suite()
        s.add_context("foo", c_foo)
        s.add_context("bah", c_bah)
        s.add_context("bah2", c_bah)

        expected_tools = set(["fooer", "bahbah", "blacksheep"])
        self.assertEqual(set(s.get_tools().keys()), expected_tools)
        self.assertEqual(s.get_tool_context("bahbah"), "bah2")
        self.assertEqual(s.get_tool_context("blacksheep"), "bah2")

        s.bump_context("bah")
        self.assertEqual(s.get_tool_context("bahbah"), "bah")
        self.assertEqual(s.get_tool_context("blacksheep"), "bah")

        expected_conflicts = set(["bahbah", "blacksheep"])
        self.assertEqual(set(s.get_conflicting_aliases()), expected_conflicts)

        s.set_context_prefix("bah", "hey_")
        expected_tools = set(["fooer", "bahbah", "blacksheep",
                              "hey_bahbah", "hey_blacksheep"])
        self.assertEqual(set(s.get_tools().keys()), expected_tools)

        s.remove_context_prefix("bah")
        expected_tools = set(["fooer", "bahbah", "blacksheep"])
        self.assertEqual(set(s.get_tools().keys()), expected_tools)

        self.assertEqual(s.get_tool_context("bahbah"), "bah")
        self.assertEqual(s.get_tool_context("blacksheep"), "bah")

        s.hide_tool("bah", "bahbah")
        self.assertEqual(s.get_tool_context("bahbah"), "bah2")
        s.unhide_tool("bah", "bahbah")
        self.assertEqual(s.get_tool_context("bahbah"), "bah")

        self._test_serialization(s)

    @per_available_shell()
    @install_dependent()
    def test_executable_versions(self, shell) -> None:
        """Test suite tool can list its package versions with ``++versions``.

        Regression test for https://github.com/AcademySoftwareFoundation/rez/issues/2046
        """
        config.override("default_shell", shell)

        c_foo = ResolvedContext(["foo"])
        s = Suite()
        s.add_context("foo", c_foo)

        per_shell = config.get("default_shell")
        suite_path = os.path.join(self.root, "test_suites", per_shell, "foo")
        s.save(suite_path)

        bin_path = os.path.join(suite_path, "bin")
        env = os.environ.copy()

        env.update(self.get_settings_env())
        env["PATH"] = os.pathsep.join([system.rez_bin_path, env["PATH"]])
        env["PATH"] = os.pathsep.join([bin_path, env["PATH"]])

        output = subprocess.check_output("fooer ++versions", shell=True, env=env,
                                         universal_newlines=True)

        lines = output.splitlines()
        self.assertEqual(len(lines), 1)
        columns = lines[0].split()
        self.assertEqual(columns[0], "*")
        self.assertEqual(columns[1], "foo")
        self.assertEqual(
            columns[2],
            self.data_path("suites", "packages", "foo", "package.yaml")
        )

    @per_available_shell()
    @install_dependent()
    def test_executable(self, shell) -> None:
        """Test suite tool can be executed

        Testing suite tool can be found and executed in multiple platforms.
        This test is equivalent to the following commands in shell:
        ```
        $ rez-env pooh --output pooh.rxt
        $ rez-suite --create pooh
        $ rez-suite --add pooh.rxt --context pooh pooh
        $ export PATH=$(pwd)/pooh/bin:$PATH
        $ hunny
        yum yum
        ```

        """
        config.override("default_shell", shell)

        c_pooh = ResolvedContext(["pooh"])
        s = Suite()
        s.add_context("pooh", c_pooh)

        expected_tools = set(["hunny"])
        self.assertEqual(set(s.get_tools().keys()), expected_tools)

        per_shell = config.get("default_shell")
        suite_path = os.path.join(self.root, "test_suites", per_shell, "pooh")
        s.save(suite_path)

        bin_path = os.path.join(suite_path, "bin")
        env = os.environ.copy()
        # activate rez, to access _rez_fwd
        env["PATH"] = os.pathsep.join([system.rez_bin_path, env["PATH"]])
        # activate suite
        env["PATH"] = os.pathsep.join([bin_path, env["PATH"]])

        output = subprocess.check_output(["hunny"], shell=True, env=env,
                                         universal_newlines=True)
        self.assertTrue("yum yum" in output)


if __name__ == '__main__':
    unittest.main()
