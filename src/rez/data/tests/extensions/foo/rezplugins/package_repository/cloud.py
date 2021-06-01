
from rez.package_repository import PackageRepository


class CloudPackageRepository(PackageRepository):
    @classmethod
    def name(cls):
        return "cloud"


def register_plugin():
    return CloudPackageRepository
