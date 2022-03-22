# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
test completions
"""
import unittest
from rez.tests.util import TestBase
from rez.config import Config, get_module_root_config
from rez.packages import get_completions


class TestCompletion(TestBase):
    @classmethod
    def setUpClass(cls):
        packages_path = cls.data_path("solver", "packages")
        cls.settings = dict(
            packages_path=[packages_path],
            package_filter=None)

        cls.config = Config([get_module_root_config()], locked=True)

    def test_config(self):
        """Test config completion."""
        def _eq(prefix, expected_completions):
            completions = self.config.get_completions(prefix)
            self.assertEqual(set(completions), set(expected_completions))

        _eq("zzz", [])
        _eq("pref", ["prefix_prompt"])
        _eq("plugin", ["plugins",
                       "plugin_path"])
        _eq("plugins", ["plugins",
                        "plugins.command",
                        "plugins.package_repository",
                        "plugins.build_process",
                        "plugins.build_system",
                        "plugins.release_hook",
                        "plugins.release_vcs",
                        "plugins.shell"])
        _eq("plugins.release_vcs.releasable_",
            ["plugins.release_vcs.releasable_branches"])

    def test_packages(self):
        """Test packages completion."""
        def _eq(prefix, expected_completions):
            completions = get_completions(prefix)
            self.assertEqual(set(completions), set(expected_completions))

        _eq("zzz", [])
        _eq("", ["bahish", "nada", "nopy", "pybah", "pydad", "pyfoo", "pymum",
                 "pyodd", "pyson", "pysplit", "python", "pyvariants",
                 "test_variant_split_start", "test_variant_split_mid1",
                 "test_variant_split_mid2", "test_variant_split_end"])
        _eq("py", ["pybah", "pydad", "pyfoo", "pymum", "pyodd", "pyson",
            "pysplit", "python", "pyvariants"])
        _eq("pys", ["pyson", "pysplit"])
        _eq("pyb", ["pybah", "pybah-4", "pybah-5"])
        _eq("pybah-", ["pybah-4", "pybah-5"])
        _eq("pyfoo-3.0", ["pyfoo-3.0.0"])


if __name__ == '__main__':
    unittest.main()
