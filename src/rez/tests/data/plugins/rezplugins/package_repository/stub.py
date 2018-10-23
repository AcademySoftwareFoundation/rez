from rez.package_repository import PackageRepository


class StubRepository(PackageRepository):
    schema_dict = {
        "floob": bool
    }


def register_plugin():
    return StubRepository
