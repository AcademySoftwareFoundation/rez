# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


from __future__ import annotations

from typing import Any, List, TYPE_CHECKING

from rez.config import config
from rez.package_order import PackageOrder, from_pod, to_pod
from rez.utils.data_utils import cached_class_property


class PackageOrderList(List[PackageOrder]):
    """A list of package orderer.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
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
