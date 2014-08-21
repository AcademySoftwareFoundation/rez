import rez.vendor.unittest2 as unittest
from rez.tests.util import TestBase
from rez.exceptions import ConfigurationError
from rez.config import Config
from rez.system import system
from rez import module_root_path
from rez.util import RO_AttrDictWrapper
from rez.packages import load_developer_package
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

        # second override
        c.override("build_directory", "flabber")
        self.assertEqual(c.build_directory, "flabber")

        self._test_basic(c)

    def test_1(self):
        """Test just the root config file."""

        # do a full validation of a config
        c = Config([self.root_config_file], locked=True)
        c.validate_data()

        # check a few expected settings
        c = Config([self.root_config_file], locked=True)
        self._test_basic(c)
        self.assertEqual(c.warn_all, False)
        self.assertEqual(c.build_directory, "build")

        # check user path expansion
        self.assertEqual(c.local_packages_path,
                         os.path.expanduser("~/packages"))

        # check access to plugins settings common to a plugin type
        self.assertEqual(c.plugins.release_vcs.tag_name, '{qualified_name}')

        # check access to plugins settings
        self.assertEqual(c.plugins.release_hook.emailer.smtp_port, 25)

        # check system attribute expansion
        expected_value = "%s@rez-release.com" % system.user
        self.assertEqual(c.plugins.release_hook.emailer.sender, expected_value)

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

    def test_3(self):
        """Test environment variable config overrides."""
        c = Config([self.root_config_file], locked=False)

        # test basic env-var override
        os.environ["REZ_WARN_ALL"] = "1"
        self.assertEqual(c.warn_all, True)
        self._test_basic(c)

        # test env-var override that contains a system expansion
        os.environ["REZ_TMPDIR"] = "/tmp/{system.user}"
        expected_value = "/tmp/%s" % system.user
        self.assertEqual(c.tmpdir, expected_value)

        # _test_overrides overrides this value, so here we're making sure
        # that an API override takes precedence over an env-var override
        os.environ["BUILD_DIRECTORY"] = "flaabs"
        self._test_overrides(c)

    def test_4(self):
        """Test package config overrides."""
        pkg = load_developer_package(self.config_path)
        c = pkg.config
        self._test_basic(c)

        # check overrides from package.yaml are working
        os.environ["REZ_BUILD_DIRECTORY"] = "foo"  # should have no effect
        self.assertEqual(c.build_directory, "weeble")
        self.assertEqual(c.plugins.release_vcs.tag_name, "tag")

        # check system expansion in package overridden setting works
        expected_value = "%s@somewhere.com" % system.user
        self.assertEqual(c.plugins.release_hook.emailer.sender, expected_value)

        # check env-var expansion in package overridden setting works
        os.environ["FUNK"] = "dude"
        expected_value = ["FOO", "BAH_dude", "EEK"]
        self.assertEqual(c.parent_variables, expected_value)

        self._test_overrides(c)

    def test_5(self):
        """Test misconfigurations."""

        # overrides set to bad types
        overrides = {
            "build_directory": [],
            "plugins": {
                "release_hook": {
                    "emailer": {
                        "recipients": 42
                    }
                }
            }
        }
        c = Config([self.root_config_file], overrides=overrides, locked=False)
        with self.assertRaises(ConfigurationError):
            _ = c.build_directory
        with self.assertRaises(ConfigurationError):
            _ = c.plugins.release_hook.emailer.recipients

        # missing keys
        conf = os.path.join(self.config_path, "test1.yaml")
        c = Config([conf], locked=True)

        with self.assertRaises(ConfigurationError):
            _ = c.debug_all


def get_test_suites():
    suites = []
    suite = unittest.TestSuite()
    suite.addTest(TestConfig("test_1"))
    suite.addTest(TestConfig("test_2"))
    suite.addTest(TestConfig("test_3"))
    suite.addTest(TestConfig("test_4"))
    suite.addTest(TestConfig("test_5"))
    suites.append(suite)
    return suites


if __name__ == '__main__':
    unittest.main()
