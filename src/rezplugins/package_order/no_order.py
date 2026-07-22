# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


from __future__ import annotations

from typing import TYPE_CHECKING

from rez.package_order import PackageOrder
from rez.utils.typing import SupportsLessThan
from rez.version import Version

if TYPE_CHECKING:
    from typing import Self


class NullPackageOrder(PackageOrder):
    """An orderer that does not change the order - a no op.

    This orderer is useful in cases where you want to apply some default orderer
    to a set of packages, but may want to explicitly NOT reorder a particular
    package. You would use a :class:`NullPackageOrder` in a :class:`PerFamilyOrder` to do this.
    """

    name = "no_order"

    def sort_key_implementation(self, package_name: str, version: Version) -> SupportsLessThan:
        # python's sort will preserve the order of items that compare equal, so
        # to not change anything, we just return the same object for all...
        return 0

    def __str__(self) -> str:
        return "{}"

    def __eq__(self, other):
        return type(self) is type(other)

    def to_pod(self) -> dict[str, object]:
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
    def from_pod(cls, data: dict[str, object]) -> Self:
        return cls(packages=data.get("packages"))


def register_plugin():
    return NullPackageOrder
