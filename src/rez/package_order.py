from inspect import isclass
from hashlib import sha1
import collections
from abc import ABCMeta, abstractmethod

from rez.exceptions import ConfigurationError
from rez.utils.yaml import YamlDumpable
from rez.vendor.version.version import _Comparable, _ReversedComparable, Version

DEFAULT_TOKEN = "<DEFAULT>"


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
        return '%s(%r, %r)' % (type(self).__name__, self.main_comparable,
                               self.fallback_comparable)


class PackageOrder(YamlDumpable):
    """Package reorderer base class."""
    __metaclass__ = ABCMeta

    name = None

    def __init__(self):
        pass

    def sort_key(self, package_name, version_like):
        """Returns a sort key usable for sorting these packages within the
        same family

        Args:
            package_name: (str) The family name of the package we are sorting
            verison_like: (Version|_LowerBound|_UpperBound|_Bound|VersionRange)
                the version-like object you wish to generate a key for

        Returns:
            Comparable object
        """
        from rez.vendor.version.version import Version, _LowerBound, _UpperBound, _Bound, VersionRange
        if isinstance(version_like, VersionRange):
            return tuple(self.sort_key(package_name, bound)
                         for bound in version_like.bounds)
        elif isinstance(version_like, _Bound):
            return (self.sort_key(package_name, version_like.lower),
                    self.sort_key(package_name, version_like.upper))
        elif isinstance(version_like, _LowerBound):
            inclusion_key = -2 if version_like.inclusive else -1
            return (self.sort_key(package_name, version_like.version),
                    inclusion_key)
        elif isinstance(version_like, _UpperBound):
            inclusion_key = 2 if version_like.inclusive else 1
            return (self.sort_key(package_name, version_like.version),
                    inclusion_key)
        elif isinstance(version_like, Version):
            # finally, the bit that we actually use the sort_key_implementation
            # for...
            # Need to use a FallbackComparable because we can compare versions
            # of different packages...
            return FallbackComparable(
                self.sort_key_implementation(package_name, version_like),
                version_like)
        else:
            raise TypeError(version_like)

    @abstractmethod
    def sort_key_implementation(self, package_name, version):
        """Returns a sort key usable for sorting these packages within the
        same family

        Args:
            package_name: (str) The family name of the package we are sorting
            verison: (Version) the version object you wish to generate a key for

        Returns:
            Comparable object
        """
        raise NotImplementedError

    # override this if you have an orderer that doesn't store packages
    # in the standard way
    @property
    def packages(self):
        """Returns an iterable over the list of package family names that this
        order applies to

        Returns:
            (iterable(str|None)) Package families that this orderer is used for
        """
        return self._packages

    @packages.setter
    def packages(self, packages):
        if isinstance(packages, basestring):
            self._packages = [packages]
        else:
            self._packages = sorted(packages)

    def to_yaml_pod(self):
        data = self.to_pod()
        data['type'] = self.name
        return data

    @abstractmethod
    def to_pod(self):
        raise NotImplementedError

    @classmethod
    def from_pod(self, data):
        raise NotImplementedError

    @property
    def sha1(self):
        return sha1(repr(self)).hexdigest()

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, str(self))

    def __eq__(self, other):
        return type(self) == type(other) and str(self) == str(other)

    # need to implement this to avoid infinite recursion!
    @abstractmethod
    def __str__(self):
        raise NotImplementedError


class NullPackageOrder(PackageOrder):
    """An orderer that does not change the order - a no op.

    This orderer is useful in cases where you want to apply some default orderer
    to a set of packages, but may want to explicitly NOT reorder a particular
    package. You would use a `NullPackageOrder` in a `PerFamilyOrder` to do this.
    """
    name = "no_order"

    def __init__(self, packages):
        self.packages = packages

    def sort_key_implementation(self, package_name, version):
        # python's sort will preserve the order of items that compare equal, so
        # to not change anything, we just return the same object for all...
        return 0

    def __str__(self):
        return str(self.packages)

    def to_pod(self):
        """
        Example (in yaml):

            type: no_order
            packages: ["foo"]
        """
        return {
            "packages": self.packages,
        }

    @classmethod
    def from_pod(cls, data):
        return cls(packages=data["packages"])


class SortedOrder(PackageOrder):
    """An orderer that sorts wrt version.
    """
    name = "sorted"

    def __init__(self, packages, descending):
        self.packages = packages
        self.descending = descending

    def sort_key_implementation(self, package_name, version):
        # Note that the name "descending" can be slightly confusing - it
        # indicates that the final ordering this Order gives should be
        # version descending (ie, the default) - however, the sort_key itself
        # returns it's results in "normal" ascending order (because it needs to
        # be used "alongside" normally-sorted objects like versions).
        # when the key is passed to sort(), though, it is always invoked with
        # reverse=True...
        if self.descending:
            return version
        else:
            return _ReversedComparable(version)

    def __str__(self):
        return str((self.packages, self.descending))

    def to_pod(self):
        """
        Example (in yaml):

            type: sorted
            packages: ["foo", "bar"]
            descending: true
        """
        return {
            "packages": self.packages,
            "descending": self.descending
        }

    @classmethod
    def from_pod(cls, data):
        return cls(packages=data["packages"], descending=data["descending"])


class PerFamilyOrder(PackageOrder):
    """WARNING: this orderer is DEPRECATED. It was implemented for performance
    reasons that are no longer required!
    
    An orderer that applies different orderers to different package families.
    """
    name = "per_family"

    def __init__(self, order_dict, default_order=None):
        """WARNING: this orderer is DEPRECATED. It was implemented for
        performance reasons that are no longer required!

        Create a reorderer.

        Args:
            order_dict (dict of (str, `PackageOrder`): Orderers to apply to
                each package family.
            default_order (`PackageOrder`): Orderer to apply to any packages
                not specified in `order_dict`.
        """
        import warnings
        warnings.warn("The %s orderer is deprecated - it was implemented for"
                      " performance reasons that are no longer required"
                      % type(self).__name__)

        self.order_dict = order_dict.copy()
        if default_order is None:
            default_order = NullPackageOrder(DEFAULT_TOKEN)
        self.default_order = default_order

    def sort_key_implementation(self, package_name, version):
        orderer = self.order_dict.get(package_name)
        if orderer is None:
            if self.default_order is not None:
                orderer = self.default_order
            else:
                # shouldn't get here, because applies_to should protect us...
                raise RuntimeError("package family orderer %r does not apply to package family %r",
                    (self, package_name))
        return orderer.sort_key_implementation(package_name, version)

    @property
    def packages(self):
        return iter(self.order_dict)

    def __str__(self):
        items = sorted((x[0], str(x[1])) for x in self.order_dict.items())
        return str((items, str(self.default_order)))

    def to_pod(self):
        """
        Example (in yaml):

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
        for fam, orderer in self.order_dict.iteritems():
            k = id(orderer)
            orderers[k] = orderer
            packages.setdefault(k, set()).add(fam)

        orderlist = []
        for k, fams in packages.iteritems():
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
            orderer = from_pod(d)

            for fam in orderer.packages:
                order_dict[fam] = orderer

        d = data.get("default_order")
        if d:
            default_order = from_pod(d)

        return cls(order_dict, default_order)


class VersionSplitPackageOrder(PackageOrder):
    """Orders package versions <= a given version first.

    For example, given the versions [5, 4, 3, 2, 1], an orderer initialized
    with version=3 would give the order [3, 2, 1, 5, 4].
    """
    name = "version_split"

    def __init__(self, packages, first_version):
        """Create a reorderer.

        Args:
            packages: (str or list of str): packages that this orderer should apply to
            first_version (`Version`): Start with versions <= this value.
        """
        self.packages = packages
        self.first_version = first_version

    def sort_key_implementation(self, package_name, version):
        priority_key = 1 if version <= self.first_version else 0
        return (priority_key, version)

    def __str__(self):
        return str((self.packages, self.first_version))

    def to_pod(self):
        """
        Example (in yaml):

            type: version_split
            packages: ["foo", "bar"]
            first_version: "3.0.0"
        """
        return dict(packages=self.packages,
                    first_version=str(self.first_version))

    @classmethod
    def from_pod(cls, data):
        return cls(packages=data["packages"],
                   first_version=Version(data["first_version"]))


class TimestampPackageOrder(PackageOrder):
    """A timestamp order function.

    Given a time T, this orderer returns packages released before T, in descending
    order, followed by those released after. If `rank` is non-zero, version
    changes at that rank and above are allowed over the timestamp.

    For example, consider the common case where we want to prioritize packages
    released before T, except for newer patches. Consider the following package
    versions, and time T:

        2.2.1
        2.2.0
        2.1.1
        2.1.0
        2.0.6
        2.0.5
              <-- T
        2.0.0
        1.9.0

    A timestamp orderer set to rank=3 (patch versions) will attempt to consume
    the packages in the following order:

        2.0.6
        2.0.5
        2.0.0
        1.9.0
        2.1.1
        2.1.0
        2.2.1
        2.2.0

    Notice that packages before T are preferred, followed by newer versions.
    Newer versions are consumed in ascending order, except within rank (this is
    why 2.1.1 is consumed before 2.1.0).
    """
    name = "soft_timestamp"

    def __init__(self, packages, timestamp, rank=0):
        """Create a reorderer.

        Args:
            packages: (str or list of str): packages that this orderer should apply to
            timestamp (int): Epoch time of timestamp. Packages before this time
                are preferred.
            rank (int): If non-zero, allow version changes at this rank or above
                past the timestamp.
        """
        self.packages = packages
        self.timestamp = timestamp
        self.rank = rank

        # dictionary mapping from package family to the first-version-after
        # the given timestamp
        self._cached_first_after = {}
        self._cached_sort_key = {}

    def get_first_after(self, package_family):
        first_after = self._cached_first_after.get(package_family, KeyError)
        if first_after is KeyError:
            first_after = self._calc_first_after(package_family)
            self._cached_first_after[package_family] = first_after
        return first_after

    def _calc_first_after(self, package_family):
        from rez.packages_ import iter_packages
        descending = sorted(iter_packages(package_family),
                             key=lambda p: p.version,
                             reverse=True)

        first_after = None
        for i, package in enumerate(descending):
            if package.timestamp:
                if package.timestamp > self.timestamp:
                    first_after = package.version
                else:
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
        return first_after

    def _calc_sort_key(self, package_name, version):
        first_after = self.get_first_after(package_name)
        if first_after is None:
            # all packages are before T
            is_before = True
        else:
            is_before = int(version < first_after)

        # ascend below rank, but descend within
        if is_before:
            return (is_before, version)
        else:
            if self.rank:
                return (is_before,
                        _ReversedComparable(version.trim(self.rank - 1)),
                        version.tokens[self.rank - 1:])
            else:
                return (is_before, _ReversedComparable(version))

    def sort_key_implementation(self, package_name, version):
        cache_key = (package_name, str(version))
        result = self._cached_sort_key.get(cache_key)
        if result is None:
            result = self._calc_sort_key(package_name, version)
            self._cached_sort_key[cache_key] = result
        return result

    def __str__(self):
        return str((self.packages, self.timestamp, self.rank))

    def to_pod(self):
        """
        Example (in yaml):

            type: soft_timestamp
            packages: ["foo", "bar"]
            timestamp: 1234567
            rank: 3
        """
        return dict(packages=self.packages,
                    timestamp=self.timestamp,
                    rank=self.rank)

    @classmethod
    def from_pod(cls, data):
        return cls(packages=data["packages"],
                   timestamp=data["timestamp"],
                   rank=data.get("rank", 0))


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

    def __init__(self, packages):
        """Create a reorderer.

        Args:
            packages: (dict from str to list of VersionRange): packages that
                this orderer should apply to, and the version priority ordering
                for that package
        """
        self.packages_dict = self._packages_from_pod(packages)
        self._version_key_cache = {}

    def sort_key_implementation(self, package_name, version):
        family_cache = self._version_key_cache.setdefault(package_name, {})
        key = family_cache.get(version)
        if key is not None:
            return key

        key = self.version_priority_key_uncached(package_name, version)
        family_cache[version] = key
        return key

    @property
    def packages(self):
        return iter(self.packages_dict)

    def __str__(self):
        return str(self.packages_dict)

    def version_priority_key_uncached(self, package_name, version):
        version_priorities = self.packages_dict[package_name]

        default_key = -1
        for sort_order_index, range in enumerate(version_priorities):
            # in the config, version_priorities are given in decreasing
            # priority order... however, we want a sort key that sorts in the
            # same way that versions do - where higher values are higher
            # priority - so we need to take the inverse of the index
            priority_sort_key = len(version_priorities) - sort_order_index
            if range in (False, ""):
                if default_key != -1:
                    raise ValueError("version_priorities may only have one "
                                     "False / empty value")
                default_key = priority_sort_key
                continue
            if range.contains_version(version):
                break
        else:
            # For now, we're permissive with the version_sort_order - it may
            # contain ranges which match no actual versions, and if an actual
            # version matches no entry in the version_sort_order, it is simply
            # placed after other entries
            priority_sort_key = default_key
        return priority_sort_key, version

    @classmethod
    def _packages_to_pod(cls, packages):
        return dict((package, [str(v) for v in versions])
                    for (package, versions) in packages.iteritems())

    @classmethod
    def _packages_from_pod(cls, packages):
        from rez.vendor.version.version import VersionRange
        parsed_dict = {}
        for package, versions in packages.iteritems():
            new_versions = []
            numFalse = 0
            for v in versions:
                if v in ("", False):
                    v = False
                    numFalse += 1
                else:
                    if not isinstance(v, VersionRange):
                        if isinstance(v, (int, float)):
                            v = str(v)
                        v = VersionRange(v)
                new_versions.append(v)
            if numFalse > 1:
                raise ConfigurationError("version_priorities for CustomPackageOrder may only have one False / empty value")
            parsed_dict[package] = new_versions
        return parsed_dict

    def to_pod(self):
        return dict(packages=self._packages_to_pod(self.packages_dict))

    @classmethod
    def from_pod(cls, data):
        return cls(packages=data["packages"])


class OrdererDict(collections.Mapping, YamlDumpable):
    def __init__(self, orderer_list):
        self.list = []
        self.by_package = {}

        for orderer in orderer_list:
            if not isinstance(orderer, PackageOrder):
                orderer = from_pod(orderer)
            self.list.append(orderer)
            for package in orderer.packages:
                # We allow duplicates (so we can have hierarchical configs,
                # which can override each other) - earlier orderers win
                if package in self.by_package:
                    continue
                self.by_package[package] = orderer

    def to_yaml_pod(self):
        return self.to_pod()

    def to_pod(self):
        return [to_pod(x) for x in self.list]

    def __repr__(self):
        return '%s(%r)' % (type(self).__name__, self.list)

    def __getitem__(self, package):
        return self.by_package[package]

    def __iter__(self):
        return iter(self.by_package)

    def __len__(self):
        return len(self.by_package)


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


def register_orderer(cls):
    if isclass(cls) and issubclass(cls, PackageOrder) and \
            hasattr(cls, "name") and cls.name:
        _orderers[cls.name] = cls
        return True
    else:
        return False


def get_orderer(package_name, orderers=None):
    from rez.config import config
    if orderers is None:
        orderers = config.package_orderers
    if not orderers:
        orderers = {}
    found_orderer = orderers.get(package_name)
    if found_orderer is None:
        found_orderer = orderers.get(DEFAULT_TOKEN)
        if found_orderer is None:
            # default ordering is version descending
            found_orderer = SortedOrder([DEFAULT_TOKEN], descending=True)
    return found_orderer


# registration of builtin orderers
_orderers = {}
for o in globals().values():
    register_orderer(o)


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
