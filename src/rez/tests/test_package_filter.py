# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Test cases for package_filter.py (package filtering)
"""
from rez.tests.util import TestBase
from rez.packages import iter_packages
from rez.vendor.version.requirement import Requirement
from rez.package_filter import PackageFilter, PackageFilterList, GlobRule, \
    RegexRule, RangeRule, TimestampRule


class TestPackageFilter(TestBase):
    """Tests package filtering.
    """
    @classmethod
    def setUpClass(cls):
        cls.py_packages_path = cls.data_path("packages", "py_packages")
        cls.solver_packages_path = cls.data_path("solver", "packages")

        cls.settings = dict(
            packages_path=[
                cls.solver_packages_path,
                cls.py_packages_path
            ],
            package_filter=None)

    def _test(self, fltr, pkg_family, expected_result):

        # convert from json if required
        if isinstance(fltr, dict):
            fltr = PackageFilter.from_pod(fltr)
        elif isinstance(fltr, list):
            fltr = PackageFilterList.from_pod(fltr)

        def filter_versions(fltr_):
            matching_versions = set()

            for pkg in iter_packages(pkg_family):
                if not fltr_.excludes(pkg):
                    matching_versions.add(str(pkg.version))

            self.assertEqual(matching_versions, set(expected_result))

        # apply filter to all pkg versions
        filter_versions(fltr)

        # serialise to/from json and do it again
        data = fltr.to_pod()
        fltr2 = fltr.from_pod(data)
        filter_versions(fltr2)

    def test_empty_filter(self):
        """Test that empty filter has no effect
        """
        fltr = PackageFilter()
        self._test(
            fltr,
            "pydad",
            ["1", "2", "3"]
        )

    def test_empty_filter_list(self):
        """Test that empty filter list has no effect
        """
        fltr = PackageFilterList()
        self._test(
            fltr,
            "pydad",
            ["1", "2", "3"]
        )

    def test_glob_filter(self):
        """Test the glob filter.
        """
        fltr = PackageFilter()
        fltr.add_exclusion(GlobRule("timestamped-*.5"))

        self._test(
            fltr,
            "timestamped",
            [
                "1.0.6",
                "1.1.0",
                "1.1.1",
                "1.2.0",
                "2.0.0",
                "2.1.0"
            ]
        )

    def test_regex_filter(self):
        """Test the regex filter.
        """
        fltr = PackageFilter()
        fltr.add_exclusion(RegexRule("timestamped-1.[1|2].*"))

        self._test(
            fltr,
            "timestamped",
            [
                "1.0.5",
                "1.0.6",
                "2.0.0",
                "2.1.0",
                "2.1.5"
            ]
        )

    def test_range_filter(self):
        """Test the range filter.
        """
        fltr = PackageFilter()
        fltr.add_exclusion(RangeRule(Requirement("timestamped-1.1+")))

        self._test(
            fltr,
            "timestamped",
            [
                "1.0.5",
                "1.0.6"
            ]
        )

    def test_timestamp_filter(self):
        """Test the timestamp filter.
        """
        fltr = PackageFilter()
        fltr.add_exclusion(TimestampRule(6999, family="timestamped"))

        self._test(
            fltr,
            "timestamped",
            [
                "2.1.0",
                "2.1.5"
            ]
        )

    def test_otherfam_filter(self):
        """Test that a filter on a different fam has no effect
        """
        fltr = PackageFilter()
        fltr.add_exclusion(GlobRule("timestamped-*"))

        self._test(
            fltr,
            "pydad",
            ["1", "2", "3"]
        )

    def test_excl_and_incl(self):
        """Test that combo of exclusion and inclusion works as expected
        """
        self._test(
            {
                "excludes": ["glob(*.5)"],
                "includes": ["range(timestamped-2)"]
            },
            "timestamped",
            [
                # "1.0.5",  due to excludes
                "1.0.6",
                "1.1.0",
                "1.1.1",
                "1.2.0",
                "2.0.0",
                "2.1.0",
                "2.1.5"  # due to includes
            ]
        )

    def test_filter_list(self):
        """Test that logic wrt list of filters works as expected
        """

        # exclude all *.0 packages, and all 2.* packages except for pymum
        fltrs = [
            # fltr-1
            {
                "excludes": ["*.0"]
            },
            # fltr-2
            {
                "excludes": ["*-2.*"],
                "includes": ["pymum"]
            }
        ]

        self._test(
            fltrs,
            "timestamped",
            [
                "1.0.5",
                "1.0.6",
                # "1.1.0",  due to fltr-1
                "1.1.1",
                # "1.2.0",  due to fltr-1
                # "2.0.0",  due to fltr-1 and fltr-2
                # "2.1.0",  due to fltr-1 and fltr-2
                # "2.1.5"   due to fltr-2
            ]
        )

        self._test(
            fltrs,
            "pymum",
            ["1", "2", "3"]
        )
