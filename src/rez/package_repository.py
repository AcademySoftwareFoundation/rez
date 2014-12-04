


def get_package_repository_types():
    """Returns the available package repository implementations."""
    from rez.plugin_managers import plugin_manager
    return plugin_manager.get_plugins('package_repository')


class PackageRepository(object):
    @classmethod
    def name(cls):
        """Return the name of the package repository type."""
        raise NotImplementedError

    def __init__(self, location):
        """Create a package repository.

        Args:
            location (str): A string specifying the location of the repository.
                This could be a filesystem path, or a database uri, etc.
        """
        self.location = location

    def iter_package_families(self):
        """Iterate over the package families in the repository, in no
        particular order.

        Returns:
            `ResourceHandle` iterator. The associated resource must be a
            `PackageFamilyResource` subclass.
        """
        raise NotImplementedError
