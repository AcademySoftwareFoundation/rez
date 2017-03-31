from inspect import isclass
from hashlib import sha1
import collections

from rez.vendor.version.version import Version

DEFAULT_TOKEN = "<DEFAULT>"

class PackageOrder(object):
    """Package reorderer base class."""
    name = None

    def __init__(self):
        pass

    def reorder(self, iterable, key=None):
        """Put packages into some order for consumption.

        You can safely assume that the packages referred to by `iterable` are
        all versions of the same package family.

        Args:
            iterable: Iterable list of packages, or objects that contain packages.
            key (callable): Callable, where key(iterable) gives a `Package`. If
                None, iterable is assumed to be a list of `Package` objects.

        Returns:
            List of `iterable` type, reordered.
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


class NullPackageOrder(PackageOrder):
    """An orderer that does not change the order - a no op.

    This orderer is useful in cases where you want to apply some default orderer
    to a set of packages, but may want to explicitly NOT reorder a particular
    package. You would use a `NullPackageOrder` in a `PerFamilyOrder` to do this.
    """
    name = "no_order"

    def __init__(self, packages):
        self.packages = packages

    def reorder(self, iterable, key=None):
        return list(iterable)

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

    def reorder(self, iterable, key=None):
        key = key or (lambda x: x)
        return sorted(iterable, key=lambda x: key(x).version,
                      reverse=self.descending)

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

    def reorder(self, iterable, key=None):
        try:
            item = iter(iterable).next()
        except:
            return None

        key = key or (lambda x: x)
        package = key(item)

        orderer = self.order_dict.get(package.name, self.default_order)
        return orderer.reorder(iterable, key)

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

    def reorder(self, iterable, key=None):
        key = key or (lambda x: x)

        # sort by version descending
        descending = sorted(iterable, key=lambda x: key(x).version, reverse=True)

        above = []
        below = []
        is_above = True

        for item in descending:
            if is_above:
                package = key(item)
                is_above = (package.version > self.first_version)

            if is_above:
                above.append(item)
            else:
                below.append(item)

        return below + above

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

    def reorder(self, iterable, key=None):
        reordered = []
        first_after = None
        key = key or (lambda x: x)

        # sort by version descending
        descending = sorted(iterable, key=lambda x: key(x).version, reverse=True)

        for i, o in enumerate(descending):
            package = key(o)
            if package.timestamp:
                if package.timestamp > self.timestamp:
                    first_after = i
                else:
                    break

        if first_after is None:
            # all packages are before T, just use version descending
            return descending

        before = descending[first_after + 1:]
        after = list(reversed(descending[:first_after + 1]))

        if not self.rank:  # simple case
            return before + after

        # include packages after timestamp but within rank
        if before and after:
            package = key(before[0])
            first_prerank = package.version.trim(self.rank - 1)

            for i, o in enumerate(after):
                package = key(o)
                prerank = package.version.trim(self.rank - 1)
                if prerank != first_prerank:
                    break

            if i:
                before = list(reversed(after[:i])) + before
                after = after[i:]

        # ascend below rank, but descend within
        after_ = []
        postrank = []
        prerank = None

        for o in after:
            package = key(o)
            prerank_ = package.version.trim(self.rank - 1)

            if prerank_ == prerank:
                postrank.append(o)
            else:
                after_.extend(reversed(postrank))
                postrank = [o]
                prerank = prerank_

        after_.extend(reversed(postrank))
        return before + after_

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


class OrdererDict(collections.Mapping):
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
