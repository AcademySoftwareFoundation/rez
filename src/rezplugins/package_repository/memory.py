"""
In-memory package repository
"""
from rez.package_repository import PackageRepository
from rez.package_resources_ import PackageFamilyResource, PackageResource, \
    VariantResourceHelper, PackageResourceHelper, package_pod_schema
from rez.exceptions import PackageMetadataError
from rez.utils.formatting import is_valid_package_name, PackageRequest
from rez.utils.resources import ResourceHandle, ResourcePool, cached_property
from rez.vendor.version.requirement import VersionedObject


# This repository type is used when loading 'developer' packages (a package.yaml
# or package.py in a developer's working directory), and when programmatically
# creating packages via `PackageMaker`.


#------------------------------------------------------------------------------
# resource classes
#------------------------------------------------------------------------------

class MemoryPackageFamilyResource(PackageFamilyResource):
    key = "memory.family"
    repository_type = "memory"

    def _uri(self):
        return "%s:%s" % (self.location, self.name)

    def iter_packages(self):
        data = self._repository.data.get(self.name, {})

        # check for unversioned package
        if "_NO_VERSION" in data:
            package = self._repository.get_resource(
                MemoryPackageResource.key,
                location=self.location,
                name=self.name)
            yield package
            return

        # versioned packages
        for version_str in data.keys():
            package = self._repository.get_resource(
                MemoryPackageResource.key,
                location=self.location,
                name=self.name,
                version=version_str)
            yield package


class MemoryPackageResource(PackageResourceHelper):
    key = "memory.package"
    variant_key = "memory.variant"
    repository_type = "memory"
    schema = package_pod_schema

    def _uri(self):
        obj = VersionedObject.construct(self.name, self.version)
        return "%s:%s" % (self.location, str(obj))

    @property
    def base(self):
        return None  # memory types do not have 'base'

    @cached_property
    def parent(self):
        family = self._repository.get_resource(
            MemoryPackageFamilyResource.key,
            location=self.location,
            name=self.name)
        return family

    def _load(self):
        family_data = self._repository.data.get(self.name, {})
        version_str = self.get("version")
        if not version_str:
            version_str = "_NO_VERSION"
        package_data = family_data.get(version_str, {})
        return package_data


class MemoryVariantResource(VariantResourceHelper):
    key = "memory.variant"
    repository_type = "memory"

    def _root(self):
        return None  # memory types do not have 'root'

    @cached_property
    def parent(self):
        package = self._repository.get_resource(
            MemoryPackageResource.key,
            location=self.location,
             name=self.name,
             version=self.get("version"))
        return package


#------------------------------------------------------------------------------
# repository
#------------------------------------------------------------------------------

class MemoryPackageRepository(PackageRepository):
    """An in-memory package repository.

    Packages are stored in a dict, organised like so:

        {
            "foo": {
                "1.0.0": {
                    "name":         "foo",
                    "version":      "1.0.0",
                    "description":  "does foo-like things.",
                }
            },

            "bah": {
                "_NO_VERSION": {
                    "name":         "bah",
                    "description":  "does bah-like things.",
                    "requires":     ["python-2.6", "foo-1+"]
                }
            }
        }

        This example repository contains one versioned package 'foo', and one
        unversioned package 'bah'.
    """
    @classmethod
    def name(cls):
        return "memory"

    @classmethod
    def create_repository(cls, repository_data):
        """Create a standalone, in-memory repository.

        Using this function bypasses the `package_repository_manager` singleton.
        This is usually desired however, since in-memory repositories are for
        temporarily storing programmatically created packages, which we do not
        want to cache and that do not persist.

        Args:
            repository_data (dict): Repository data, see class docstring.

        Returns:
            `MemoryPackageRepository` object.
        """
        location = "memory{%s}" % hex(id(repository_data))
        resource_pool = ResourcePool(cache_size=None)
        repo = MemoryPackageRepository(location, resource_pool)
        repo.data = repository_data
        return repo

    def __init__(self, location, resource_pool):
        """Create an in-memory package repository.

        Args:
            location (str): Path containing the package repository.
        """
        super(MemoryPackageRepository, self).__init__(location, resource_pool)
        self.data = {}
        self.register_resource(MemoryPackageFamilyResource)
        self.register_resource(MemoryPackageResource)
        self.register_resource(MemoryVariantResource)

    def get_package_family(self, name):
        is_valid_package_name(name, raise_error=True)
        if name in self.data:
            family = self.get_resource(
                MemoryPackageFamilyResource.key,
                location=self.location,
                name=name)
            return family
        return None

    def iter_package_families(self):
        for name in self.data.keys():
            family = self.get_package_family(name)
            yield family

    def iter_packages(self, package_family_resource):
        for package in package_family_resource.iter_packages():
            yield package

    def iter_variants(self, package_resource):
        for variant in package_resource.iter_variants():
            yield variant

    def get_parent_package_family(self, package_resource):
        return package_resource.parent

    def get_parent_package(self, variant_resource):
        return variant_resource.parent


def register_plugin():
    return MemoryPackageRepository


# Copyright 2013-2016 Allan Johns.
#
# This library is free software: you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.
