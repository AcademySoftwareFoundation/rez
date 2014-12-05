from rez.resources_ import Resource, ResourcePool, Required, cached_property
from rez.exceptions import PackageMetadataError, ResourceError
from rez.plugin_managers import plugin_manager
from rez.vendor.version.version import Version
from rez.vendor.schema.schema import Schema, Optional
from rez.backport.lru_cache import lru_cache


package_family_schema = Schema({
    Required("name"):               basestring
})


package_schema = Schema({
    Required("name"):               basestring,
    Optional("version"):            Version,
    Optional('description'):        basestring
})


class PackageRepositoryResource(Resource):
    """Base class for all package-related resources."""
    schema_error = PackageMetadataError

    def __init__(self, variables=None):
        super(PackageRepositoryResource, self).__init__(variables)
        self._repository = None

    @property
    def location(self):
        return self.variables["location"]

    @property
    def name(self):
        return self.variables["name"]


class PackageFamilyResource(PackageRepositoryResource):
    """A package family.

    A repository implementation's package family resource(s) must derive from
    this class. It must satisfy the schema `package_family_schema`.
    """
    pass


class PackageResource(PackageRepositoryResource):
    """A package.

    A repository implementation's package resource(s) must derive from this
    class. It must satisfy the schema `package_schema`.
    """
    @cached_property
    def version(self):
        ver_str = self.get("version", "")
        return Version(ver_str)


def get_package_repository_types():
    """Returns the available package repository implementations."""
    return plugin_manager.get_plugins('package_repository')


class PackageRepository(object):
    """Base class for package repositories implemented in the package_repository
    plugin type.
    """
    @classmethod
    def name(cls):
        """Return the name of the package repository type."""
        raise NotImplementedError

    def __init__(self, location, resource_pool):
        """Create a package repository.

        Args:
            location (str): A string specifying the location of the repository.
                This could be a filesystem path, or a database uri, etc.
            resource_pool (`ResourcePool`): The pool used to manage package
                resources.
        """
        self.location = location
        self.pool = resource_pool

    def get_package_family(self, name):
        """Get a package family.

        Args:
            name (str): Package name.

        Returns:
            `PackageFamilyResource`, or None if not found.
        """
        raise NotImplementedError

    def iter_package_families(self):
        """Iterate over the package families in the repository, in no
        particular order.

        Returns:
            `PackageFamilyResource` iterator.
        """
        raise NotImplementedError

    def iter_packages(self, package_family_resource):
        """Iterate over the packages within the given family, in no particular
        order.

        Args:
            package_family_resource (`PackageFamilyResource`): Parent family.

        Returns:
            `PackageResource` iterator.
        """
        raise NotImplementedError

    def _get_resource(self, resource_handle):
        resource = self.pool.get_resource_from_handle(resource_handle)
        assert isinstance(resource, PackageRepositoryResource)
        resource._repository = self
        return resource


class PackageRepositoryManager(object):
    """Package repository manager.

    Contains instances of `PackageRepository` for each repository pointed to
    by the 'packages_path' config setting (also commonly set using the
    environment variable $REZ_PACKAGES_PATH).
    """
    def __init__(self):
        self.pool = ResourcePool()  # TODO hook up cachesize to rezconfig

    @lru_cache(maxsize=None)
    def get_repository(self, path):
        """Get a package repository.

        Args:
            path (str): Entry from the 'packages_path' config setting. This may
                simply be a path (which is managed by the 'filesystem' package
                repository plugin), or a string in the form "type:location",
                where 'type' identifies the plugin type to use.

        Returns:
            `PackageRepository` instance.
        """
        if ':' not in path:
            path = "filesystem:%s" % path
        return self._get_repository(path)

    def get_resource(self, resource_handle):
        """Get a resource.

        Args:
            resource_handle (`ResourceHandle`): Handle of the resource.

        Returns:
            `PackageRepositoryResource` instance.
        """
        repo_type = resource_handle.get("repository_type", "filesystem")
        location = resource_handle["location"]
        path = "%s:%s" % (repo_type, location)

        repo = self.get_repository(path)
        resource = self.pool.get_resource_from_handle(resource_handle)
        resource._repository = repo
        return resource

    def clear_caches(self):
        """Clear all caches and repositories."""
        self.get_repository.clear_caches()
        self._get_repository.clear_caches()
        self.pool.clear_caches()

    @lru_cache(maxsize=None)
    def _get_repository(self, path):
        repo_type, location = path.split(':', 1)
        cls = plugin_manager.get_plugin_class('package_repository', repo_type)
        repo = cls(location, self.pool)
        return repo


# singleton
package_repository_manager = PackageRepositoryManager()
