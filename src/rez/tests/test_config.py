import rez.vendor.unittest2 as unittest
from rez.tests.util import TestBase
from rez.config import Config
from rez.system import system
from rez import module_root_path
from rez.util import RO_AttrDictWrapper
import os
import os.path


class TestConfig(TestBase):
    @classmethod
    def setUpClass(cls):
        cls.settings = {}
        cls.root_config_file = os.path.join(module_root_path, "rezconfig")
        path = os.path.dirname(__file__)
        cls.config_path = os.path.join(path, "data", "config")

    def _test_basic(self, c):
        self.assertEqual(type(c.warn_all), bool)
        self.assertEqual(type(c.build_directory), str)

        # plugin settings
        p = c.plugins
        self.assertEqual(type(p.release_hook.emailer), RO_AttrDictWrapper)
        self.assertEqual(type(p.release_hook.emailer.sender), str)
        self.assertEqual(type(p.release_hook.emailer.smtp_port), int)

        # plugin settings common to a plugin type
        self.assertEqual(type(p.release_vcs.tag_name), str)

    def _test_overrides(self, c):
        c.override("debug_none", True)
        c.override("build_directory", "floober")
        c.override("plugins.release_vcs.tag_name", "bah")
        c.override("plugins.release_hook.emailer.sender", "joe.bloggs")

        self.assertEqual(c.debug_none, True)
        self.assertEqual(c.build_directory, "floober")
        self.assertEqual(c.plugins.release_vcs.tag_name, "bah")
        self.assertEqual(c.plugins.release_hook.emailer.sender, "joe.bloggs")

        self._test_basic(c)

    def test_1(self):
        """Test just the root config file."""
        c = Config([self.root_config_file], locked=True)
        self._test_basic(c)
        self.assertEqual(c.warn_all, False)
        self.assertEqual(c.build_directory, "build")

        # check user path expansion
        self.assertEqual(c.local_packages_path,
                         os.path.expanduser("~/packages"))

        # check access to plugins settings common to a plugin type
        self.assertEqual(c.plugins.release_vcs.tag_name, '{name}-{version}')

        # check access to plugins settings
        self.assertEqual(c.plugins.release_hook.emailer.smtp_port, 25)

        # check system attribute expansion
        sender = "%s@rez-release.com" % system.user
        self.assertEqual(c.plugins.release_hook.emailer.sender, sender)

        # check that an env-var override doesn't affect locked config
        os.environ["REZ_WARN_NONE"] = "true"
        self.assertEqual(c.warn_none, False)

        self._test_overrides(c)

    def test_2(self):
        """Test a config with an overriding file."""
        conf = os.path.join(self.config_path, "test1.yaml")
        c = Config([self.root_config_file, conf], locked=True)
        self._test_basic(c)

        # check overrides in test1.yaml are being used
        self.assertEqual(c.warn_all, True)
        self.assertEqual(c.plugins.release_vcs.tag_name, "foo")
        self.assertEqual(c.plugins.release_hook.emailer.sender,
                         "santa.claus")

        self._test_overrides(c)


def get_test_suites():
    suites = []
    suite = unittest.TestSuite()
    suite.addTest(TestConfig("test_1"))
    suite.addTest(TestConfig("test_2"))
    suites.append(suite)
    return suites


if __name__ == '__main__':
    unittest.main()
