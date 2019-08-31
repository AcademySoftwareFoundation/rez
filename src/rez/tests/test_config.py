"""
test configuration settings
"""
import unittest
from rez.tests.util import TestBase
from rez.exceptions import ConfigurationError
from rez.config import Config, get_module_root_config, _replace_config
from rez.system import system
from rez.utils.data_utils import RO_AttrDictWrapper
from rez.packages_ import get_developer_package
import os
import os.path


class TestConfig(TestBase):
    @classmethod
    def setUpClass(cls):
        cls.settings = {}
        cls.root_config_file = get_module_root_config()
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

        # remove override
        value = c.tmpdir or ''
        new_value = value + '_'
        c.override("tmpdir", new_value)
        self.assertEqual(c.tmpdir, new_value)
        c.remove_override("tmpdir")
        value_ = c.tmpdir or ''
        self.assertEqual(value_, value)

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
                         os.path.expanduser(os.path.join("~", "packages")))

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
        REZ_TMPDIR_ = os.environ.get("REZ_TMPDIR")
        os.environ["REZ_TMPDIR"] = "/tmp/{system.user}"
        expected_value = "/tmp/%s" % system.user
        self.assertEqual(c.tmpdir, expected_value)
        if REZ_TMPDIR_:
            os.environ["REZ_TMPDIR"] = REZ_TMPDIR_
        else:
            del os.environ["REZ_TMPDIR"]
        c._uncache("tmpdir")

        # _test_overrides overrides this value, so here we're making sure
        # that an API override takes precedence over an env-var override
        os.environ["BUILD_DIRECTORY"] = "flaabs"
        self._test_overrides(c)

    def test_4(self):
        """Test package config overrides."""
        conf = os.path.join(self.config_path, "test2.py")
        config2 = Config([self.root_config_file, conf])

        with _replace_config(config2):
            pkg = get_developer_package(self.config_path)
            c = pkg.config
            self._test_basic(c)

            # check overrides from package.py are working
            os.environ["REZ_BUILD_DIRECTORY"] = "foo"  # should have no effect
            self.assertEqual(c.build_directory, "weeble")
            self.assertEqual(c.plugins.release_vcs.tag_name, "tag")

            # check list modification is working
            self.assertEqual(c.release_hooks, ["foo", "bah"])

            # check list modification within plugin settings is working
            self.assertEqual(c.plugins.release_hook.emailer.recipients,
                             ["joe@here.com", "jay@there.com"])

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


    def test_6(self):
        """Test setting of dict values from environ"""
        from rez.config import Dict
        from rez.vendor.schema.schema import Schema

        class TestConfig(Config):
            schema = Schema({
                'dumb_dict': Dict,
            })

            DEFAULT_DUMB_DICT = {'default': 'value'}

            # don't want to bother writing a file just to set a default value,
            # and can't use overrides, as that will make it ignore env vars...
            @property
            def _data(self):
                return {'dumb_dict': self.DEFAULT_DUMB_DICT}


        # need to NOT use locked, because we want to test setting from env
        # vars, but don't want values from "real" os.environ to pollute our
        # test...
        old_environ = os.environ
        try:
            os.environ = {}
            c = TestConfig([])
            self.assertEqual(c.dumb_dict, TestConfig.DEFAULT_DUMB_DICT)

            os.environ = {'REZ_DUMB_DICT': 'foo:bar,more:stuff'}
            c = TestConfig([])
            self.assertEqual(c.dumb_dict, {'foo': 'bar', 'more': 'stuff'})
        finally:
            os.environ = old_environ

    def test_7(self):
        """Test path list environment variable with whitespace."""
        c = Config([self.root_config_file], locked=False)

        # test basic env-var override
        packages_path = [
            "/foo bar/baz",
            "/foo bar/baz hey",
            "/home/foo bar/baz",
        ]
        os.environ["REZ_PACKAGES_PATH"] = os.pathsep.join(packages_path)

        self.assertEqual(c.packages_path, packages_path)


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
