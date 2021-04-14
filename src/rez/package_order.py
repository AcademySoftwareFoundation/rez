from inspect import isclass
from hashlib import sha1

from rez.config import config
from rez.utils.data_utils import cached_class_property
from rez.vendor.version.version import Version


class PackageOrder(object):
    """Package reorderer base class."""
    name = None

    def __init__(self):
        pass

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
            key (callable): Callable, where key(iterable) gives a `Package`. If
                None, iterable is assumed to be a list of `Package` objects.

        Returns:
            List of `iterable` type, reordered.
        """
        raise NotImplementedError

    def to_pod(self):
        raise NotImplementedError

    @property
    def sha1(self):
        return sha1(repr(self).encode('utf-8')).hexdigest()

    def __str__(self):
        raise NotImplementedError

    def __eq__(self, other):
        raise NotImplementedError

    def __ne__(self, other):
        return not self == other

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, str(self))


class NullPackageOrder(PackageOrder):
    """An orderer that does not change the order - a no op.

    This orderer is useful in cases where you want to apply some default orderer
    to a set of packages, but may want to explicitly NOT reorder a particular
    package. You would use a `NullPackageOrder` in a `PerFamilyOrder` to do this.
    """
    name = "no_order"

    def reorder(self, iterable, key=None):
        return list(iterable)

    def __str__(self):
        return "{}"

    def __eq__(self, other):
        return type(self) == type(other)

    def to_pod(self):
        """
        Example (in yaml):

            type: no_order
        """
        return {}

    @classmethod
    def from_pod(cls, data):
        return cls()


class SortedOrder(PackageOrder):
    """An orderer that sorts wrt version.
    """
    name = "sorted"

    def __init__(self, descending):
        self.descending = descending

    def reorder(self, iterable, key=None):
        key = key or (lambda x: x)
        return sorted(iterable, key=lambda x: key(x).version,
                      reverse=self.descending)

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

            type: sorted
            descending: true
        """
        return {"descending": self.descending}

    @classmethod
    def from_pod(cls, data):
        return cls(descending=data["descending"])


class PerFamilyOrder(PackageOrder):
    """An orderer that applies different orderers to different package families.
    """
    name = "per_family"

    def __init__(self, order_dict, default_order=None):
        """Create a reorderer.

        Args:
            order_dict (dict of (str, `PackageOrder`): Orderers to apply to
                each package family.
            default_order (`PackageOrder`): Orderer to apply to any packages
                not specified in `order_dict`.
        """
        self.order_dict = order_dict.copy()
        self.default_order = default_order

    def reorder(self, iterable, key=None):
        try:
            item = next(iter(iterable))
        except:
            return None

        key = key or (lambda x: x)
        package = key(item)

        orderer = self.order_dict.get(package.name)
        if orderer is None:
            orderer = self.default_order
        if orderer is None:
            return None

        return orderer.reorder(iterable, key)

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
    with version=3 would give the order [3, 2, 1, 5, 4].
    """
    name = "version_split"

    def __init__(self, first_version):
        """Create a reorderer.

        Args:
            first_version (`Version`): Start with versions <= this value.
        """
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
        return str(self.first_version)

    def __eq__(self, other):
        return (
            type(other) == type(self)
            and self.first_version == other.first_version
        )

    def to_pod(self):
        """
        Example (in yaml):

            type: version_split
            first_version: "3.0.0"
        """
        return dict(first_version=str(self.first_version))

    @classmethod
    def from_pod(cls, data):
        return cls(Version(data["first_version"]))


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

    def __init__(self, timestamp, rank=0):
        """Create a reorderer.

        Args:
            timestamp (int): Epoch time of timestamp. Packages before this time
                are preferred.
            rank (int): If non-zero, allow version changes at this rank or above
                past the timestamp.
        """
        self.timestamp = timestamp
        self.rank = rank

    def reorder(self, iterable, key=None):
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

        if first_after is None:  # all packages are before T
            return None

        before = descending[first_after + 1:]
        after = list(reversed(descending[:first_after + 1]))

        if not self.rank:  # simple case
            return before + after

        # include packages after timestamp but within rank
        if before and after:
            package = key(before[0])
            first_prerank = package.version.trim(self.rank - 1)
            found = False

            for i, o in enumerate(after):
                package = key(o)
                prerank = package.version.trim(self.rank - 1)
                if prerank != first_prerank:
                    found = True
                    break

            if not found:
                # highest version is also within rank, so result is just
                # simple descending list
                return descending

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

            type: soft_timestamp
            timestamp: 1234567
            rank: 3
        """
        return dict(timestamp=self.timestamp,
                    rank=self.rank)

    @classmethod
    def from_pod(cls, data):
        return cls(timestamp=data["timestamp"], rank=data.get("rank", 0))


class PackageOrderList(list):
    """A list of package orderer.
    """
    def to_pod(self):
        data = []
        for f in self:
            data.append(to_pod(f))
        return data

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


# registration of builtin orderers
_orderers = {}
for o in list(globals().values()):
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
