from rez.tests.util import TestBase, TempdirMixin
from rez.resolved_context import ResolvedContext
from rez.suite import Suite
import rez.vendor.unittest2 as unittest
import uuid
import os.path


class TestRezSuites(TestBase, TempdirMixin):
    @classmethod
    def setUpClass(cls):
        TempdirMixin.setUpClass()

        path = os.path.dirname(__file__)
        packages_path = os.path.join(path, "data", "suites", "packages")
        cls.settings = dict(
            packages_path=[packages_path],
            implicit_packages=[],
            add_bootstrap_path=False,
            warn_untimestamped=False,
            resolve_caching=False)

    @classmethod
    def tearDownClass(cls):
        TempdirMixin.tearDownClass()

    def _test_serialization(self, suite):
        name = uuid.uuid4().hex
        path = os.path.join(self.root, name)
        suite.save(path)
        suite2 = Suite.load(path)
        self.assertEqual(suite.get_tools(), suite2.get_tools())
        self.assertEqual(set(suite.context_names), set(suite2.context_names))

    def test_1(self):
        """Test empty suite."""
        path = os.path.join(self.root, "suite1")
        s = Suite()
        tools = s.get_tools()
        self.assertEqual(tools, {})
        self._test_serialization(s)

    def test_2(self):
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

    def test_3(self):
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


def get_test_suites():
    suites = []
    suite = unittest.TestSuite()
    suite.addTest(TestRezSuites("test_1"))
    suite.addTest(TestRezSuites("test_2"))
    suite.addTest(TestRezSuites("test_3"))
    suites.append(suite)
    return suites


if __name__ == '__main__':
    unittest.main()
