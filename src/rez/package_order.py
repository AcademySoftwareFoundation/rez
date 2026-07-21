# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


from __future__ import annotations

from inspect import isclass
from hashlib import sha1
from typing import Any, Callable, Iterable, List, TYPE_CHECKING

from rez.config import config
from rez.exceptions import RezPluginError
from rez.utils.data_utils import cached_class_property
from rez.version import Version, VersionRange
from rez.version._version import _Comparable, _LowerBound, _UpperBound, _Bound
from rez.packages import Package
from rez.utils.typing import SupportsLessThan

ALL_PACKAGES = "*"


class FallbackComparable(_Comparable):
    """First tries to compare objects using the main_comparable, but if that
    fails, compares using the fallback_comparable object.
    """

    def __init__(self, main_comparable: SupportsLessThan, fallback_comparable: SupportsLessThan) -> None:
        self.main_comparable = main_comparable
        self.fallback_comparable = fallback_comparable

    def __eq__(self, other: object) -> bool:
        try:
            return self.main_comparable == other.main_comparable
        except Exception:
            return self.fallback_comparable == other.fallback_comparable

    def __lt__(self, other: object) -> bool:
        try:
            return self.main_comparable < other.main_comparable
        except Exception:
            return self.fallback_comparable < other.fallback_comparable

    def __repr__(self) -> str:
        return "%s(%r, %r)" % (type(self).__name__, self.main_comparable, self.fallback_comparable)


class PackageOrder(object):
    """Package reorderer base class."""

    #: Orderer name
    name = None

    def __init__(self, packages: list[str] | None = None) -> None:
        """
        Args:
            packages: If not provided, PackageOrder applies to all packages.
        """
        # TYPING: odd behavior where mypy disregards the property setter
        self.packages = packages  # type: ignore[assignment]

    @property
    def packages(self) -> list[str]:
        """Returns an iterable over the list of package family names that this
        order applies to

        Returns:
            (Iterable[str]) Package families that this orderer is used for
        """
        return self._packages

    @packages.setter
    def packages(self, packages: str | Iterable[str] | None) -> None:
        if packages is None:
            # Apply to all packages
            self._packages = [ALL_PACKAGES]
        elif isinstance(packages, str):
            self._packages = [packages]
        else:
            self._packages = sorted(packages)

    def reorder(self, iterable: Iterable[Package], key: Callable[[Any], Package] | None = None) -> list[Package] | None:
        """Put packages into some order for consumption.

        You can safely assume that the packages referred to by `iterable` are
        all versions of the same package family.

        Note:
            Returning None, and an unchanged `iterable` list, are not the same
            thing. Returning None may cause rez to pass the package list to the
            next orderer; whereas a package list that has been reordered (even
            if the unchanged list is returned) is not passed onto another orderer.

        Args:
            iterable: Iterable list of packages, or objects that contain packages.
            key (typing.Callable[typing.Any, Package]): Callable, where key(iterable)
                gives a :class:`~rez.packages.Package`. If None, iterable is assumed
                to be a list of :class:`~rez.packages.Package` objects.

        Returns:
            list: Reordered ``iterable``
        """
        key = key or (lambda x: x)
        package_name = self._get_package_name_from_iterable(iterable, key=key)
        return sorted(iterable, key=lambda x: self.sort_key(package_name, key(x).version), reverse=True)

    @staticmethod
    def _get_package_name_from_iterable(
        iterable: Iterable[Package], key: Callable[[Any], Package] | None = None
    ) -> str | None:
        """Utility method for getting a package from an iterable"""
        try:
            item = next(iter(iterable))
        except (TypeError, StopIteration):
            return None

        key = key or (lambda x: x)
        return key(item).name

    def sort_key(
        self, package_name: str, version_like: Version | _LowerBound | _UpperBound | _Bound | VersionRange | None
    ) -> SupportsLessThan:
        """Returns a sort key usable for sorting packages within the same family

        Args:
            package_name: (str) The family name of the package we are sorting
            version_like: (Version|_LowerBound|_UpperBound|_Bound|VersionRange|None)
                The version-like object to be used as a basis for generating a sort key.
                Note that 'None' is also a supported value, which maintains the default sorting order.

        Returns:
            Sortable object
                The returned object must be sortable, which means that it must implement __lt__.
                The specific return type is not important.
        """
        if isinstance(version_like, VersionRange):
            return tuple(self.sort_key(package_name, bound) for bound in version_like.bounds)
        if isinstance(version_like, _Bound):
            return (self.sort_key(package_name, version_like.lower), self.sort_key(package_name, version_like.upper))
        if isinstance(version_like, _LowerBound):
            inclusion_key = -2 if version_like.inclusive else -1
            return self.sort_key(package_name, version_like.version), inclusion_key
        if isinstance(version_like, _UpperBound):
            inclusion_key = 2 if version_like.inclusive else 1
            return self.sort_key(package_name, version_like.version), inclusion_key
        if isinstance(version_like, Version):
            # finally, the bit that we actually use the sort_key_implementation for.
            return FallbackComparable(self.sort_key_implementation(package_name, version_like), version_like)
        if version_like is None:
            # As no version range is provided for this package,
            # Python's sort preserves the order of equal elements.
            # Thus, to maintain the original order,
            # we return the same object for all None values.
            return 0
        raise TypeError(version_like)

    def sort_key_implementation(self, package_name: str, version: Version) -> SupportsLessThan:
        """Returns a sort key usable for sorting these packages within the
        same family
        Args:
            package_name: (str) The family name of the package we are sorting
            version: (Version) the version object you wish to generate a key for

        Returns:
            Sortable object
                The returned object must be sortable, which means that it must implement __lt__.
                The specific return type is not important.
        """
        raise NotImplementedError

    def to_pod(self) -> dict[str, Any]:
        raise NotImplementedError

    @classmethod
    def from_pod(cls, data: dict[str, Any]) -> PackageOrder:
        raise NotImplementedError

    @property
    def sha1(self) -> str:
        return sha1(repr(self).encode("utf-8")).hexdigest()

    def __str__(self) -> str:
        raise NotImplementedError

    def __eq__(self, other):
        return type(self) is type(other) and str(self) == str(other)

    def __ne__(self, other) -> bool:
        return not self == other

    def __repr__(self) -> str:
        return "%s(%s)" % (self.__class__.__name__, str(self))


# Legacy orderer registry. Used as fallback by _find_orderer when an orderer
# is not found in the plugin system.
_orderers = {}


def _find_orderer(name):
    """Find an orderer class by name.

    Checks the plugin system first, then falls back to the _orderers
    registry for orderers registered via register_orderer().
    """
    from rez.plugin_managers import plugin_manager

    try:
        return plugin_manager.get_plugin_class("package_order", name)
    except RezPluginError:
        # Fallback to register_orderer() API-based registration
        if name not in _orderers:
            raise
        return _orderers[name]


# Backward-compat aliases. These are resolved lazily via __getattr__ below to
# avoid a circular import: the plugin modules in rezplugins/package_order/
# import from this module, so we cannot call _find_orderer (which loads the
# plugin system) at module load time.
#
# New code should import from the plugin system directly.
_LEGACY_ORDERER_NAMES = {
    "NullPackageOrder": "no_order",
    "PerFamilyOrder": "per_family",
    "SortedOrder": "sorted",
    "TimestampPackageOrder": "soft_timestamp",
    "VersionSplitPackageOrder": "version_split",
}


def __getattr__(name):
    """Provide backward-compat class aliases for orderers now in the plugin system.

    Resolved lazily to avoid circular imports at module load time.
    """
    if name in _LEGACY_ORDERER_NAMES:
        return _find_orderer(_LEGACY_ORDERER_NAMES[name])
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


class PackageOrderList(List[PackageOrder]):
    """A list of package orderer."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.by_package: dict[str, PackageOrder] = {}
        self.dirty = True

    def to_pod(self) -> list[dict[str, Any]]:
        return [to_pod(f) for f in self]

    @classmethod
    def from_pod(cls, data: list[dict[str, Any]]) -> PackageOrderList:
        flist = PackageOrderList()
        for dict_ in data:
            f = from_pod(dict_)
            flist.append(f)
        return flist

    @cached_class_property
    def singleton(cls) -> PackageOrderList:
        """Filter list as configured by rezconfig.package_filter."""
        return cls.from_pod(config.package_orderers)

    @classmethod
    def clear_singleton_cache(cls) -> None:
        """Clear the cached singleton so the next access re-reads config.

        Use this when runtime configuration (e.g. REZ_PACKAGE_ORDERERS_JSON)
        has changed and you want the new config to take effect. Note that
        the config-level cache must also be cleared via
        ``config._uncache("package_orderers")``.
        """
        name = "_class_property_singleton"
        if hasattr(cls, name):
            delattr(cls, name)

    @staticmethod
    def _to_orderer(orderer: dict | PackageOrder) -> PackageOrder:
        if isinstance(orderer, dict):
            orderer = from_pod(orderer)
        return orderer

    def refresh(self) -> None:
        """Update the internal order-by-package mapping"""
        self.by_package = {}
        for orderer in self:
            orderer = self._to_orderer(orderer)
            for package in orderer.packages:
                # We allow duplicates (so we can have hierarchical configs,
                # which can override each other) - earlier orderers win
                if package in self.by_package:
                    continue
                self.by_package[package] = orderer

    if not TYPE_CHECKING:
        # Since this class inherits from list it's easier to rely on the type hints coming from
        # that base class than to redefine them here, so we hide them by placing them behind
        # not TYPE_CHECKING.

        def append(self, *args, **kwargs):
            self.dirty = True
            return super().append(*args, **kwargs)

        def extend(self, *args, **kwargs):
            self.dirty = True
            return super().extend(*args, **kwargs)

        def pop(self, *args, **kwargs):
            self.dirty = True
            return super().pop(*args, **kwargs)

        def remove(self, *args, **kwargs):
            self.dirty = True
            return super().remove(*args, **kwargs)

        def clear(self, *args, **kwargs):
            self.dirty = True
            return super().clear(*args, **kwargs)

        def insert(self, *args, **kwargs):
            self.dirty = True
            return super().insert(*args, **kwargs)

    def get(self, key: str, default: PackageOrder | None = None) -> PackageOrder | None:
        """
        Get an orderer that sorts a package by name.
        """
        if self.dirty:
            self.refresh()
            self.dirty = False
        result = self.by_package.get(key, default)
        return result


def to_pod(orderer: PackageOrder) -> dict:
    data = {"type": orderer.name}
    data.update(orderer.to_pod())
    return data


def from_pod(data: dict[str, Any]) -> PackageOrder:
    if isinstance(data, dict):
        cls_name = data["type"]
        data = data.copy()
        data.pop("type")

        cls = _find_orderer(cls_name)
        return cls.from_pod(data)
    else:
        # old-style, kept for backwards compatibility
        cls_name, data_ = data
        cls = _find_orderer(cls_name)
        return cls.from_pod(data_)


def get_orderer(package_name: str, orderers: PackageOrderList | dict[str, PackageOrder] | None = None) -> PackageOrder:
    if orderers is None:
        orderers = PackageOrderList.singleton
    orderer = orderers.get(package_name)
    if orderer is None:
        orderer = orderers.get(ALL_PACKAGES)
    if orderer is None:
        # default ordering is version descending
        sorted_order = _find_orderer("sorted")
        orderer = sorted_order(descending=True)
    return orderer


# Orderers registered at runtime via register_orderer(). This is the API-based
# registration pathway, used as fallback by _find_orderer when an orderer is
# not found in the plugin system.
_orderers = {}


# Register an orderer for runtime/API-based use. Orderers registered here are
# found by _find_orderer as a fallback when the plugin system does not have
# a matching orderer. For filesystem-based, facility-wide orderers, prefer
# creating a plugin in rezplugins/package_order/ instead.
def register_orderer(cls: type[PackageOrder]) -> bool:
    """Register an orderer.

    This is the API-based registration pathway, useful for dynamic or
    programmatic orderer registration. For persistent, facility-wide
    orderers, prefer the plugin system (rezplugins/package_order/).

    Args:
        cls (type[PackageOrder]): Package order class to register.

    returns:
        bool: True if successfully registered, else False.
    """
    if isclass(cls) and issubclass(cls, PackageOrder) and hasattr(cls, "name") and cls.name:
        _orderers[cls.name] = cls
        return True
    else:
        return False
