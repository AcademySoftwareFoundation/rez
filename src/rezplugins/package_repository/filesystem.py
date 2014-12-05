"""
Filesystem-based package repository
"""
from rez.package_repository import PackageRepository, PackageFamilyResource, \
    PackageResource
from rez.resources_ import ResourceHandle, cached_property
from rez.backport.lru_cache import lru_cache
import os.path
import os


class FileSystemPackageFamilyResource(PackageFamilyResource):
    key = "filesystem.family"

    @cached_property
    def path(self):
        return os.path.join(self.location, self.name)

    def iter_packages(self):
        for name in os.listdir(self.path):
            if name.startswith('.'):
                continue
            path = os.path.join(self.path, name)
            if os.path.isdir(path):
                handle = ResourceHandle(FileSystemPackageResource.key,
                                        dict(location=self.location,
                                             name=self.name,
                                             version=name))
                package = self._repository._get_resource(handle)
                yield package


class FileSystemPackageResource(PackageResource):
    key = "filesystem.package"


class FileSystemPackageRepository(PackageRepository):
    """A filesystem-based package repository.

    Packages are stored on disk, in either 'package.yaml' or 'package.py' files.
    These files are stored into an organised directory structure like so:

        /LOCATION/pkgA/1.0.0/package.py
                      /1.0.1/package.py
                 /pkgB/2.1/package.py
                      /2.2/package.py
    """
    @classmethod
    def name(cls):
        return "filesystem"

    def __init__(self, location, resource_pool):
        """Create a filesystem package repository.

        Args:
            location (str): Path containing the package repository.
            resource_pool (`ResourcePool`): Pool to manage all resources from
                this repository.
        """
        super(FileSystemPackageRepository, self).__init__(location, resource_pool)
        self.pool.register_resource(FileSystemPackageFamilyResource)
        self.pool.register_resource(FileSystemPackageResource)

    def get_package_family(self, name):
        return self._get_family(name)

    def iter_package_families(self):
        for family in self._get_families():
            yield family

    def iter_packages(self, package_family_resource):
        for package in self._get_packages(package_family_resource):
            yield package

    # -- internal

    @lru_cache(maxsize=None)
    def _get_families(self):
        families = []
        for name in os.listdir(self.location):
            family = self._get_family(name)
            families.append(family)
        return families

    @lru_cache(maxsize=None)
    def _get_family(self, name):
        if os.path.isdir(os.path.join(self.location, name)):
            handle = ResourceHandle(FileSystemPackageFamilyResource.key,
                                    dict(location=self.location,
                                         name=name))
            family = self._get_resource(handle)
            return family
        return None

    @lru_cache(maxsize=None)
    def _get_packages(self, package_family_resource):
        return [x for x in package_family_resource.iter_packages()]


def register_plugin():
    return FileSystemPackageRepository
