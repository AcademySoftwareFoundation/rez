
from rez.package_repository import PackageRepository


class MemoryPackageRepository(PackageRepository):
    @classmethod
    def name(cls):
        return "memory"
    on_test = "bar"


def register_plugin():
    return MemoryPackageRepository
