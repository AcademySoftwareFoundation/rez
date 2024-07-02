# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project

from rez.package_order import PackageOrder, to_pod, from_pod


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
            type(self) is type(other)
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


def register_plugin():
    return PerFamilyOrder