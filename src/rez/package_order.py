# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


from inspect import isclass
from hashlib import sha1
from typing import Dict, Iterable, List, Optional, Tuple, Union

from rez.config import config
from rez.exceptions import ConfigurationError
from rez.utils.data_utils import cached_class_property
from rez.version import Version, VersionRange
from rez.version._version import _Comparable, _ReversedComparable, _LowerBound, _UpperBound, _Bound
from rez.packages import iter_packages

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
            version_like: (Version|_LowerBound|_UpperBound|_Bound|VersionRange)
                the version-like object you wish to generate a key for

        Returns:
            Sortable object
                The returned object must be sortable, which means that it must implement __lt__.
                The specific return type is not important.
        """
        if isinstance(version_like, VersionRange):
            return tuple(self.sort_key(package_name, bound) for bound in version_like.bounds)
        elif isinstance(version_like, _Bound):
            return (self.sort_key(package_name, version_like.lower),
                    self.sort_key(package_name, version_like.upper))
        elif isinstance(version_like, _LowerBound):
            inclusion_key = -2 if version_like.inclusive else -1
            return self.sort_key(package_name, version_like.version), inclusion_key
        elif isinstance(version_like, _UpperBound):
            inclusion_key = 2 if version_like.inclusive else 1
            return self.sort_key(package_name, version_like.version), inclusion_key
        elif isinstance(version_like, Version):
            # finally, the bit that we actually use the sort_key_implementation for.
            return FallbackComparable(
                self.sort_key_implementation(package_name, version_like), version_like)
        else:
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
        return type(self) == type(other) and str(self) == str(other)

    def __ne__(self, other):
        return not self == other

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, str(self))


class NullPackageOrder(PackageOrder):
    """An orderer that does not change the order - a no op.

    This orderer is useful in cases where you want to apply some default orderer
    to a set of packages, but may want to explicitly NOT reorder a particular
    package. You would use a :class:`NullPackageOrder` in a :class:`PerFamilyOrder` to do this.
    """
    name = "no_order"

    def sort_key_implementation(self, package_name, version):
        # python's sort will preserve the order of items that compare equal, so
        # to not change anything, we just return the same object for all...
        return 0

    def __str__(self):
        return "{}"

    def __eq__(self, other):
        return type(self) == type(other)

    def to_pod(self):
        """
        Example (in yaml):

        .. code-block:: yaml

           type: no_order
           packages: ["foo"]
        """
        return {
            "packages": self.packages,
        }

    @classmethod
    def from_pod(cls, data):
        return cls(packages=data.get("packages"))


class SortedOrder(PackageOrder):
    """An orderer that sorts based on :attr:`Package.version <rez.packages.Package.version>`.
    """
    name = "sorted"

    def __init__(self, descending, packages=None):
        super().__init__(packages)
        self.descending = descending

    def sort_key_implementation(self, package_name, version):
        # Note that the name "descending" can be slightly confusing - it
        # indicates that the final ordering this Order gives should be
        # version descending (ie, the default) - however, the sort_key itself
        # returns its results in "normal" ascending order (because it needs to
        # be used "alongside" normally-sorted objects like versions).
        # when the key is passed to sort(), though, it is always invoked with
        # reverse=True...
        if self.descending:
            return version
        else:
            return _ReversedComparable(version)

    def __str__(self):
        return str(self.descending)

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and self.descending == other.descending
        )

    def to_pod(self):
        """
        Example (in yaml):

        .. code-block:: yaml

           type: sorted
           descending: true
           packages: ["foo"]
        """
        return {
            "descending": self.descending,
            "packages": self.packages,
        }

    @classmethod
    def from_pod(cls, data):
        return cls(
            data["descending"],
            packages=data.get("packages"),
        )


class PerFamilyOrder(PackageOrder):
    """An orderer that applies different orderers to different package families.
    """
    name = "per_family"

    def __init__(self, order_dict, default_order=None):
        """Create a reorderer.

        Args:
            order_dict (dict[str, PackageOrder]): Orderers to apply to
                each package family.
            default_order (PackageOrder): Orderer to apply to any packages
                not specified in ``order_dict``.
        """
        super().__init__(list(order_dict))
        self.order_dict = order_dict.copy()
        self.default_order = default_order

    def reorder(self, iterable, key=None):
        package_name = self._get_package_name_from_iterable(iterable, key)
        if package_name is None:
            return None

        orderer = self.order_dict.get(package_name)
        if orderer is None:
            orderer = self.default_order
        if orderer is None:
            return None

        return orderer.reorder(iterable, key)

    def sort_key_implementation(self, package_name, version):
        orderer = self.order_dict.get(package_name)
        if orderer is None:
            if self.default_order is None:
                # shouldn't get here, because applies_to should protect us...
                raise RuntimeError(
                    "package family orderer %r does not apply to package family %r",
                    (self, package_name))

            orderer = self.default_order

        return orderer.sort_key_implementation(package_name, version)

    def __str__(self):
        items = sorted((x[0], str(x[1])) for x in self.order_dict.items())
        return str((items, str(self.default_order)))

    def __eq__(self, other):
        return (
            type(other) == type(self)
            and self.order_dict == other.order_dict
            and self.default_order == other.default_order
        )

    def to_pod(self):
        """
        Example (in yaml):

        .. code-block:: yaml

           type: per_family
           orderers:
           - packages: ['foo', 'bah']
             type: version_split
             first_version: '4.0.5'
           - packages: ['python']
             type: sorted
             descending: false
           default_order:
             type: sorted
             descending: true
        """
        orderers = {}
        packages = {}

        # group package fams by orderer they use
        for fam, orderer in self.order_dict.items():
            k = id(orderer)
            orderers[k] = orderer
            packages.setdefault(k, set()).add(fam)

        orderlist = []
        for k, fams in packages.items():
            orderer = orderers[k]
            data = to_pod(orderer)
            data["packages"] = sorted(fams)
            orderlist.append(data)

        result = {"orderers": orderlist}

        if self.default_order is not None:
            result["default_order"] = to_pod(self.default_order)

        return result

    @classmethod
    def from_pod(cls, data):
        order_dict = {}
        default_order = None

        for d in data["orderers"]:
            d = d.copy()
            fams = d.pop("packages")
            orderer = from_pod(d)

            for fam in fams:
                order_dict[fam] = orderer

        d = data.get("default_order")
        if d:
            default_order = from_pod(d)

        return cls(order_dict, default_order)


class VersionSplitPackageOrder(PackageOrder):
    """Orders package versions <= a given version first.

    For example, given the versions [5, 4, 3, 2, 1], an orderer initialized
    with ``version=3`` would give the order [3, 2, 1, 5, 4].
    """
    name = "version_split"

    def __init__(self, first_version, packages=None):
        """Create a reorderer.

        Args:
            first_version (Version): Start with versions <= this value.
        """
        super().__init__(packages)
        self.first_version = first_version

    def sort_key_implementation(self, package_name, version):
        priority_key = 1 if version <= self.first_version else 0
        return priority_key, version

    def __str__(self):
        return str(self.first_version)

    def __eq__(self, other):
        return (
            type(other) == type(self)
            and self.first_version == other.first_version
        )

    def to_pod(self):
        """
        Example (in yaml):

        .. code-block:: yaml

           type: version_split
           first_version: "3.0.0"
           packages: ["foo"]
        """
        return dict(
            first_version=str(self.first_version),
            packages=self.packages,
        )

    @classmethod
    def from_pod(cls, data):
        return cls(
            Version(data["first_version"]),
            packages=data.get("packages"),
        )


class TimestampPackageOrder(PackageOrder):
    """A timestamp order function.

    Given a time ``T``, this orderer returns packages released before ``T``, in descending
    order, followed by those released after. If ``rank`` is non-zero, version
    changes at that rank and above are allowed over the timestamp.

    For example, consider the common case where we want to prioritize packages
    released before ``T``, except for newer patches. Consider the following package
    versions, and time ``T``:

    .. code-block:: text

       2.2.1
       2.2.0
       2.1.1
       2.1.0
       2.0.6
       2.0.5
             <-- T
       2.0.0
       1.9.0

    A timestamp orderer set to ``rank=3`` (patch versions) will attempt to consume
    the packages in the following order:

    .. code-block:: text

       2.0.6
       2.0.5
       2.0.0
       1.9.0
       2.1.1
       2.1.0
       2.2.1
       2.2.0

    Notice that packages before ``T`` are preferred, followed by newer versions.
    Newer versions are consumed in ascending order, except within rank (this is
    why 2.1.1 is consumed before 2.1.0).
    """
    name = "soft_timestamp"

    def __init__(self, timestamp, rank=0, packages=None):
        """Create a reorderer.

        Args:
            timestamp (int): Epoch time of timestamp. Packages before this time
                are preferred.
            rank (int): If non-zero, allow version changes at this rank or above
                past the timestamp.
        """
        super().__init__(packages)
        self.timestamp = timestamp
        self.rank = rank

        # dictionary mapping from package family to the first-version-after
        # the given timestamp
        self._cached_first_after = {}
        self._cached_sort_key = {}

    def _get_first_after(self, package_family):
        """Get the first package version that is after the timestamp"""
        try:
            first_after = self._cached_first_after[package_family]
        except KeyError:
            first_after = self._calc_first_after(package_family)
            self._cached_first_after[package_family] = first_after
        return first_after

    def _calc_first_after(self, package_family):
        descending = sorted(iter_packages(package_family),
                            key=lambda p: p.version,
                            reverse=True)
        first_after = None
        for i, package in enumerate(descending):
            if not package.timestamp:
                continue
            if package.timestamp > self.timestamp:
                first_after = package.version
            else:
                break

        if not self.rank:
            return first_after

        # if we have rank, then we need to then go back UP the
        # versions, until we find one whose trimmed version doesn't
        # match.
        # Note that we COULD do this by simply iterating through
        # an ascending sequence, in which case we wouldn't have to
        # "switch direction" after finding the first result after
        # by timestamp... but we're making the assumption that the
        # timestamp break will be closer to the higher end of the
        # version, and that we'll therefore have to check fewer
        # timestamps this way...
        trimmed_version = package.version.trim(self.rank - 1)
        first_after = None
        for after_package in reversed(descending[:i]):
            if after_package.version.trim(self.rank - 1) != trimmed_version:
                return after_package.version

        return first_after

    def _calc_sort_key(self, package_name, version):
        first_after = self._get_first_after(package_name)
        if first_after is None:
            # all packages are before T
            is_before = True
        else:
            is_before = int(version < first_after)

        if is_before:
            return is_before, version

        if self.rank:
            return (is_before,
                    _ReversedComparable(version.trim(self.rank - 1)),
                    version.tokens[self.rank - 1:])

        return is_before, _ReversedComparable(version)

    def sort_key_implementation(self, package_name, version):
        cache_key = (package_name, str(version))
        result = self._cached_sort_key.get(cache_key)
        if result is None:
            result = self._calc_sort_key(package_name, version)
            self._cached_sort_key[cache_key] = result

        return result

    def __str__(self):
        return str((self.timestamp, self.rank))

    def __eq__(self, other):
        return (
            type(other) == type(self)
            and self.timestamp == other.timestamp
            and self.rank == other.rank
        )

    def to_pod(self):
        """
        Example (in yaml):

        .. code-block:: yaml

           type: soft_timestamp
           timestamp: 1234567
           rank: 3
           packages: ["foo"]
        """
        return dict(
            timestamp=self.timestamp,
            rank=self.rank,
            packages=self.packages,
        )

    @classmethod
    def from_pod(cls, data):
        return cls(
            data["timestamp"],
            rank=data.get("rank", 0),
            packages=data.get("packages"),
        )


class CustomPackageOrder(PackageOrder):
    """A package order that allows explicit specification of version ordering.
    Specified through the "packages" attributes, which should be a dict which
    maps from a package family name to a list of version ranges to prioritize,
    in decreasing priority order.

    As an example, consider a package splunge which has versions:
      [1.0, 1.1, 1.2, 1.4, 2.0, 2.1, 3.0, 3.2]
    By default, version priority is given to the higest version, so version
    priority, from most to least preferred, is:
      [3.2, 3.0, 2.1, 2.0, 1.4, 1.2, 1.1, 1.0]

    However, if you set a custom package order like this:
      package_orderers:
      - type: custom
        packages:
          splunge: ['2', '1.1+<1.4']

    Then the preferred versions, from most to least preferred, will be:
     [2.1, 2.0, 1.2, 1.1, 3.2, 3.0, 1.4, 1.0]
    Any version which does not match any of these expressions are sorted in
    decreasing version order (like normal) and then appended to this list (so they
    have lower priority). This provides an easy means to effectively set a
    "default version."  So if you do:
      package_orderers:
      - type: custom
        packages:
          splunge: ['3.0']

    resulting order is:
      [3.0, 3.2, 2.1, 2.0, 1.4, 1.2, 1.1, 1.0]
    You may also include a single False or empty string in the list, in which case
    all "other" versions will be placed at that spot. ie
      package_orderers:
      - type: custom
        packages:
          splunge: ['', '3+']
    yields:
     [2.1, 2.0, 1.4, 1.2, 1.1, 1.0, 3.2, 3.0]

    Note that you could also have gotten the same result by doing:
      package_orderers:
      - type: custom
        packages:
          splunge: ['<3']
    If a version matches more than one range expression, it will be placed at
    the highest-priority matching spot, so:
      package_orderers:
      - type: custom
        packages:
          splunge: ['1.2+<=2.0', '1.1+<3']
    gives:
     [2.0, 1.4, 1.2, 2.1, 1.1, 3.2, 3.0, 1.0]

    Also note that this does not change the version sort order for any purpose but
    determining solving priorities - for instance, even if version priorities is:
      package_orderers:
      - type: custom
        packages:
          splunge: [2, 3, 1]
    The expression splunge-1+<3 would still match version 2.
    """
    name = "custom"

    def __init__(self,
                 packages: Dict[str, List[Union[str, VersionRange]]],
                 version_orderer: Optional[PackageOrder] = None,
                 ):
        """
        Args:
            packages: (Dict[str, List[VersionRange]]): packages that
                this orderer should apply to, and the version priority ordering
                for that package
            version_orderer (Optional[PackageOrder]):
                How versions are sorted within custom version ranges.
                If not provided, will use the standard rez version sorting.
        """
        super().__init__(list(packages))
        self.packages_dict = self._packages_from_pod(packages)
        self.version_orderer = version_orderer

        self._version_key_cache = {}

    def sort_key_implementation(self, package_name, version):
        family_cache = self._version_key_cache.setdefault(package_name, {})
        key = family_cache.get(version)
        if key is not None:
            return key
        key = self._version_priority_key_uncached(package_name, version)
        family_cache[version] = key
        return key

    def __str__(self):
        return str(self.packages_dict)

    def _version_priority_key_uncached(self, package_name, version: Version):
        version_priorities = self.packages_dict[package_name]

        default_key = -1
        for sort_order_index, version_range in enumerate(version_priorities):
            # in the config, version_priorities are given in decreasing
            # priority order... however, we want a sort key that sorts in the
            # same way that versions do - where higher values are higher
            # priority - so we need to take the inverse of the index
            priority_sort_key = len(version_priorities) - sort_order_index
            if version_range in (False, ""):
                if default_key != -1:
                    raise ValueError("version_priorities may only have one "
                                     "False / empty value")
                default_key = priority_sort_key
                continue
            if version_range.contains_version(version):
                break
        else:
            # For now, we're permissive with the version_sort_order - it may
            # contain ranges which match no actual versions, and if an actual
            # version matches no entry in the version_sort_order, it is simply
            # placed after other entries
            priority_sort_key = default_key

        if self.version_orderer:
            version_key = self.version_orderer.sort_key_implementation(package_name, version)
        else:
            version_key = version

        return priority_sort_key, version_key

    @staticmethod
    def _packages_to_pod(packages: Dict[str, List[Union[str, VersionRange]]]) -> Dict[str, List[str]]:
        return {
            package: [str(v) for v in versions]
            for (package, versions) in packages.items()
        }

    @staticmethod
    def _packages_from_pod(
            packages: Dict[str, List[Union[str, VersionRange]]],
    ) -> Dict[str, List[Union[str, VersionRange]]]:
        parsed_dict = {}
        for package, versions in packages.items():
            new_versions = []
            num_false = 0
            for v in versions:
                if v in ("", False):
                    v = False
                    num_false += 1
                else:
                    if not isinstance(v, VersionRange):
                        if isinstance(v, (int, float)):
                            v = str(v)
                        v = VersionRange(v)
                new_versions.append(v)
            if num_false > 1:
                raise ConfigurationError("version_priorities for CustomPackageOrder may "
                                         "only have one False / empty value")
            parsed_dict[package] = new_versions
        return parsed_dict

    def to_pod(self):
        return dict(
            packages=self._packages_to_pod(self.packages_dict),
            version_orderer=to_pod(self.version_orderer) if self.version_orderer else None,
        )

    @classmethod
    def from_pod(cls, data):
        version_orderer = data["version_orderer"]
        return cls(
            packages=data["packages"],
            version_orderer=from_pod(version_orderer) if version_orderer else None,
        )


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
        return super().clear(*args, **kwargs)

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

        cls = _orderers[cls_name]
        return cls.from_pod(data)
    else:
        # old-style, kept for backwards compatibility
        cls_name, data_ = data
        cls = _orderers[cls_name]
        return cls.from_pod(data_)


def get_orderer(package_name, orderers=None):
    if orderers is None:
        orderers = PackageOrderList.singleton
    orderer = orderers.get(package_name)
    if orderer is None:
        orderer = orderers.get(ALL_PACKAGES)
    if orderer is None:
        # default ordering is version descending
        orderer = SortedOrder(descending=True)
    return orderer


def register_orderer(cls):
    """Register an orderer

    Args:
        cls (type[PackageOrder]): Package orderer class to register.

    returns:
        bool: True if successfully registered, else False.
    """
    if isclass(cls) and issubclass(cls, PackageOrder) and \
            hasattr(cls, "name") and cls.name:
        _orderers[cls.name] = cls
        return True
    else:
        return False


# registration of builtin orderers
_orderers = {}
for o in list(globals().values()):
    register_orderer(o)
