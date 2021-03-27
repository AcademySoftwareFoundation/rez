"""
Test cases for package_order.py (package ordering)
"""
import json

from rez.config import config
from rez.package_order import NullPackageOrder, PackageOrder, PerFamilyOrder, VersionSplitPackageOrder, \
    TimestampPackageOrder, SortedOrder, PackageOrderList, from_pod
from rez.packages_ import iter_packages
from rez.tests.util import TestBase, TempdirMixin
from rez.vendor.version.version import Version


class _BaseTestPackagesOrder(TestBase, TempdirMixin):
    """Base class for a package ordering test case"""
    @classmethod
    def setUpClass(cls):
        TempdirMixin.setUpClass()

        cls.py_packages_path = cls.data_path("packages", "py_packages")
        cls.solver_packages_path = cls.data_path("solver", "packages")

        cls.settings = dict(
            packages_path=[
                cls.solver_packages_path,
                cls.py_packages_path
            ],
            package_filter=None)

    @classmethod
    def tearDownClass(cls):
        TempdirMixin.tearDownClass()

    def _test_reorder(self, orderer, package_name, expected_order):
        """Ensure ordered order package version as expected."""
        it = iter_packages(package_name)
        descending = sorted(it, key=lambda x: x.version, reverse=True)
        ordered = orderer.reorder(descending) or descending
        result = [str(x.version) for x in ordered]
        self.assertEqual(expected_order, result)

    def _test_pod(self, orderer):
        """Ensure an orderer integrity when serialized to pod."""
        pod = json.loads(json.dumps(orderer.to_pod()))  # roundtrip to JSON
        actual = orderer.__class__.from_pod(pod)
        self.assertEqual(orderer, actual)


class TestAbstractPackageOrder(TestBase):
    """Test case for the abstract PackageOrder class"""

    def test_reorder(self):
        """Validate reorder is not implemented"""
        with self.assertRaises(NotImplementedError):
            PackageOrder().reorder([])

    def test_to_pod(self):
        """Validate to_pod is not implemented"""
        self.assertRaises(NotImplementedError, PackageOrder().to_pod)

    def test_str(self):
        """Validate __str__ is not implemented"""
        with self.assertRaises(NotImplementedError):
            str(PackageOrder())

    def test_eq(self):
        """Validate __eq__ is not implemented"""
        with self.assertRaises(NotImplementedError):
            PackageOrder() == PackageOrder()


class TestNullPackageOrder(_BaseTestPackagesOrder):
    """Test case for the NullPackageOrder class"""

    def test_repr(self):
        """Validate we can represent a VersionSplitPackageOrder as a string."""
        self.assertEqual("NullPackageOrder({})", repr(NullPackageOrder()))

    def test_comparison(self):
        """Validate we can compare VersionSplitPackageOrder together."""
        inst1 = NullPackageOrder()
        inst2 = NullPackageOrder()
        self.assertTrue(inst1 == inst2)  # __eq__ positive
        self.assertFalse(inst1 == "wrong_type")  # __eq__ negative (wrong type)
        self.assertTrue(inst1 != "wrong_type")  # __ne__ positive (wrong type)
        self.assertFalse(inst1 != inst2)  # __ne__ negative

    def test_pod(self):
        """Validate we can save and load a VersionSplitPackageOrder to it's pod representation."""
        self._test_pod(NullPackageOrder())

    def test_sha1(self):
        """Validate we can get a sha1 hash.
        """
        self.assertEqual(
            'bf7c2fa4e6bd198c02adeea2c3a382cf57242051', NullPackageOrder().sha1
        )


class TestSortedOrder(_BaseTestPackagesOrder):
    """Test case for the SortedOrder class"""

    def test_reorder_ascending(self):
        """Validate we can sort packages in ascending order."""
        self._test_reorder(SortedOrder(descending=False), "pymum", ["1", "2", "3"])

    def test_reorder_descending(self):
        """Validate we can sort packages in descending order."""
        self._test_reorder(SortedOrder(descending=True), "pymum", ["3", "2", "1"])

    def test_comparison(self):
        """Validate we can compare SortedOrder together."""
        inst1 = SortedOrder(descending=False)
        inst2 = SortedOrder(descending=False)
        inst3 = SortedOrder(descending=True)
        self.assertTrue(inst1 == inst2)  # __eq__ positive
        self.assertFalse(inst1 == inst3)  # __eq__ negative
        self.assertTrue(inst1 != inst3)  # __ne__ positive
        self.assertFalse(inst1 != inst2)  # __ne__ negative
        self.assertFalse(inst1 == "wrong_type")  # __eq__ negative (wrong type)
        self.assertTrue(inst1 != "wrong_type")  # __eq__ negative (wrong type)

    def test_repr(self):
        """Validate we can represent a SortedOrder as a string."""
        self.assertEqual("SortedOrder(True)", repr(SortedOrder(descending=True)))

    def test_pod(self):
        """Validate we can save and load a SortedOrder to it's pod representation."""
        self._test_pod(SortedOrder(descending=True))


class TestPerFamilyOrder(_BaseTestPackagesOrder):
    """Test case for the PerFamilyOrder class"""

    def test_reorder(self):
        """Test ordering."""
        expected_null_result = ["7", "6", "5"]
        expected_split_result = ["2.6.0", "2.5.2", "2.7.0", "2.6.8"]
        expected_timestamp_result = ["1.1.1", "1.1.0", "1.0.6", "1.0.5", "1.2.0", "2.0.0", "2.1.5", "2.1.0"]

        orderer = PerFamilyOrder(
            order_dict=dict(
                pysplit=NullPackageOrder(),
                python=VersionSplitPackageOrder(Version("2.6.0")),
                timestamped=TimestampPackageOrder(timestamp=3001, rank=3)
            ),
            default_order=SortedOrder(descending=False)
        )

        self._test_reorder(orderer, "pysplit", expected_null_result)
        self._test_reorder(orderer, "python", expected_split_result)
        self._test_reorder(orderer, "timestamped", expected_timestamp_result)
        self._test_reorder(orderer, "pymum", ["1", "2", "3"])

    def test_reorder_no_packages(self):
        """Validate ordering for a family with no packages."""
        orderer = PerFamilyOrder(order_dict=dict(missing_package=NullPackageOrder()))
        self._test_reorder(orderer, "missing_package", [])

    def test_reorder_no_default_order(self):
        """Test behavior when there's no secondary default_order."""
        fam_orderer = PerFamilyOrder(order_dict={})
        self._test_reorder(fam_orderer, "pymum", ["3", "2", "1"])

    def test_comparison(self):
        """Validate we can compare PerFamilyOrder."""
        inst1 = PerFamilyOrder(order_dict={'foo': NullPackageOrder()}, default_order=NullPackageOrder())
        inst2 = PerFamilyOrder(order_dict={'foo': NullPackageOrder()}, default_order=NullPackageOrder())
        inst3 = PerFamilyOrder(order_dict={'bar': NullPackageOrder()}, default_order=NullPackageOrder())
        inst4 = PerFamilyOrder(order_dict={'foo': NullPackageOrder()}, default_order=None)
        self.assertTrue(inst1 == inst2)  # __eq__ positive
        self.assertFalse(inst1 == inst3)  # __eq__ negative (different order dict)
        self.assertFalse(inst1 == inst4)  # __eq__ negative (different default_order)
        self.assertTrue(inst1 != inst3)  # __ne__ positive (different order dict)
        self.assertTrue(inst1 != inst4)  # __ne__ positive (different default order)
        self.assertFalse(inst1 != inst2)  # __ne__ negative

    def test_repr(self):
        """Validate we can represent a PerFamilyOrder as a string."""
        inst = PerFamilyOrder(order_dict={"family1": VersionSplitPackageOrder(Version("2.6.0"))})
        self.assertEqual("PerFamilyOrder(([('family1', '2.6.0')], 'None'))", repr(inst))

    def test_pod(self):
        """Validate we can save and load a PerFamilyOrder to it's pod representation."""
        self._test_pod(
            PerFamilyOrder(order_dict={'foo': NullPackageOrder()}, default_order=NullPackageOrder())
        )

        # No default_order
        self._test_pod(
            PerFamilyOrder(order_dict={'foo': NullPackageOrder()})
        )


class TestVersionSplitPackageOrder(_BaseTestPackagesOrder):
    """Test case for the VersionSplitPackageOrder class"""

    def test_reordere(self):
        """Validate package ordering with a VersionSplitPackageOrder"""
        orderer = VersionSplitPackageOrder(Version("2.6.0"))
        expected = ["2.6.0", "2.5.2", "2.7.0", "2.6.8"]
        self._test_reorder(orderer, "python", expected)

    def test_comparison(self):
        """Validate we can compare VersionSplitPackageOrder together."""
        inst1 = VersionSplitPackageOrder(first_version=Version("1.2.3"))
        inst2 = VersionSplitPackageOrder(first_version=Version("1.2.3"))
        inst3 = VersionSplitPackageOrder(first_version=Version("1.2.4"))
        self.assertTrue(inst1 == inst2)  # __eq__ positive
        self.assertFalse(inst1 == inst3)  # __eq__ negative
        self.assertTrue(inst1 != inst3)  # __ne__ positive
        self.assertFalse(inst1 != inst2)  # __ne__ negative
        self.assertFalse(inst1 == "wrong_type")  # __eq__ negative (wrong type)
        self.assertTrue(inst1 != "wrong_type")  # __eq__ negative (wrong type)

    def test_repr(self):
        """Validate we can represent a VersionSplitPackageOrder as a string."""
        inst = VersionSplitPackageOrder(first_version=Version("1,2,3"))
        self.assertEqual("VersionSplitPackageOrder(1,2,3)", repr(inst))

    def test_pod(self):
        """Validate we can save and load a VersionSplitPackageOrder to it's pod representation."""
        self._test_pod(VersionSplitPackageOrder(first_version=Version("1.2.3")))


class TestTimestampPackageOrder(_BaseTestPackagesOrder):
    """Test cases for the TimestampPackageOrder class"""

    def test_reorder_no_rank(self):
        """Validate reordering with a rank of 0."""
        orderer = TimestampPackageOrder(timestamp=3001)
        expected = ['1.1.0', '1.0.6', '1.0.5', '1.1.1', '1.2.0', '2.0.0', '2.1.0', '2.1.5']
        self._test_reorder(orderer, "timestamped", expected)

    def test_reorder_rank_3(self):
        """Validate reordering with a rank of 3."""
        # after v1.1.0 and before v1.1.1
        orderer1 = TimestampPackageOrder(timestamp=3001, rank=3)
        expected1 = ["1.1.1", "1.1.0", "1.0.6", "1.0.5", "1.2.0", "2.0.0", "2.1.5", "2.1.0"]
        self._test_reorder(orderer1, "timestamped", expected1)

        # after v2.1.0 and before v2.1.5
        orderer2 = TimestampPackageOrder(timestamp=7001, rank=3)
        expected2 = ["2.1.5", "2.1.0", "2.0.0", "1.2.0", "1.1.1", "1.1.0", "1.0.6", "1.0.5"]
        self._test_reorder(orderer2, "timestamped", expected2)

    def test_reorder_rank_2(self):
        """Add coverage for a corner case where there's only one candidate without the rank."""
        orderer = TimestampPackageOrder(timestamp=4001, rank=3)  # 1.1.1
        expected = ['1.1.1', '1.1.0', '1.0.6', '1.0.5', '1.2.0', '2.0.0', '2.1.5', '2.1.0']
        self._test_reorder(orderer, "timestamped", expected)

    def test_reorder_packages_without_timestamps(self):
        """Validate reordering of packages that have no timestamp data."""
        orderer = TimestampPackageOrder(timestamp=3001)
        self._test_reorder(orderer, "pymum", ["3", "2", "1"])

    def test_reorder_all_packages_before_timestamp(self):
        """Test behavior when all packages are before the timestamp."""
        timestamp_orderer = TimestampPackageOrder(timestamp=9999999999, rank=3)
        expected = ['2.1.5', '2.1.0', '2.0.0', '1.2.0', '1.1.1', '1.1.0', '1.0.6', '1.0.5']
        self._test_reorder(timestamp_orderer, "timestamped", expected)

    def test_reorder_all_packages_after_timestamp(self):
        """Test behavior when all packages are after the timestamp."""
        timestamp_orderer = TimestampPackageOrder(timestamp=0, rank=3)
        expected = ['1.0.6', '1.0.5', '1.1.1', '1.1.0', '1.2.0', '2.0.0', '2.1.5', '2.1.0']
        self._test_reorder(timestamp_orderer, "timestamped", expected)

    def test_comparison(self):
        """Validate we can compare TimestampPackageOrder."""
        inst1 = TimestampPackageOrder(timestamp=1, rank=1)
        inst2 = TimestampPackageOrder(timestamp=1, rank=1)
        inst3 = TimestampPackageOrder(timestamp=2, rank=1)
        inst4 = TimestampPackageOrder(timestamp=2, rank=2)
        self.assertTrue(inst1 == inst2)  # __eq__ positive
        self.assertFalse(inst1 == inst3)  # __eq__ negative (different timestamp)
        self.assertFalse(inst1 == inst4)  # __eq__ negative (different rank)
        self.assertTrue(inst1 != inst3)  # __ne__ positive (different timestamp)
        self.assertTrue(inst1 != inst4)  # __ne__ positive (different rank)
        self.assertFalse(inst1 != inst2)  # __ne__ negative

    def test_repr(self):
        """Validate we can represent a TimestampPackageOrder as a string."""
        inst = TimestampPackageOrder(timestamp=1, rank=2)
        self.assertEqual(repr(inst), "TimestampPackageOrder((1, 2))")

    def test_pod(self):
        """Validate we can save and load a TimestampPackageOrder to pod representation."""
        self._test_pod(TimestampPackageOrder(timestamp=3001, rank=3))


class TestPackageOrdererList(_BaseTestPackagesOrder):
    """Test cases for the PackageOrderList class."""

    def test_singleton(self):
        """Validate we can build a PackageOrderList object from configuration values."""
        config.override("package_orderers", [
            {
                "type": "per_family",
                "orderers": [
                    {
                        "packages": ["python"],
                        "type": "version_split",
                        "first_version": "2.9.9"
                    }
                ]
            }
        ])
        expected = PackageOrderList()
        expected.append(PerFamilyOrder(order_dict={
            "python": VersionSplitPackageOrder(Version("2.9.9"))
        }))

        # Clear @classproperty cache
        try:
            delattr(PackageOrderList, '_class_property_singleton')
        except AttributeError:
            pass
        self.assertEqual(expected, PackageOrderList.singleton)

    def test_singleton_novalue(self):
        """Validate we can build a PackageOrderList object from empty configuration values."""
        config.override("package_orderers", None)

        # Clear @classproperty cache
        try:
            delattr(PackageOrderList, '_class_property_singleton')
        except AttributeError:
            pass

        self.assertEqual(PackageOrderList(), PackageOrderList.singleton)

    def test_pod(self):
        """Validate we can save and load a PackageOrdererList to pod representation."""
        inst = PackageOrderList((
            VersionSplitPackageOrder(Version("2.6.0")),
            PerFamilyOrder(order_dict={}, default_order=SortedOrder(descending=False))
        ))
        self._test_pod(inst)


class TestPackageOrderPublic(TestBase):
    """Additional tests for public symbols in package_order.py"""

    def test_from_pod_old_style(self):
        """Validate from_pod is still compatible with the older pod style."""
        self.assertEqual(
            VersionSplitPackageOrder(first_version=Version("1.2.3")),
            from_pod(("version_split", {"first_version": "1.2.3"}))
        )

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
