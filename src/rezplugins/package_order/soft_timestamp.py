# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project

from rez.package_order import PackageOrder
from rez.packages import iter_packages
from rez.version._version import _ReversedComparable


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
            type(self) is type(other)
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


def register_plugin():
    return TimestampPackageOrder
