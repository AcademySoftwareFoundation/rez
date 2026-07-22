# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Test cases for package_order.py (package ordering)
"""

import json

from rez.config import config
from rez.package_order import (
    PackageOrder,
    PackageOrderList,
    from_pod,
)
from rez.packages import iter_packages
from rez.tests.util import TestBase, TempdirMixin
from rez.version import Version


def _orderer(name):
    """Resolve an orderer class lazily.

    The plugin manager may be reset by other tests (e.g. test_plugin_manager),
    which re-imports plugin modules and creates new class objects. Importing
    orderer classes at module level binds them to stale class objects. This
    helper resolves them at call time so tests always see the current class.
    """
    from rez.package_order import _find_orderer

    return _find_orderer(name)


class _BaseTestPackagesOrder(TestBase, TempdirMixin):
    """Base class for a package ordering test case"""

    def setUp(self) -> None:
        # Re-resolve orderer classes on each test run. The plugin manager
        # may be reset by other tests (e.g. test_plugin_manager), which
        # re-imports plugin modules and creates new class objects. Class
        # references bound at module import time would become stale.
        self.NullPackageOrder = _orderer("no_order")
        self.SortedOrder = _orderer("sorted")
        self.PerFamilyOrder = _orderer("per_family")
        self.VersionSplitPackageOrder = _orderer("version_split")
        self.TimestampPackageOrder = _orderer("soft_timestamp")
        super().setUp()

    @classmethod
    def setUpClass(cls) -> None:
        TempdirMixin.setUpClass()

        cls.py_packages_path = cls.data_path("packages", "py_packages")
        cls.solver_packages_path = cls.data_path("solver", "packages")

        cls.settings = dict(packages_path=[cls.solver_packages_path, cls.py_packages_path], package_filter=None)

    @classmethod
    def tearDownClass(cls) -> None:
        TempdirMixin.tearDownClass()

    def _test_reorder(self, orderer, package_name, expected_order) -> None:
        """Ensure ordered order package version as expected."""
        it = iter_packages(package_name)
        descending = sorted(it, key=lambda x: x.version, reverse=True)
        ordered = orderer.reorder(descending) or descending
        result = [str(x.version) for x in ordered]
        self.assertEqual(expected_order, result)

    def _test_pod(self, orderer) -> None:
        """Ensure an orderer integrity when serialized to pod."""
        pod = json.loads(json.dumps(orderer.to_pod()))  # roundtrip to JSON
        actual = orderer.__class__.from_pod(pod)
        self.assertEqual(orderer, actual)


class TestAbstractPackageOrder(TestBase):
    """Test case for the abstract PackageOrder class"""

    def test_to_pod(self) -> None:
        """Validate to_pod is not implemented"""
        self.assertRaises(NotImplementedError, PackageOrder().to_pod)

    def test_str(self) -> None:
        """Validate __str__ is not implemented"""
        with self.assertRaises(NotImplementedError):
            str(PackageOrder())

    def test_eq(self) -> None:
        """Validate __eq__ is not implemented"""
        with self.assertRaises(NotImplementedError):
            PackageOrder() == PackageOrder()


class TestNullPackageOrder(_BaseTestPackagesOrder):
    """Test case for the NullPackageOrder class"""

    def test_repr(self) -> None:
        """Validate we can represent a VersionSplitPackageOrder as a string."""
        self.assertEqual("NullPackageOrder({})", repr(self.NullPackageOrder()))

    def test_comparison(self) -> None:
        """Validate we can compare VersionSplitPackageOrder together."""
        inst1 = self.NullPackageOrder()
        inst2 = self.NullPackageOrder()
        self.assertTrue(inst1 == inst2)  # __eq__ positive
        self.assertFalse(inst1 == "wrong_type")  # __eq__ negative (wrong type)
        self.assertTrue(inst1 != "wrong_type")  # __ne__ positive (wrong type)
        self.assertFalse(inst1 != inst2)  # __ne__ negative

    def test_pod(self) -> None:
        """Validate we can save and load a VersionSplitPackageOrder to its pod representation."""
        self._test_pod(self.NullPackageOrder())

    def test_sha1(self) -> None:
        """Validate we can get a sha1 hash."""
        self.assertEqual("bf7c2fa4e6bd198c02adeea2c3a382cf57242051", self.NullPackageOrder().sha1)


class TestSortedOrder(_BaseTestPackagesOrder):
    """Test case for the SortedOrder class"""

    def test_reorder_ascending(self) -> None:
        """Validate we can sort packages in ascending order."""
        self._test_reorder(self.SortedOrder(descending=False), "pymum", ["1", "2", "3"])

    def test_reorder_descending(self) -> None:
        """Validate we can sort packages in descending order."""
        self._test_reorder(self.SortedOrder(descending=True), "pymum", ["3", "2", "1"])

    def test_comparison(self) -> None:
        """Validate we can compare SortedOrder together."""
        inst1 = self.SortedOrder(descending=False)
        inst2 = self.SortedOrder(descending=False)
        inst3 = self.SortedOrder(descending=True)
        self.assertTrue(inst1 == inst2)  # __eq__ positive
        self.assertFalse(inst1 == inst3)  # __eq__ negative
        self.assertTrue(inst1 != inst3)  # __ne__ positive
        self.assertFalse(inst1 != inst2)  # __ne__ negative
        self.assertFalse(inst1 == "wrong_type")  # __eq__ negative (wrong type)
        self.assertTrue(inst1 != "wrong_type")  # __eq__ negative (wrong type)

    def test_repr(self) -> None:
        """Validate we can represent a SortedOrder as a string."""
        self.assertEqual("SortedOrder(True)", repr(self.SortedOrder(descending=True)))

    def test_pod(self) -> None:
        """Validate we can save and load a SortedOrder to its pod representation."""
        self._test_pod(self.SortedOrder(descending=True))


class TestPerFamilyOrder(_BaseTestPackagesOrder):
    """Test case for the PerFamilyOrder class"""

    def test_reorder(self) -> None:
        """Test ordering."""
        expected_null_result = ["7", "6", "5"]
        expected_split_result = ["2.6.0", "2.5.2", "2.7.0", "2.6.8"]
        expected_timestamp_result = ["1.1.1", "1.1.0", "1.0.6", "1.0.5", "1.2.0", "2.0.0", "2.1.5", "2.1.0"]

        orderer = self.PerFamilyOrder(
            order_dict=dict(
                pysplit=self.NullPackageOrder(),
                python=self.VersionSplitPackageOrder(Version("2.6.0")),
                timestamped=self.TimestampPackageOrder(timestamp=3001, rank=3),
            ),
            default_order=self.SortedOrder(descending=False),
        )

        self._test_reorder(orderer, "pysplit", expected_null_result)
        self._test_reorder(orderer, "python", expected_split_result)
        self._test_reorder(orderer, "timestamped", expected_timestamp_result)
        self._test_reorder(orderer, "pymum", ["1", "2", "3"])

    def test_reorder_no_packages(self) -> None:
        """Validate ordering for a family with no packages."""
        orderer = self.PerFamilyOrder(order_dict=dict(missing_package=self.NullPackageOrder()))
        self._test_reorder(orderer, "missing_package", [])

    def test_reorder_no_default_order(self) -> None:
        """Test behavior when there's no secondary default_order."""
        fam_orderer = self.PerFamilyOrder(order_dict={})
        self._test_reorder(fam_orderer, "pymum", ["3", "2", "1"])

    def test_comparison(self) -> None:
        """Validate we can compare PerFamilyOrder."""
        inst1 = self.PerFamilyOrder(order_dict={"foo": self.NullPackageOrder()}, default_order=self.NullPackageOrder())
        inst2 = self.PerFamilyOrder(order_dict={"foo": self.NullPackageOrder()}, default_order=self.NullPackageOrder())
        inst3 = self.PerFamilyOrder(order_dict={"bar": self.NullPackageOrder()}, default_order=self.NullPackageOrder())
        inst4 = self.PerFamilyOrder(order_dict={"foo": self.NullPackageOrder()}, default_order=None)
        self.assertTrue(inst1 == inst2)  # __eq__ positive
        self.assertFalse(inst1 == inst3)  # __eq__ negative (different order dict)
        self.assertFalse(inst1 == inst4)  # __eq__ negative (different default_order)
        self.assertTrue(inst1 != inst3)  # __ne__ positive (different order dict)
        self.assertTrue(inst1 != inst4)  # __ne__ positive (different default order)
        self.assertFalse(inst1 != inst2)  # __ne__ negative

    def test_repr(self) -> None:
        """Validate we can represent a PerFamilyOrder as a string."""
        inst = self.PerFamilyOrder(order_dict={"family1": self.VersionSplitPackageOrder(Version("2.6.0"))})
        self.assertEqual("PerFamilyOrder(([('family1', '2.6.0')], 'None'))", repr(inst))

    def test_pod(self) -> None:
        """Validate we can save and load a PerFamilyOrder to its pod representation."""
        self._test_pod(
            self.PerFamilyOrder(order_dict={"foo": self.NullPackageOrder()}, default_order=self.NullPackageOrder())
        )

        # No default_order
        self._test_pod(self.PerFamilyOrder(order_dict={"foo": self.NullPackageOrder()}))


class TestVersionSplitPackageOrder(_BaseTestPackagesOrder):
    """Test case for the VersionSplitPackageOrder class"""

    def test_reordere(self) -> None:
        """Validate package ordering with a VersionSplitPackageOrder"""
        orderer = self.VersionSplitPackageOrder(Version("2.6.0"))
        expected = ["2.6.0", "2.5.2", "2.7.0", "2.6.8"]
        self._test_reorder(orderer, "python", expected)

    def test_comparison(self) -> None:
        """Validate we can compare VersionSplitPackageOrder together."""
        inst1 = self.VersionSplitPackageOrder(first_version=Version("1.2.3"))
        inst2 = self.VersionSplitPackageOrder(first_version=Version("1.2.3"))
        inst3 = self.VersionSplitPackageOrder(first_version=Version("1.2.4"))
        self.assertTrue(inst1 == inst2)  # __eq__ positive
        self.assertFalse(inst1 == inst3)  # __eq__ negative
        self.assertTrue(inst1 != inst3)  # __ne__ positive
        self.assertFalse(inst1 != inst2)  # __ne__ negative
        self.assertFalse(inst1 == "wrong_type")  # __eq__ negative (wrong type)
        self.assertTrue(inst1 != "wrong_type")  # __eq__ negative (wrong type)

    def test_repr(self) -> None:
        """Validate we can represent a VersionSplitPackageOrder as a string."""
        inst = self.VersionSplitPackageOrder(first_version=Version("1,2,3"))
        self.assertEqual("VersionSplitPackageOrder(1,2,3)", repr(inst))

    def test_pod(self) -> None:
        """Validate we can save and load a VersionSplitPackageOrder to its pod representation."""
        self._test_pod(self.VersionSplitPackageOrder(first_version=Version("1.2.3")))


class TestTimestampPackageOrder(_BaseTestPackagesOrder):
    """Test cases for the TimestampPackageOrder class"""

    def test_reorder_no_rank(self) -> None:
        """Validate reordering with a rank of 0."""
        orderer = self.TimestampPackageOrder(timestamp=3001)
        expected = ["1.1.0", "1.0.6", "1.0.5", "1.1.1", "1.2.0", "2.0.0", "2.1.0", "2.1.5"]
        self._test_reorder(orderer, "timestamped", expected)

    def test_reorder_rank_3(self) -> None:
        """Validate reordering with a rank of 3."""
        # after v1.1.0 and before v1.1.1
        orderer1 = self.TimestampPackageOrder(timestamp=3001, rank=3)
        expected1 = ["1.1.1", "1.1.0", "1.0.6", "1.0.5", "1.2.0", "2.0.0", "2.1.5", "2.1.0"]
        self._test_reorder(orderer1, "timestamped", expected1)

        # after v2.1.0 and before v2.1.5
        orderer2 = self.TimestampPackageOrder(timestamp=7001, rank=3)
        expected2 = ["2.1.5", "2.1.0", "2.0.0", "1.2.0", "1.1.1", "1.1.0", "1.0.6", "1.0.5"]
        self._test_reorder(orderer2, "timestamped", expected2)

    def test_reorder_rank_2(self) -> None:
        """Add coverage for a corner case where there's only one candidate without the rank."""
        orderer = self.TimestampPackageOrder(timestamp=4001, rank=3)  # 1.1.1
        expected = ["1.1.1", "1.1.0", "1.0.6", "1.0.5", "1.2.0", "2.0.0", "2.1.5", "2.1.0"]
        self._test_reorder(orderer, "timestamped", expected)

    def test_reorder_packages_without_timestamps(self) -> None:
        """Validate reordering of packages that have no timestamp data."""
        orderer = self.TimestampPackageOrder(timestamp=3001)
        self._test_reorder(orderer, "pymum", ["3", "2", "1"])

    def test_reorder_all_packages_before_timestamp(self) -> None:
        """Test behavior when all packages are before the timestamp."""
        timestamp_orderer = self.TimestampPackageOrder(timestamp=9999999999, rank=3)
        expected = ["2.1.5", "2.1.0", "2.0.0", "1.2.0", "1.1.1", "1.1.0", "1.0.6", "1.0.5"]
        self._test_reorder(timestamp_orderer, "timestamped", expected)

    def test_reorder_all_packages_after_timestamp(self) -> None:
        """Test behavior when all packages are after the timestamp."""
        timestamp_orderer = self.TimestampPackageOrder(timestamp=0, rank=3)
        expected = ["1.0.6", "1.0.5", "1.1.1", "1.1.0", "1.2.0", "2.0.0", "2.1.5", "2.1.0"]
        self._test_reorder(timestamp_orderer, "timestamped", expected)

    def test_comparison(self) -> None:
        """Validate we can compare TimestampPackageOrder."""
        inst1 = self.TimestampPackageOrder(timestamp=1, rank=1)
        inst2 = self.TimestampPackageOrder(timestamp=1, rank=1)
        inst3 = self.TimestampPackageOrder(timestamp=2, rank=1)
        inst4 = self.TimestampPackageOrder(timestamp=2, rank=2)
        self.assertTrue(inst1 == inst2)  # __eq__ positive
        self.assertFalse(inst1 == inst3)  # __eq__ negative (different timestamp)
        self.assertFalse(inst1 == inst4)  # __eq__ negative (different rank)
        self.assertTrue(inst1 != inst3)  # __ne__ positive (different timestamp)
        self.assertTrue(inst1 != inst4)  # __ne__ positive (different rank)
        self.assertFalse(inst1 != inst2)  # __ne__ negative

    def test_repr(self) -> None:
        """Validate we can represent a TimestampPackageOrder as a string."""
        inst = self.TimestampPackageOrder(timestamp=1, rank=2)
        self.assertEqual(repr(inst), "TimestampPackageOrder((1, 2))")

    def test_pod(self) -> None:
        """Validate we can save and load a TimestampPackageOrder to pod representation."""
        self._test_pod(self.TimestampPackageOrder(timestamp=3001, rank=3))


class TestPackageOrdererList(_BaseTestPackagesOrder):
    """Test cases for the PackageOrderList class."""

    def test_singleton(self) -> None:
        """Validate we can build a PackageOrderList object from configuration values."""
        config.override(
            "package_orderers",
            [
                {
                    "type": "per_family",
                    "orderers": [{"packages": ["python"], "type": "version_split", "first_version": "2.9.9"}],
                }
            ],
        )
        expected = PackageOrderList()
        expected.append(self.PerFamilyOrder(order_dict={"python": self.VersionSplitPackageOrder(Version("2.9.9"))}))

        # Clear @classproperty cache
        try:
            delattr(PackageOrderList, "_class_property_singleton")
        except AttributeError:
            pass
        self.assertEqual(expected, PackageOrderList.singleton)

    def test_singleton_novalue(self) -> None:
        """Validate we can build a PackageOrderList object from empty configuration values."""
        config.override("package_orderers", None)

        # Clear @classproperty cache
        try:
            delattr(PackageOrderList, "_class_property_singleton")
        except AttributeError:
            pass

        self.assertEqual(PackageOrderList(), PackageOrderList.singleton)

    def test_pod(self) -> None:
        """Validate we can save and load a PackageOrdererList to pod representation."""
        inst = PackageOrderList(
            (
                self.VersionSplitPackageOrder(Version("2.6.0")),
                self.PerFamilyOrder(order_dict={}, default_order=self.SortedOrder(descending=False)),
            )
        )
        self._test_pod(inst)

    def test_from_pod_module_function_round_trip(self):
        """Verify the module-level from_pod function resolves orderer types."""
        from rez.package_order import from_pod as module_from_pod

        # sorted
        orderer = module_from_pod({"type": "sorted", "descending": True})
        self.assertIsInstance(orderer, self.SortedOrder)
        self.assertTrue(orderer.descending)

        # no_order
        orderer = module_from_pod({"type": "no_order"})
        self.assertIsInstance(orderer, self.NullPackageOrder)

        # version_split
        orderer = module_from_pod({"type": "version_split", "first_version": "1.2.3"})
        self.assertIsInstance(orderer, self.VersionSplitPackageOrder)

    def test_isinstance_against_imported_classes(self):
        """Verify isinstance works for orderer classes imported from package_order."""
        self.assertIsInstance(self.SortedOrder(descending=True), self.SortedOrder)
        self.assertIsInstance(self.NullPackageOrder(), self.NullPackageOrder)
        self.assertIsInstance(
            self.VersionSplitPackageOrder(first_version=Version("1.0")), self.VersionSplitPackageOrder
        )
        self.assertIsInstance(self.TimestampPackageOrder(timestamp=1000), self.TimestampPackageOrder)
        # Cross-type checks
        self.assertNotIsInstance(self.SortedOrder(descending=True), self.NullPackageOrder)

    def test_get_orderer_default_fallback(self):
        """Verify get_orderer falls back to SortedOrder(descending=True)."""
        from rez.package_order import get_orderer

        config.override("package_orderers", None)
        # Clear singleton cache
        try:
            delattr(PackageOrderList, "_class_property_singleton")
        except AttributeError:
            pass

        orderer = get_orderer("nonexistent_package")
        self.assertIsInstance(orderer, self.SortedOrder)
        self.assertTrue(orderer.descending)

    def test_plugin_system_loads_builtin_orderers(self) -> None:
        """Verify all five built-in orderers are loadable via the plugin system."""
        from rez.plugin_managers import plugin_manager

        expected = {
            "no_order": "NullPackageOrder",
            "sorted": "SortedOrder",
            "per_family": "PerFamilyOrder",
            "version_split": "VersionSplitPackageOrder",
            "soft_timestamp": "TimestampPackageOrder",
        }

        for plugin_name, class_name in expected.items():
            cls = plugin_manager.get_plugin_class("package_order", plugin_name)
            self.assertEqual(cls.__name__, class_name)

    def test_pod_round_trip_through_plugin_system(self) -> None:
        """Verify to_pod/from_pod round-trip works through the plugin system."""
        from rez.package_order import to_pod, from_pod

        orderers = [
            self.SortedOrder(descending=True),
            self.NullPackageOrder(),
            self.VersionSplitPackageOrder(first_version=Version("1.2.3")),
            self.TimestampPackageOrder(timestamp=3001, rank=3),
            self.PerFamilyOrder(order_dict={"foo": self.NullPackageOrder()}, default_order=self.NullPackageOrder()),
        ]

        for original in orderers:
            pod = to_pod(original)
            restored = from_pod(pod)
            self.assertEqual(original, restored)
            self.assertIs(type(original), type(restored))

    def test_legacy_register_orderer_fallback(self) -> None:
        """Verify _find_orderer falls back to _orderers for legacy-registered orderers."""
        from rez.package_order import PackageOrder, register_orderer, _find_orderer, _orderers

        class TestLegacyOrderer(PackageOrder):
            name = "test_legacy_fallback"

            def sort_key_implementation(self, package_name, version):
                return 0

            def __str__(self):
                return "test"

            def to_pod(self):
                return {}

            @classmethod
            def from_pod(cls, data):
                return cls()

        try:
            register_orderer(TestLegacyOrderer)
            found = _find_orderer("test_legacy_fallback")
            self.assertIs(found, TestLegacyOrderer)
        finally:
            _orderers.pop("test_legacy_fallback", None)

    def test_rez_package_orderers_json_env_var(self) -> None:
        """Verify REZ_PACKAGE_ORDERERS_JSON configures orderers at runtime.

        The test framework uses a locked config that blocks env-var reads, so
        we simulate the env-var path by parsing the JSON and using
        config.override() — this is exactly what the _JSON path does.
        """
        import json

        config_json = json.dumps(
            [
                {
                    "type": "per_family",
                    "orderers": [{"packages": ["python"], "type": "version_split", "first_version": "2.9.9"}],
                }
            ]
        )

        old_overrides = config.overrides.get("package_orderers")
        try:
            config.override("package_orderers", json.loads(config_json))
            PackageOrderList.clear_singleton_cache()

            orderers = PackageOrderList.singleton
            self.assertEqual(len(orderers), 1)
            self.assertEqual(orderers[0].name, "per_family")
        finally:
            if old_overrides is not None:
                config.override("package_orderers", old_overrides)
            else:
                config.override("package_orderers", None)
            PackageOrderList.clear_singleton_cache()

    def test_cache_invalidation_for_env_var_changes(self) -> None:
        """Verify cache invalidation allows config changes to take effect."""
        import json

        old_overrides = config.overrides.get("package_orderers")
        try:
            # First config: empty orderers
            config.override("package_orderers", None)
            PackageOrderList.clear_singleton_cache()
            orderers1 = PackageOrderList.singleton
            self.assertEqual(len(orderers1), 0)

            # Second config: one orderer
            config.override("package_orderers", json.loads('[{"type": "sorted", "descending": false}]'))
            PackageOrderList.clear_singleton_cache()
            orderers2 = PackageOrderList.singleton
            self.assertEqual(len(orderers2), 1)
            self.assertEqual(orderers2[0].name, "sorted")
            self.assertFalse(orderers2[0].descending)
        finally:
            if old_overrides is not None:
                config.override("package_orderers", old_overrides)
            else:
                config.override("package_orderers", None)
            PackageOrderList.clear_singleton_cache()

    def test_kwarg_orderer_configurable_via_env_var(self) -> None:
        """Verify an orderer with constructor kwargs can be configured at runtime.

        This validates the pattern used by PRs #1706 (PEP440PackageOrder with
        'prerelease' kwarg) and #1709 (CustomPackageOrder with 'packages' kwarg)
        without requiring those PRs to be merged.

        The test framework uses a locked config that blocks env-var reads, so
        we simulate the _JSON path by parsing JSON and using config.override().
        """
        import json
        from rez.package_order import PackageOrder, register_orderer, _orderers

        class TestKwargOrderer(PackageOrder):
            name = "test_kwarg"

            def __init__(self, mode="default", packages=None):
                super().__init__(packages)
                self.mode = mode

            def sort_key_implementation(self, package_name, version):
                return 0

            def __str__(self):
                return str(self.mode)

            def __eq__(self, other):
                return type(self) is type(other) and self.mode == other.mode

            def to_pod(self):
                return {"mode": self.mode, "packages": self.packages}

            @classmethod
            def from_pod(cls, data):
                return cls(
                    mode=data.get("mode", "default"),
                    packages=data.get("packages"),
                )

        old_overrides = config.overrides.get("package_orderers")
        try:
            register_orderer(TestKwargOrderer)

            config.override(
                "package_orderers", json.loads('[{"type": "test_kwarg", "mode": "production", "packages": ["foo"]}]')
            )
            PackageOrderList.clear_singleton_cache()

            orderers = PackageOrderList.singleton
            self.assertEqual(len(orderers), 1)
            self.assertEqual(orderers[0].name, "test_kwarg")
            self.assertEqual(orderers[0].mode, "production")
            self.assertEqual(orderers[0].packages, ["foo"])
        finally:
            _orderers.pop("test_kwarg", None)
            if old_overrides is not None:
                config.override("package_orderers", old_overrides)
            else:
                config.override("package_orderers", None)
            PackageOrderList.clear_singleton_cache()


class TestPackageOrderPublic(TestBase):
    """Additional tests for public symbols in package_order.py"""

    def setUp(self) -> None:
        self.VersionSplitPackageOrder = _orderer("version_split")
        super().setUp()

    def test_from_pod_old_style(self) -> None:
        """Validate from_pod is still compatible with the older pod style."""
        self.assertEqual(
            self.VersionSplitPackageOrder(first_version=Version("1.2.3")),
            from_pod(("version_split", {"first_version": "1.2.3"})),
        )
