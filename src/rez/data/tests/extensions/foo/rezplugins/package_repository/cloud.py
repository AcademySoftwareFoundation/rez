from rez.package_repository import PackageRepository


class CloudPackageRepository(PackageRepository):
    @classmethod
    def name(cls) -> str:
        return "cloud"


def register_plugin():
    return CloudPackageRepository
