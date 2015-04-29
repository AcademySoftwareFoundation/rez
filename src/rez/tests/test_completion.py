import rez.vendor.unittest2 as unittest
from rez.tests.util import TestBase
from rez.config import Config, get_module_root_config
from rez.packages_ import get_completions
import os
import os.path


class TestCompletion(TestBase):
    @classmethod
    def setUpClass(cls):
        path = os.path.dirname(__file__)
        packages_path = os.path.join(path, "data", "solver", "packages")
        cls.settings = dict(
            packages_path=[packages_path])

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
                 "pyodd", "pyson", "pysplit", "python", 'eek', 'bar', 'foo',
                 'variable_variant_package_in_single_column', 'bah',
                 'package_name_in_require_and_variant', 'asymmetric_variants',
                 'multi_version_variant_higher_to_lower_version_order',
                 'multi_version_variant_lower_to_higher_version_order',
                 'permuted_family_names_same_position_weight',
                 'variant_ordered_alphabetically_reversed_same_version',
                 'variant_ordered_alphabetically_reversed_diff_version',
                 'variant_ordered_alphabetically_same_version',
                 'variant_ordered_alphabetically_diff_version',
                 'multi_packages_variant_unsorted', 'permuted_family_names',
                 'variant_with_weak_package_in_variant',
                 'three_packages_in_variant', 'variant_with_antipackage',
                 'multi_packages_variant_sorted',
                 'two_packages_in_variant_unsorted'])
        _eq("py", ["pybah", "pydad", "pyfoo", "pymum", "pyodd", "pyson",
            "pysplit", "python"])
        _eq("pys", ["pyson", "pysplit"])
        _eq("pyb", ["pybah", "pybah-4", "pybah-5"])
        _eq("pybah-", ["pybah-4", "pybah-5"])
        _eq("pyfoo-3.0", ["pyfoo-3.0.0"])


def get_test_suites():
    suites = []
    suite = unittest.TestSuite()
    suite.addTest(TestCompletion("test_config"))
    suite.addTest(TestCompletion("test_packages"))
    suites.append(suite)
    return suites


if __name__ == '__main__':
    unittest.main()
