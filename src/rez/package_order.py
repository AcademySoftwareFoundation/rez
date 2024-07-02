# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


from inspect import isclass
from hashlib import sha1
from typing import Dict, Iterable, List, Optional, Union

from rez.config import config
from rez.exceptions import RezPluginError
from rez.utils.data_utils import cached_class_property
from rez.version import Version, VersionRange
from rez.version._version import _Comparable, _LowerBound, _UpperBound, _Bound

ALL_PACKAGES = "*"


class FallbackComparable(_Comparable):
    """First tries to compare objects using the main_comparable, but if that
    fails, compares using the fallback_comparable object.
    """

    def __init__(self, main_comparable, fallback_comparable):
        self.main_comparable = main_comparable
        self.fallback_comparable = fallback_comparable

    def __eq__(self, other):
        try:
            return self.main_comparable == other.main_comparable
        except Exception:
            return self.fallback_comparable == other.fallback_comparable

    def __lt__(self, other):
        try:
            return self.main_comparable < other.main_comparable
        except Exception:
            return self.fallback_comparable < other.fallback_comparable

    def __repr__(self):
        return '%s(%r, %r)' % (type(self).__name__, self.main_comparable, self.fallback_comparable)


class PackageOrder(object):
    """Package reorderer base class."""

    #: Orderer name
    name = None

    def __init__(self, packages: Optional[Iterable[str]] = None):
        """
        Args:
            packages: If not provided, PackageOrder applies to all packages.
        """
        self.packages = packages

    @property
    def packages(self) -> List[str]:
        """Returns an iterable over the list of package family names that this
        order applies to

        Returns:
            (Iterable[str]) Package families that this orderer is used for
        """
        return self._packages

    @packages.setter
    def packages(self, packages: Union[str, Iterable[str]]):
        if packages is None:
            # Apply to all packages
            self._packages = [ALL_PACKAGES]
        elif isinstance(packages, str):
            self._packages = [packages]
        else:
            self._packages = sorted(packages)

    def reorder(self, iterable, key=None):
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
        return sorted(iterable,
                      key=lambda x: self.sort_key(package_name, key(x).version),
                      reverse=True)

    @staticmethod
    def _get_package_name_from_iterable(iterable, key=None):
        """Utility method for getting a package from an iterable"""
        try:
            item = next(iter(iterable))
        except (TypeError, StopIteration):
            return None

        key = key or (lambda x: x)
        return key(item).name

    def sort_key(self, package_name, version_like):
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
            return (self.sort_key(package_name, version_like.lower),
                    self.sort_key(package_name, version_like.upper))
        if isinstance(version_like, _LowerBound):
            inclusion_key = -2 if version_like.inclusive else -1
            return self.sort_key(package_name, version_like.version), inclusion_key
        if isinstance(version_like, _UpperBound):
            inclusion_key = 2 if version_like.inclusive else 1
            return self.sort_key(package_name, version_like.version), inclusion_key
        if isinstance(version_like, Version):
            # finally, the bit that we actually use the sort_key_implementation for.
            return FallbackComparable(
                self.sort_key_implementation(package_name, version_like), version_like)
        if version_like is None:
            # As no version range is provided for this package,
            # Python's sort preserves the order of equal elements.
            # Thus, to maintain the original order,
            # we return the same object for all None values.
            return 0
        raise TypeError(version_like)

    def sort_key_implementation(self, package_name, version):
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

    def to_pod(self):
        raise NotImplementedError

    @classmethod
    def from_pod(cls, data):
        raise NotImplementedError

    @property
    def sha1(self):
        return sha1(repr(self).encode('utf-8')).hexdigest()

    def __str__(self):
        raise NotImplementedError

    def __eq__(self, other):
        return type(self) is type(other) and str(self) == str(other)

    def __ne__(self, other):
        return not self == other

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, str(self))


class PackageOrderList(list):
    """A list of package orderer.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.by_package: Dict[str, PackageOrder] = {}
        self.dirty = True

    def to_pod(self):
        return [to_pod(f) for f in self]

    @classmethod
    def from_pod(cls, data):
        flist = PackageOrderList()
        for dict_ in data:
            f = from_pod(dict_)
            flist.append(f)
        return flist

    @cached_class_property
    def singleton(cls):
        """Filter list as configured by rezconfig.package_filter."""
        return cls.from_pod(config.package_orderers)

    @staticmethod
    def _to_orderer(orderer: Union[dict, PackageOrder]) -> PackageOrder:
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
        return super().clear()

    def insert(self, *args, **kwargs):
        self.dirty = True
        return super().insert(*args, **kwargs)

    def get(self, key: str, default: Optional[PackageOrder] = None) -> PackageOrder:
        """
        Get an orderer that sorts a package by name.
        """
        if self.dirty:
            self.refresh()
            self.dirty = False
        result = self.by_package.get(key, default)
        return result


def to_pod(orderer):
    data = {"type": orderer.name}
    data.update(orderer.to_pod())
    return data


def from_pod(data):
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


def get_orderer(package_name, orderers=None):
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


_orderers = {}


def register_orderer(cls):
    """Register an orderer.

    Kept for backwards compatability.  New orderers should be a plugin.

    Args:
        cls (type[PackageOrder]): Package order class to register.

    returns:
        bool: True if successfully registered, else False.
    """
    if isclass(cls) and issubclass(cls, PackageOrder) and \
            hasattr(cls, "name") and cls.name:
        _orderers[cls.name] = cls
        return True
    else:
        return False


def _find_orderer(name):
    from rez.plugin_managers import plugin_manager

    try:
        return plugin_manager.get_plugin_class('package_order', name)
    except RezPluginError:
        # Fallback to old "register_orderer" method
        if name not in _orderers:
            raise
        return _orderers[name]


# For backwards compatibility create "construction functions" to replace
# existing classes in case a user is importing the class.
def NullPackageOrder(*args, **kwargs):
    return _find_orderer('no_order')(*args, **kwargs)


def PerFamilyOrder(*args, **kwargs):
    return _find_orderer('per_family')(*args, **kwargs)


def SortedOrder(*args, **kwargs):
    return _find_orderer('sorted')(*args, **kwargs)


def TimestampPackageOrder(*args, **kwargs):
    return _find_orderer('soft_timestamp')(*args, **kwargs)


def VersionSplitPackageOrder(*args, **kwargs):
    return _find_orderer("version_split")(*args, **kwargs)
