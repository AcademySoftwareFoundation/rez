# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project

from rez.package_order import PackageOrder
from rez.version._version import _ReversedComparable


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
            type(self) is type(other)
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


def register_plugin():
    return SortedOrder
