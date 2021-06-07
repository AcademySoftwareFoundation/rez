
from rez.package_repository import PackageRepository


class MemoryPackageRepository(PackageRepository):
    @classmethod
    def name(cls):
        return "memory"
    on_test = "non-mod"


def register_plugin():
    return MemoryPackageRepository
