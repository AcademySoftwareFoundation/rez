# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


from __future__ import annotations

from typing import TYPE_CHECKING

from rez.package_order import PackageOrder
from rez.utils.typing import SupportsLessThan
from rez.version import Version

if TYPE_CHECKING:
    from typing import Self


class VersionSplitPackageOrder(PackageOrder):
    """Orders package versions <= a given version first.

    For example, given the versions [5, 4, 3, 2, 1], an orderer initialized
    with ``version=3`` would give the order [3, 2, 1, 5, 4].
    """

    name = "version_split"

    def __init__(self, first_version: Version, packages: list[str] | None = None) -> None:
        """Create a reorderer.

        Args:
            first_version (Version): Start with versions <= this value.
        """
        super().__init__(packages)
        self.first_version = first_version

    def sort_key_implementation(self, package_name: str, version: Version) -> SupportsLessThan:
        priority_key = 1 if version <= self.first_version else 0
        return priority_key, version

    def __str__(self) -> str:
        return str(self.first_version)

    def __eq__(self, other):
        return type(other) is type(self) and self.first_version == other.first_version

    def to_pod(self) -> dict[str, object]:
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
    def from_pod(cls, data: dict[str, object]) -> Self:
        return cls(
            Version(data["first_version"]),
            packages=data.get("packages"),
        )


def register_plugin():
    return VersionSplitPackageOrder
